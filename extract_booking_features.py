#!/usr/bin/env python3
"""
Extract structured accommodation features from downloaded Booking.com detail HTML pages
and candidate metadata, matching the schema used by properties_structured.json.
"""

import argparse
import glob
import json
import csv
import os
import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup


DEFAULT_CANDIDATES_JSON = "booking_candidates_20_40.json"
DEFAULT_HTML_DIR = "booking_html"
DEFAULT_OUTPUT_JSON = "booking_properties_structured.json"
DEFAULT_OUTPUT_CSV = "booking_properties_structured.csv"


def extract_features_from_detail_html(html: str) -> Dict[str, Any]:
    """Parse JSON-LD and DOM from Booking detail page."""
    soup = BeautifulSoup(html, "html.parser")

    # 1. JSON-LD schema
    ld_script = soup.find("script", type="application/ld+json")
    ld = {}
    if ld_script and ld_script.string:
        try:
            ld = json.loads(ld_script.string)
        except Exception:
            pass

    name = ld.get("name") or ""
    description = ld.get("description") or ""
    address = ld.get("address") or {}

    street = address.get("streetAddress", "")
    locality = address.get("addressLocality", "")
    region = address.get("addressRegion", "")
    postal = address.get("postalCode", "")

    # 2. Text inspection
    text = soup.get_text(" \n ", strip=True)

    # Sauna detection
    has_sauna = bool(re.search(r"\bsauna\b", text, re.I))
    sauna_type = "none"
    if has_sauna:
        if re.search(r"infra\s*saun", text, re.I):
            sauna_type = "infra"
        elif re.search(r"finsk[aá]\s*saun|finnish", text, re.I):
            sauna_type = "finnish"
        elif re.search(r"parn[ií]|steam", text, re.I):
            sauna_type = "steam"
        else:
            sauna_type = "sauna"

    # Pool detection
    has_pool = bool(re.search(r"\b(?:swimming\s+pool|baz[eé]n)\b", text, re.I))
    pool_notes = None
    if has_pool:
        if re.search(r"kryt[yý]\s*baz[eé]n|indoor\s+pool", text, re.I):
            pool_notes = "indoor pool"
        elif re.search(r"vyh[rř][ií]van[yý]\s*baz[eé]n|heated\s+pool", text, re.I):
            pool_notes = "heated pool"
        else:
            pool_notes = "outdoor pool"

    # Hot tub / Whirlpool detection
    has_hot_tub = bool(re.search(r"\b(?:hot\s+tub|whirlpool|v[ií][rř]ivk|koupac[ií]\s+sud)\b", text, re.I))
    hot_tub_notes = "Whirlpool / hot tub present" if has_hot_tub else None

    # Wi-Fi
    has_wifi = bool(re.search(r"\b(?:free\s+wifi|wi-fi|wifi)\b", text, re.I))

    # Dishwasher & Kitchen
    has_dishwasher = bool(re.search(r"\b(?:dishwasher|my[cč]k)\b", text, re.I))
    has_beer_tap = bool(re.search(r"\b(?:p[ií]p[ae]|v[yý][cč]ep|draft\s+beer)\b", text, re.I))

    # Table & Dining visual captions
    captions = re.findall(r'alt=["\']([^"\']*(?:table|dining|kitchen|living\s+room|desk)[^"\']*)["\']', html, re.I)
    unique_captions = sorted(list(set(c.strip() for c in captions if len(c.strip()) > 10)))

    tables_notes = ""
    for c in unique_captions:
        if "table" in c.lower() or "dining" in c.lower():
            tables_notes = c
            break

    # Photos count
    photos = re.findall(r'https?://[^"\'\s]+bstatic\.com/xdata/images/hotel/[^"\'\s]+', html)
    unique_photos = len(set(photos))

    return {
        "ld_name": name,
        "description": description,
        "street_address": street,
        "locality": locality,
        "region": region,
        "postal_code": postal,
        "has_sauna": has_sauna,
        "sauna_type": sauna_type,
        "has_pool": has_pool,
        "pool_notes": pool_notes,
        "has_hot_tub_or_whirlpool": has_hot_tub,
        "hot_tub_notes": hot_tub_notes,
        "wifi_available": has_wifi,
        "has_dishwasher": has_dishwasher,
        "beer_tap_available": has_beer_tap,
        "tables_and_workspace": tables_notes or "Table information extracted from photos",
        "photos_count": unique_photos,
        "photo_captions_sample": unique_captions[:6]
    }


def main():
    parser = argparse.ArgumentParser(description="Extract structured features from Booking candidate HTML files")
    parser.add_argument("--candidates", "-c", default=DEFAULT_CANDIDATES_JSON, help="Candidates JSON file")
    parser.add_argument("--html-dir", "-d", default=DEFAULT_HTML_DIR, help="Directory containing HTML files")
    parser.add_argument("--output-json", "-o", default=DEFAULT_OUTPUT_JSON, help="Output JSON file")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV, help="Output CSV file")
    args = parser.parse_args()

    if not os.path.exists(args.candidates):
        print(f"Error: {args.candidates} not found!")
        return

    with open(args.candidates, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    print(f"Loaded {len(candidates)} candidate accommodations.")

    structured_data = {}
    csv_rows = []

    for p in candidates:
        slug = p["slug"]
        html_file = os.path.join(args.html_dir, f"{slug}.html")

        detail = {}
        if os.path.exists(html_file):
            try:
                with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
                    html_content = f.read()
                detail = extract_features_from_detail_html(html_content)
            except Exception as e:
                print(f"Warning: error parsing {html_file}: {e}")

        # Combine candidate metadata with detail page findings
        cap_total = p.get("estimated_capacity") or p.get("cap_max") or 25
        beds_reg = p.get("cap_min") or p.get("total_beds") or cap_total
        beds_extra = max(0, cap_total - beds_reg)

        record = {
            "property_id": p["id"],
            "slug": slug,
            "name": p["name"],
            "url": p["url"],
            "review_score": p.get("review_score"),
            "capacity_total": cap_total,
            "beds_regular": beds_reg,
            "beds_extra": beds_extra,
            "bedrooms_count": p.get("bedrooms_count"),
            "bedroom_layout": p.get("breakdowns") or [],
            "toilets_count": None,
            "bathrooms_count": None,
            "has_sauna": detail.get("has_sauna", False),
            "sauna_type": detail.get("sauna_type", "none"),
            "has_hot_tub_or_whirlpool": detail.get("has_hot_tub_or_whirlpool", False),
            "hot_tub_notes": detail.get("hot_tub_notes"),
            "has_pool": detail.get("has_pool", False),
            "pool_notes": detail.get("pool_notes"),
            "common_room_description": detail.get("description", "")[:300],
            "tables_and_workspace": detail.get("tables_and_workspace", ""),
            "dishwashers_count": 1 if detail.get("has_dishwasher") else None,
            "beer_tap_available": detail.get("beer_tap_available", False),
            "wifi_available": detail.get("wifi_available", True),
            "exclusive_private_rental": p.get("is_entire_place", False),
            "street_address": detail.get("street_address", ""),
            "locality": detail.get("locality") or p.get("location", ""),
            "region": detail.get("region", ""),
            "photos_count": detail.get("photos_count", 0),
            "photo_captions_sample": detail.get("photo_captions_sample", []),
            "source": "booking.com"
        }

        structured_data[slug] = record

        csv_rows.append([
            p["id"], slug, p["name"], record["locality"], record["region"],
            p.get("review_score") or "", cap_total, beds_reg, beds_extra,
            p.get("bedrooms_count") or "", "YES" if p.get("is_entire_place") else "NO",
            "YES" if record["has_sauna"] else "NO",
            "YES" if record["has_pool"] else "NO",
            "YES" if record["has_hot_tub_or_whirlpool"] else "NO",
            "YES" if record["beer_tap_available"] else "NO",
            record["photos_count"], p["url"]
        ])

    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(structured_data, f, indent=2, ensure_ascii=False)

    with open(args.output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ID", "Slug", "Name", "Locality", "Region", "Review Score",
            "Capacity Total", "Beds Regular", "Beds Extra", "Bedrooms",
            "Entire Place", "Has Sauna", "Has Pool", "Has Hot Tub",
            "Beer Tap", "Photos Count", "URL"
        ])
        writer.writerows(csv_rows)

    print(f"\nSaved structured records:")
    print(f"  - {args.output_json} ({len(structured_data)} properties)")
    print(f"  - {args.output_csv}")


if __name__ == "__main__":
    main()
