import os
import time
import json
from typing import Any, Dict, List, Optional, Tuple

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

def place_text_search(api_key: str, query: str, page_token: Optional[str] = None) -> Dict[str, Any]:
    params = {"key": api_key}
    if page_token:
        params["pagetoken"] = page_token
    else:
        params["query"] = query
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
            state = comp.get("short_name") or state
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

# ---- Public API ----
def cafes_for_suburb(suburb: str, keyword: str = "cafe", max_leads: Optional[int] = None) -> pd.DataFrame:
    """Return a DataFrame of cafes for the given suburb. Limit with max_leads."""
    load_dotenv()

    # try Streamlit secrets first, then .env
    api_key = None
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set in st.secrets or .env")

    rows: List[Dict[str, Any]] = []
    query = f"{keyword} {suburb} QLD"
    page_token = None
    pages = 0
    while pages < 3:
        data = place_text_search(api_key, query, page_token)
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
        return df

    df = df.drop_duplicates(subset=["place_id"])
    if max_leads is not None:
        df = df.head(max_leads)

    enriched_rows: List[Dict[str, Any]] = []
    for pid, row in df.set_index("place_id").to_dict(orient="index").items():
        d = place_details(api_key, pid)
        merged = merge_details(row, d)
        enriched_rows.append(merged)
        if max_leads is not None and len(enriched_rows) >= max_leads:
            break
        time.sleep(0.1)

    out = pd.DataFrame(enriched_rows)
    cols = [
        "place_id","name","formatted_address","suburb","state","postcode",
        "lat","lng","phone","website","rating","rating_count",
        "opening_hours_json","business_status","types_json","maps_url","query_suburb","source"
    ]
    return out.reindex(columns=cols)
