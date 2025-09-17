# macro_lead_gen.py
import os
import time
import json
from typing import Any, Dict, List, Optional, Tuple, Literal

import pandas as pd
import requests
from dotenv import load_dotenv
import streamlit as st

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# ---- HTTP ----
def http_get(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    for attempt in range(5):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status")
            if status in ("OK", "ZERO_RESULTS"):
                return data
            if status == "INVALID_REQUEST":
                time.sleep(1.5); continue
            if status in ("OVER_QUERY_LIMIT", "RESOURCE_EXHAUSTED"):
                time.sleep(2 ** attempt); continue
            if status == "REQUEST_DENIED":
                raise RuntimeError(f"Request denied: {data}")
            if status == "UNKNOWN_ERROR":
                time.sleep(1.5); continue
        time.sleep(1.5)
    raise RuntimeError(f"Failed after retries. Last response: {r.status_code} {r.text[:200]}")

def place_text_search(
    api_key: str,
    query: str,
    page_token: Optional[str] = None,
    location: Optional[str] = None,   # "lat,lng"
    radius: Optional[int] = None,     # meters
    region: Optional[str] = None      # e.g. "au"
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"key": api_key}
    if page_token:
        params["pagetoken"] = page_token
    else:
        params["query"] = query
        if location: params["location"] = location
        if radius:   params["radius"] = radius
        if region:   params["region"] = region
    return http_get(TEXT_SEARCH_URL, params)

def place_details(api_key: str, place_id: str) -> Dict[str, Any]:
    fields = [
        "place_id","international_phone_number","website","opening_hours",
        "address_components","business_status","url"
    ]
    params = {"key": api_key, "place_id": place_id, "fields": ",".join(fields)}
    return http_get(DETAILS_URL, params)

# ---- Normalization ----
def parse_address_components(components: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    suburb = state = postcode = None
    for comp in components or []:
        types = comp.get("types", [])
        if "locality" in types or "postal_town" in types or "sublocality" in types:
            suburb = comp.get("long_name") or suburb
        if "administrative_area_level_1" in types:
            # Prefer long_name for full state, fallback to short
            state = comp.get("long_name") or comp.get("short_name") or state
        if "postal_code" in types:
            postcode = comp.get("long_name") or postcode
    return suburb, state, postcode

def flatten_search_result(r: Dict[str, Any]) -> Dict[str, Any]:
    geom = (r.get("geometry") or {}).get("location") or {}
    return {
        "place_id": r.get("place_id"),
        "name": r.get("name"),
        "formatted_address": r.get("formatted_address"),
        "lat": geom.get("lat"),
        "lng": geom.get("lng"),
        "rating": r.get("rating"),
        "rating_count": r.get("user_ratings_total"),
        "types_json": json.dumps(r.get("types", []), ensure_ascii=False),
        "business_status": r.get("business_status"),
        "source": "places_text_search",
    }

def merge_details(row: Dict[str, Any], details: Dict[str, Any]) -> Dict[str, Any]:
    result = details.get("result", {})
    suburb, state, postcode = parse_address_components(result.get("address_components", []))
    row.update({
        "phone": result.get("international_phone_number"),
        "website": result.get("website"),
        "opening_hours_json": json.dumps((result.get("opening_hours") or {}).get("weekday_text", []), ensure_ascii=False),
        "business_status": result.get("business_status", row.get("business_status")),
        "maps_url": result.get("url"),
        "suburb": suburb,
        "state": state,
        "postcode": postcode,
    })
    return row

# ---- Output shaping (to Capsule CRM template) ----
TEMPLATE_COLS = [
    "Organization", "Phone", "Email", "Website",
    "Office Address Street", "Office City", "Office State",
    "Office Postcode", "Office Country", "Tags"
]

def _street_from_formatted(addr: Optional[str], suburb: Optional[str]) -> Optional[str]:
    if not addr:
        return None
    if suburb and isinstance(suburb, str) and suburb in addr:
        return addr.split(suburb, 1)[0].rstrip(", ").strip()
    return addr

def _state_unabbreviator(state) -> str:
    try:
        if state is None or pd.isna(state):
            return "unknown"
    except Exception:
        return "unknown"
    s = str(state).strip().upper()
    MAP = {
        "VIC": "victoria",
        "NSW": "new_south_wales",
        "QLD": "queensland",
        "SA":  "south_australia",
        "WA":  "western_australia",
        "TAS": "tasmania",
        "NT":  "northern_territory",
        "ACT": "australian_capital_territory",
        # also accept full names
        "VICTORIA": "victoria",
        "NEW SOUTH WALES": "new_south_wales",
        "QUEENSLAND": "queensland",
        "SOUTH AUSTRALIA": "south_australia",
        "WESTERN AUSTRALIA": "western_australia",
        "TASMANIA": "tasmania",
        "NORTHERN TERRITORY": "northern_territory",
        "AUSTRALIAN CAPITAL TERRITORY": "australian_capital_territory",
    }
    return MAP.get(s, "unknown")

def to_capsule_template(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        "Organization": df["name"],
        "Phone": df.get("phone"),
        "Email": "",  # Places does not provide emails
        "Website": df.get("website"),
        "Office Address Street": df.apply(lambda r: _street_from_formatted(r.get("formatted_address"), r.get("suburb")), axis=1),
        "Office City": df.get("suburb"),
        "Office State": df.get("state"),
        "Office Postcode": df.get("postcode"),
        "Office Country": "Australia",
        "Tags": df.apply(
            lambda r: f"#newlead;type_cafe;location_{_state_unabbreviator(r.get('state'))};wholesale_supply_-_food_service;merch_tea_lists;merch_tester_tins",
            axis=1
        )
    })
    return out.reindex(columns=TEMPLATE_COLS)

# ---- Geocode helper for biasing the query ----
def _geocode_area(api_key: str, area_text: str) -> Optional[str]:
    # bias to AU to avoid overseas matches
    g = place_text_search(api_key, area_text, region="au")
    res = g.get("results", [])
    if not res:
        return None
    loc = (res[0].get("geometry") or {}).get("location") or {}
    lat, lng = loc.get("lat"), loc.get("lng")
    return f"{lat},{lng}" if lat is not None and lng is not None else None

# ---- Public API ----
def cafes_for_suburb(
    suburb: str,
    state: Optional[str] = None,          # e.g., "VIC", "New South Wales"
    keyword: str = "cafe",
    descriptor: str = "",
    max_leads: Optional[int] = None,
    return_format: str = "raw"
) -> pd.DataFrame:
    """Return raw Places DataFrame (rating, rating_count, opening_hours) or Capsule-formatted."""
    if return_format not in ("raw", "capsule"):
        raise ValueError("return_format must be 'raw' or 'capsule'")
    
    load_dotenv()

    api_key = st.secrets.get("GOOGLE_API_KEY") if hasattr(st, "secrets") else None
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set in st.secrets or .env")

    area_text = f"{suburb} {state}" if state else suburb
    location_bias = _geocode_area(api_key, area_text)

    text_query = (
        f"{descriptor} {keyword} in {suburb} {state}".strip()
        if state else f"{descriptor} {keyword} in {suburb}".strip()
    )

    rows: List[Dict[str, Any]] = []
    page_token = None
    pages = 0
    while pages < 3:
        data = place_text_search(
            api_key,
            text_query,
            page_token=page_token,
            location=location_bias,
            radius=3000,
            region="au"
        )
        results = data.get("results", [])
        for r in results:
            rows.append(flatten_search_result(r) | {"query_suburb": suburb})
            if max_leads is not None and len(rows) >= max_leads:
                break
        if max_leads is not None and len(rows) >= max_leads:
            break
        pages += 1
        page_token = data.get("next_page_token")
        if not page_token:
            break
        time.sleep(1.5)

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=[
            "place_id","name","formatted_address","lat","lng",
            "rating","rating_count","opening_hours_json","phone","website",
            "business_status","maps_url","suburb","state","postcode","types_json","query_suburb"
        ])

    df = df.drop_duplicates(subset=["place_id"]).sort_values(
        ["rating_count", "rating"], ascending=[False, False]
    )
    if max_leads is not None:
        df = df.head(max_leads)

    # Enrich with details
    enriched_rows: List[Dict[str, Any]] = []
    for pid, row in df.set_index("place_id").to_dict(orient="index").items():
        d = place_details(api_key, pid)
        merged = merge_details(row, d)
        enriched_rows.append(merged)
        if max_leads is not None and len(enriched_rows) >= max_leads:
            break
        time.sleep(0.1)

    enriched = pd.DataFrame(enriched_rows)

    # Raw view with extra fields for pandas filtering
    if return_format == "raw":
        cols = [
            "place_id","name","formatted_address","lat","lng",
            "rating","rating_count","opening_hours_json","phone","website",
            "business_status","maps_url","suburb","state","postcode","types_json","query_suburb"
        ]
        # keep existing plus any unexpected extras
        return enriched[[c for c in cols if c in enriched.columns]].copy()

    # Capsule template view
    return to_capsule_template(enriched)
