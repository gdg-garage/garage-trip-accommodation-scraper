#!/usr/bin/env python3
"""
Master Index & Multi-Year Accommodation Ledger for Garage Trip retreats.
Consolidates properties across e-chalupy.cz, Booking.com, and future sources into a unified,
deduplicated historical registry to prevent redundant processing and track historical evaluations.
"""

import argparse
import csv
import glob
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from typing import Dict, Any, List, Optional


DEFAULT_MASTER_JSON = "accommodations_master_index.json"
DEFAULT_MASTER_CSV = "accommodations_master_index.csv"
CURRENT_YEAR = 2026


def normalize(text: str) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]", "", s)


def build_master_index(
    echalupy_structured_path: str = "properties_structured.json",
    echalupy_final_csv_path: str = "rankings_garage_trip_final.csv",
    booking_structured_path: str = "booking_properties_structured.json",
    cross_validation_path: str = "cross_validation_matches.json",
    existing_master_path: Optional[str] = DEFAULT_MASTER_JSON
) -> Dict[str, Any]:
    """Build unified master index combining all known sources."""

    existing_index = {}
    if existing_master_path and os.path.exists(existing_master_path):
        try:
            with open(existing_master_path, "r", encoding="utf-8") as f:
                existing_index = json.load(f)
        except Exception:
            existing_index = {}

    # Load cross-validation matches to map Booking slugs -> e-chalupy IDs
    dual_matches_by_booking = {}
    dual_matches_by_echalupy = {}
    if os.path.exists(cross_validation_path):
        with open(cross_validation_path, "r", encoding="utf-8") as f:
            matches = json.load(f)
            for m in matches:
                dual_matches_by_booking[m["booking_slug"]] = m
                dual_matches_by_echalupy[str(m["echalupy_id"])] = m

    # Load e-chalupy rankings
    echalupy_rankings = {}
    if os.path.exists(echalupy_final_csv_path):
        with open(echalupy_final_csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                pid = r.get("Property ID")
                if pid:
                    echalupy_rankings[pid] = r

    # Map e-chalupy property ID to HTML filename and title
    echalupy_html_meta = {}
    for fp in glob.glob("html/*.html"):
        fn = os.path.basename(fp)
        m_id = re.search(r"-o(\d+)\.html$", fn)
        if m_id:
            pid = m_id.group(1)
            title = fn[:-5]
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    head = f.read(3000)
                m_t = re.search(r"<title>([^<]+)</title>", head, re.I)
                if m_t:
                    title = m_t.group(1).split("|")[0].split("-")[0].strip()
            except Exception:
                pass
            echalupy_html_meta[pid] = {"slug": fn[:-5], "title": title}

    # Load e-chalupy structured data
    echalupy_structured = {}
    if os.path.exists(echalupy_structured_path):
        with open(echalupy_structured_path, "r", encoding="utf-8") as f:
            echalupy_structured = json.load(f)

    # Load Booking structured data
    booking_structured = {}
    if os.path.exists(booking_structured_path):
        with open(booking_structured_path, "r", encoding="utf-8") as f:
            booking_structured = json.load(f)

    master: Dict[str, Dict[str, Any]] = {}
    today_str = datetime.now().strftime("%Y-%m-%d")

    # 1. Process e-chalupy properties
    for pid, ep in echalupy_structured.items():
        uid = f"echalupy_{pid}"
        rank_info = echalupy_rankings.get(pid, {})
        html_info = echalupy_html_meta.get(str(pid), {})

        name = rank_info.get("Name") or html_info.get("title") or f"e-chalupy property o{pid}"
        slug = html_info.get("slug") or f"o{pid}"
        town = rank_info.get("Village / Town") or ""
        region = rank_info.get("Region") or ""
        gps = rank_info.get("GPS") or ""
        final_score = float(rank_info["Final Score"]) if rank_info.get("Final Score") else None
        verdict = rank_info.get("Verdict") or ""

        # Check if cross-listed on Booking
        is_dual = str(pid) in dual_matches_by_echalupy
        dual_info = dual_matches_by_echalupy.get(str(pid))

        sources = ["echalupy.cz"]
        urls = {"echalupy": rank_info.get("URL") or f"https://www.e-chalupy.cz/{slug}"}
        source_ids = {"echalupy": str(pid)}

        booking_score = None
        if is_dual and dual_info:
            sources.append("booking.com")
            b_slug = dual_info["booking_slug"]
            urls["booking"] = dual_info["booking_url"]
            source_ids["booking"] = b_slug
            booking_score = dual_info.get("booking_review_score")

        master[uid] = {
            "uid": uid,
            "canonical_name": name,
            "sources": sources,
            "source_ids": source_ids,
            "urls": urls,
            "locality": town,
            "region": region,
            "gps": gps,
            "capacity_total": ep.get("capacity_total"),
            "beds_regular": ep.get("beds_regular"),
            "beds_extra": ep.get("beds_extra"),
            "bedrooms_count": ep.get("bedrooms_count"),
            "exclusive_private_rental": ep.get("exclusive_private_rental", True),
            "has_sauna": ep.get("has_sauna", False),
            "sauna_type": ep.get("sauna_type", "none"),
            "has_pool": ep.get("has_pool", False),
            "has_hot_tub": ep.get("has_hot_tub_or_whirlpool", False),
            "wifi_available": ep.get("wifi_available", True),
            "beer_tap_available": ep.get("beer_tap_available", False),
            "booking_rating": booking_score,
            "first_seen_year": 2026,
            "last_processed_date": today_str,
            "evaluated_years": [2026] if final_score else [],
            "status": "evaluated" if final_score else "candidate",
            "latest_final_score": final_score,
            "latest_verdict": verdict[:300] if verdict else None,
            "notes": ""
        }

    # 2. Process Booking.com properties
    for slug, bp in booking_structured.items():
        # Check if already unified under e-chalupy
        if slug in dual_matches_by_booking:
            dual_info = dual_matches_by_booking[slug]
            ep_id = str(dual_info["echalupy_id"])
            parent_uid = f"echalupy_{ep_id}"
            if parent_uid in master:
                # Already merged in step 1, enrich if needed
                if "booking.com" not in master[parent_uid]["sources"]:
                    master[parent_uid]["sources"].append("booking.com")
                master[parent_uid]["source_ids"]["booking"] = slug
                master[parent_uid]["urls"]["booking"] = bp["url"]
                master[parent_uid]["booking_rating"] = bp.get("review_score")
                continue

        # Booking-exclusive property
        uid = f"booking_{slug}"
        master[uid] = {
            "uid": uid,
            "canonical_name": bp["name"],
            "sources": ["booking.com"],
            "source_ids": {"booking": slug},
            "urls": {"booking": bp["url"]},
            "locality": bp.get("locality", ""),
            "region": bp.get("region", ""),
            "gps": "",
            "capacity_total": bp.get("capacity_total"),
            "beds_regular": bp.get("beds_regular"),
            "beds_extra": bp.get("beds_extra"),
            "bedrooms_count": bp.get("bedrooms_count"),
            "exclusive_private_rental": bp.get("exclusive_private_rental", False),
            "has_sauna": bp.get("has_sauna", False),
            "sauna_type": bp.get("sauna_type", "none"),
            "has_pool": bp.get("has_pool", False),
            "has_hot_tub": bp.get("has_hot_tub_or_whirlpool", False),
            "wifi_available": bp.get("wifi_available", True),
            "beer_tap_available": bp.get("beer_tap_available", False),
            "booking_rating": bp.get("review_score"),
            "first_seen_year": 2026,
            "last_processed_date": today_str,
            "evaluated_years": [],
            "status": "candidate",
            "latest_final_score": None,
            "latest_verdict": None,
            "notes": ""
        }

    return master


def save_master_index(master: Dict[str, Any], json_path: str = DEFAULT_MASTER_JSON, csv_path: str = DEFAULT_MASTER_CSV):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(master, f, indent=2, ensure_ascii=False)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "UID", "Name", "Sources", "Locality", "Region", "Capacity Total",
            "Bedrooms", "Beds Regular", "Entire Place", "Sauna", "Pool",
            "Hot Tub", "Beer Tap", "Booking Score", "Final Score 2026",
            "Status", "First Seen", "Last Processed", "Primary URL"
        ])
        for uid, p in sorted(master.items(), key=lambda x: (-(x[1].get("latest_final_score") or 0), x[1]["canonical_name"])):
            p_url = p["urls"].get("echalupy") or p["urls"].get("booking") or ""
            writer.writerow([
                p["uid"], p["canonical_name"], ", ".join(p["sources"]),
                p["locality"], p["region"], p["capacity_total"],
                p["bedrooms_count"] or "", p["beds_regular"] or "",
                "YES" if p["exclusive_private_rental"] else "NO",
                "YES" if p["has_sauna"] else "NO",
                "YES" if p["has_pool"] else "NO",
                "YES" if p["has_hot_tub"] else "NO",
                "YES" if p["beer_tap_available"] else "NO",
                p["booking_rating"] or "", p["latest_final_score"] or "",
                p["status"], p["first_seen_year"], p["last_processed_date"],
                p_url
            ])


def lookup_property(query: str, json_path: str = DEFAULT_MASTER_JSON):
    if not os.path.exists(json_path):
        print(f"Index {json_path} does not exist yet. Run --build first.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        master = json.load(f)

    norm_q = normalize(query)
    matches = []
    for uid, p in master.items():
        search_blob = normalize(p["canonical_name"] + " " + p["locality"] + " " + uid + " " + " ".join(p["source_ids"].values()))
        if norm_q in search_blob:
            matches.append(p)

    print(f"\nFound {len(matches)} matching accommodations for '{query}':")
    for m in matches[:15]:
        score_str = f" | Final Score: {m['latest_final_score']}" if m.get("latest_final_score") else ""
        b_score = f" | Booking: {m['booking_rating']}/10" if m.get("booking_rating") else ""
        print(f" • [{m['uid']}] {m['canonical_name']} ({m['locality']})")
        print(f"   Sources: {', '.join(m['sources'])}{score_str}{b_score} | Cap: {m['capacity_total']} | Status: {m['status']}")
        for src, u in m["urls"].items():
            print(f"   {src.upper()}: {u}")
        print()


def print_stats(json_path: str = DEFAULT_MASTER_JSON):
    if not os.path.exists(json_path):
        print(f"Index {json_path} does not exist yet.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        master = json.load(f)

    total = len(master)
    dual = sum(1 for p in master.values() if len(p["sources"]) > 1)
    echalupy_only = sum(1 for p in master.values() if p["sources"] == ["echalupy.cz"])
    booking_only = sum(1 for p in master.values() if p["sources"] == ["booking.com"])
    evaluated = sum(1 for p in master.values() if p["status"] == "evaluated")
    sauna_count = sum(1 for p in master.values() if p["has_sauna"])
    pool_count = sum(1 for p in master.values() if p["has_pool"])

    print("\n==============================================")
    print("      ACCOMMODATION MASTER INDEX STATS        ")
    print("==============================================")
    print(f"Total Unique Accommodations:         {total}")
    print(f"  • Cross-Listed on Both Platforms:  {dual}")
    print(f"  • Exclusive to e-chalupy.cz:       {echalupy_only}")
    print(f"  • Exclusive to Booking.com:        {booking_only}")
    print(f"Evaluated with AI Scores:            {evaluated}")
    print(f"With Sauna Facilities:               {sauna_count}")
    print(f"With Swimming Pool:                  {pool_count}")
    print("==============================================")


def main():
    parser = argparse.ArgumentParser(description="Master Index for Multi-Year Accommodation Tracking")
    parser.add_argument("--build", action="store_true", help="Build or rebuild master index")
    parser.add_argument("--lookup", "-l", type=str, help="Search index for a property name, town, or ID")
    parser.add_argument("--stats", "-s", action="store_true", help="Display index statistics")
    args = parser.parse_args()

    if args.build or not os.path.exists(DEFAULT_MASTER_JSON):
        print("Building master index from e-chalupy and Booking datasets...")
        master = build_master_index()
        save_master_index(master)
        print(f"Master index saved with {len(master)} properties.")
        print(f"  - {DEFAULT_MASTER_JSON}")
        print(f"  - {DEFAULT_MASTER_CSV}")

    if args.lookup:
        lookup_property(args.lookup)

    if args.stats or (not args.lookup and not args.build):
        print_stats()


if __name__ == "__main__":
    main()
