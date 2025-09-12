"""
QLD Cafes – Places API Starter

Usage:
  python app.py --subs path/to/suburbs.xlsx --out cafes.xlsx \
      [--sheet Sheet1] [--suburb-col Suburb] [--keyword cafe]

Requires:
  - Python 3.10+
  - pip install -r requirements.txt
  - .env file with GOOGLE_API_KEY=...

Outputs:
  - Excel (or CSV) with cafes aggregated by suburb via Places Text Search + Details
"""

import argparse
import os
import sys
import time
import json
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# ---- Helpers ----
def load_suburbs(xlsx_path: str, sheet: Optional[str], suburb_col: Optional[str]) -> List[str]:
    df = pd.read_excel(xlsx_path, sheet_name=sheet) if sheet else pd.read_excel(xlsx_path)
    col = suburb_col if suburb_col and suburb_col in df.columns else df.columns[0]
    subs = (
        df[col]
        .astype(str)
        .map(lambda x: x.strip())
        .replace({"": pd.NA})
        .dropna()
        .drop_duplicates()
        .tolist()
    )
    return subs

def http_get(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    for attempt in range(5):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status")
            if status in ("OK", "ZERO_RESULTS"):
                return data
            if status == "INVALID_REQUEST":
                time.sleep(1.5)
                continue
            if status in ("OVER_QUERY_LIMIT", "RESOURCE_EXHAUSTED"):
                time.sleep(2 ** attempt)
                continue
            if status == "REQUEST_DENIED":
                raise RuntimeError(f"Request denied: {data}")
            if status == "UNKNOWN_ERROR":
                time.sleep(1.5)
                continue
        else:
            time.sleep(1.5)
            continue
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

# ---- Runner ----
def run(suburbs: List[str], api_key: str, keyword: str) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for s in suburbs:
        query = f"{keyword} {s} QLD"
        page_token = None
        pages = 0
        while pages < 3:
            data = place_text_search(api_key, query, page_token)
            results = data.get("results", [])
            for r in results:
                rows.append(flatten_search_result(r) | {"query_suburb": s})
            pages += 1
            page_token = data.get("next_page_token")
            if not page_token:
                break
            time.sleep(1.5)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates(subset=["place_id"])
    enriched_rows: List[Dict[str, Any]] = []
    for pid, row in df.set_index("place_id").to_dict(orient="index").items():
        d = place_details(api_key, pid)
        merged = merge_details(row, d)
        enriched_rows.append(merged)
        time.sleep(0.1)
    out = pd.DataFrame(enriched_rows)
    cols = [
        "place_id","name","formatted_address","suburb","state","postcode",
        "lat","lng","phone","website","rating","rating_count",
        "opening_hours_json","business_status","types_json","maps_url","query_suburb","source"
    ]
    out = out.reindex(columns=cols)
    return out

# ---- Main ----
def main():
    parser = argparse.ArgumentParser(description="Extract cafes by suburb via Google Places Text Search + Details")
    parser.add_argument("--subs", required=True, help="Path to Excel with suburbs")
    parser.add_argument("--out", required=True, help="Output path (.xlsx or .csv)")
    parser.add_argument("--sheet", help="Excel sheet name (optional)")
    parser.add_argument("--suburb-col", help="Column name with suburbs (default: first column)")
    parser.add_argument("--keyword", default="cafe", help="Search keyword, default 'cafe'")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set in environment or .env", file=sys.stderr)
        sys.exit(1)

    suburbs = load_suburbs(args.subs, args.sheet, args.suburb_col)
    if not suburbs:
        print("No suburbs loaded. Check your Excel and column name.", file=sys.stderr)
        sys.exit(1)

    df = run(suburbs, api_key, args.keyword)

    if args.out.lower().endswith(".csv"):
        df.to_csv(args.out, index=False)
    else:
        df.to_excel(args.out, index=False)
    print(f"Wrote {len(df):,} rows -> {args.out}")

if __name__ == "__main__":
    main()
