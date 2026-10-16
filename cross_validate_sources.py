#!/usr/bin/env python3
"""
Cross-validation tool between Booking.com and e-chalupy.cz datasets.
Identifies properties present on both platforms, compares reported capacities,
and outputs a comprehensive overlap report.
"""

import argparse
import csv
import glob
import json
import os
import re
import unicodedata
from typing import Dict, Any, List, Set, Tuple


DEFAULT_BOOKING_JSON = "booking_candidates_20_40.json"
DEFAULT_ECHALUPY_CSV = "rankings_garage_trip_final.csv"
DEFAULT_ECHALUPY_HTML_DIR = "html"
DEFAULT_OUTPUT_JSON = "cross_validation_matches.json"
DEFAULT_OUTPUT_CSV = "cross_validation_matches.csv"


STOP_WORDS = {
    "horska", "chata", "chalupa", "roubenka", "penzion", "pension", "vila",
    "villa", "apartmany", "apartman", "dum", "hotel", "residence", "areal",
    "celkovy", "objekt", "ubytovani", "pronajem", "pronajmuti", "velke",
    "nove", "maly", "mala", "dolni", "horni", "pod", "nad", "ceske", "morave",
    "home", "holiday", "house", "pro", "osob", "hostu", "group", "chalet", "czech"
}

DISTINCTIVE_KEYWORDS = {
    "inffinity", "frantiskov", "hribek", "tauhaus", "boubelka", "vogelsang",
    "hostacov", "vrchovina", "sladku", "javorinka", "walterovka", "buchtovna",
    "borovka", "havana", "ralisce", "urban", "lisenka", "pisecne", "dalov",
    "kvetna", "anicka", "strakuv", "jablunka", "satelit", "stara", "skola",
    "krasna", "lipka", "moravsky", "karlov", "rejdice", "purkartice", "bezvetri"
}


def normalize_tokens(text: str) -> Set[str]:
    if not text:
        return set()
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]", " ", s)
    tokens = set()
    for w in s.split():
        if len(w) >= 3 and w not in STOP_WORDS:
            tokens.add(w)
    return tokens


def extract_echalupy_catalog(html_dir: str, csv_path: Optional[str] = None) -> List[Dict[str, Any]]:
    catalog = []
    csv_map = {}
    if csv_path and os.path.exists(csv_path):
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                p_id = r.get("Property ID")
                if p_id:
                    csv_map[p_id] = r

    for fp in glob.glob(os.path.join(html_dir, "*.html")):
        slug = os.path.splitext(os.path.basename(fp))[0]
        m_id = re.search(r"-o(\d+)$", slug)
        prop_id = m_id.group(1) if m_id else slug

        title = slug
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(3000)
            m_t = re.search(r"<title>([^<]+)</title>", head, re.I)
            if m_t:
                title = m_t.group(1).split("|")[0].split("-")[0].strip()
        except Exception:
            pass

        csv_info = csv_map.get(prop_id, {})

        catalog.append({
            "id": prop_id,
            "slug": slug,
            "title": csv_info.get("Name") or title,
            "locality": csv_info.get("Village / Town", ""),
            "capacity": csv_info.get("Capacity Total", ""),
            "url": csv_info.get("URL") or f"https://www.e-chalupy.cz/{slug}",
            "tokens": normalize_tokens(title) | normalize_tokens(slug) | normalize_tokens(csv_info.get("Name", "")),
            "loc_tokens": normalize_tokens(csv_info.get("Village / Town", ""))
        })
    return catalog


def cross_validate(booking_json: str, html_dir: str, csv_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    with open(booking_json, "r", encoding="utf-8") as f:
        booking_data = json.load(f)

    echalupy_data = extract_echalupy_catalog(html_dir, csv_path)

    matches = []
    matched_echalupy_ids = set()

    for b in booking_data:
        b_name = b["name"]
        b_tokens = normalize_tokens(b_name) | normalize_tokens(b["slug"])
        b_loc_tokens = normalize_tokens(b.get("location", ""))

        best_ep = None
        best_score = 0
        shared_tokens = []

        for ep in echalupy_data:
            overlap = b_tokens.intersection(ep["tokens"])
            meaningful = [w for w in overlap if w not in STOP_WORDS]
            loc_match = bool(b_loc_tokens.intersection(ep["loc_tokens"])) if b_loc_tokens and ep["loc_tokens"] else False

            score = 0
            # Distinctive cottage names
            distinctive_hits = [w for w in meaningful if w in DISTINCTIVE_KEYWORDS and w not in ["stara", "skola", "krasna"]]
            if distinctive_hits:
                score += 4 * len(distinctive_hits)
            else:
                score += len(meaningful)

            if loc_match:
                score += 3

            # Require either a distinctive name hit, or location match + token, or multiple meaningful tokens
            is_valid_match = False
            if distinctive_hits:
                is_valid_match = True
            elif loc_match and len(meaningful) >= 1:
                is_valid_match = True
            elif len(meaningful) >= 2 and not any(w in ["stara", "skola", "krasna", "morava"] for w in meaningful):
                is_valid_match = True

            if is_valid_match and score >= 4 and score > best_score:
                best_score = score
                best_ep = ep
                shared_tokens = meaningful

        if best_ep:
            matched_echalupy_ids.add(best_ep["id"])
            matches.append({
                "booking_id": b["id"],
                "booking_slug": b["slug"],
                "booking_name": b["name"],
                "booking_capacity": b["estimated_capacity"],
                "booking_review_score": b.get("review_score"),
                "booking_url": b["url"],
                "echalupy_id": best_ep["id"],
                "echalupy_slug": best_ep["slug"],
                "echalupy_name": best_ep["title"],
                "echalupy_capacity": best_ep["capacity"],
                "echalupy_url": best_ep["url"],
                "match_score": best_score,
                "shared_keywords": shared_tokens
            })

    stats = {
        "booking_candidates_count": len(booking_data),
        "echalupy_catalog_count": len(echalupy_data),
        "matched_count": len(matches),
        "booking_exclusive_count": len(booking_data) - len(matches),
        "echalupy_exclusive_count": len(echalupy_data) - len(matched_echalupy_ids)
    }

    return matches, stats


def main():
    parser = argparse.ArgumentParser(description="Cross-validate Booking and e-chalupy datasets")
    parser.add_argument("--booking", default=DEFAULT_BOOKING_JSON, help="Booking candidates JSON")
    parser.add_argument("--echalupy-csv", default=DEFAULT_ECHALUPY_CSV, help="e-chalupy CSV")
    parser.add_argument("--echalupy-html", default=DEFAULT_ECHALUPY_HTML_DIR, help="e-chalupy HTML dir")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON, help="Output matches JSON")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV, help="Output matches CSV")
    args = parser.parse_args()

    matches, stats = cross_validate(args.booking, args.echalupy_html, args.echalupy_csv)

    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

    with open(args.output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Booking ID", "Booking Name", "Booking Cap", "Booking Score", "Booking URL",
            "e-chalupy ID", "e-chalupy Name", "e-chalupy Cap", "e-chalupy URL",
            "Confidence Score", "Shared Keywords"
        ])
        for m in matches:
            writer.writerow([
                m["booking_id"], m["booking_name"], m["booking_capacity"],
                m["booking_review_score"] or "", m["booking_url"],
                m["echalupy_id"], m["echalupy_name"], m["echalupy_capacity"],
                m["echalupy_url"], m["match_score"], ", ".join(m["shared_keywords"])
            ])

    print("\n==============================================")
    print("      CROSS-VALIDATION & OVERLAP REPORT       ")
    print("==============================================")
    print(f"Total Booking Candidates (20-40 cap): {stats['booking_candidates_count']}")
    print(f"Total e-chalupy Scraped Catalog:     {stats['echalupy_catalog_count']}")
    print(f"Cross-Platform Matches (on Both):    {stats['matched_count']}")
    print(f"Booking-Exclusive Accommodations:    {stats['booking_exclusive_count']}")
    print(f"e-chalupy-Exclusive Accommodations:  {stats['echalupy_exclusive_count']}")
    print("==============================================")
    print(f"\nSaved matches to {args.output_json} and {args.output_csv}")


if __name__ == "__main__":
    main()
