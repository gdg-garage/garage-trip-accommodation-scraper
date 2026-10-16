#!/usr/bin/env python3
"""
Filter and export whole-house Booking.com accommodations (20-40 capacity)
with cross-validation status, enriched amenities, and Google Drive export.
"""

import csv
import json
import os
import shutil
from typing import Dict, Any, List


BOOKING_STRUCTURED_JSON = "booking_properties_structured.json"
CROSS_VALIDATION_JSON = "cross_validation_matches.json"
OUTPUT_JSON = "booking_whole_objects_20_40.json"
OUTPUT_CSV = "booking_whole_objects_20_40.csv"
GDRIVE_DIR = "/Users/tivvit/Library/CloudStorage/GoogleDrive-tivvitmail@gmail.com/My Drive/Garage Trip 7.0 2026"


def main():
    if not os.path.exists(BOOKING_STRUCTURED_JSON):
        print(f"Error: {BOOKING_STRUCTURED_JSON} not found!")
        return

    with open(BOOKING_STRUCTURED_JSON, "r", encoding="utf-8") as f:
        props = json.load(f)

    matches_by_slug = {}
    if os.path.exists(CROSS_VALIDATION_JSON):
        with open(CROSS_VALIDATION_JSON, "r", encoding="utf-8") as f:
            for m in json.load(f):
                matches_by_slug[m["booking_slug"]] = m

    whole_objects = []

    for slug, p in props.items():
        # Keep only whole object rentals
        if not p.get("exclusive_private_rental", False):
            continue

        match_info = matches_by_slug.get(slug)
        dual_listed = match_info is not None

        enriched = dict(p)
        enriched["is_dual_listed"] = dual_listed
        enriched["echalupy_match_id"] = match_info["echalupy_id"] if match_info else None
        enriched["echalupy_match_name"] = match_info["echalupy_name"] if match_info else None
        enriched["echalupy_match_url"] = match_info["echalupy_url"] if match_info else None

        whole_objects.append(enriched)

    # Sort by Review Score descending (with None at the end), then by Capacity Total descending
    whole_objects.sort(
        key=lambda x: (
            -(x.get("review_score") or 0),
            -(x.get("capacity_total") or 0)
        )
    )

    # Save JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(whole_objects, f, indent=2, ensure_ascii=False)

    # Save CSV
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Rank", "Name", "Review Score", "Capacity Total", "Beds Regular",
            "Beds Extra", "Bedrooms", "Locality", "Region", "Has Sauna",
            "Sauna Type", "Has Pool", "Has Hot Tub", "Beer Tap",
            "Photos Count", "Bed Breakdown", "On e-chalupy?",
            "e-chalupy ID", "e-chalupy URL", "Booking URL"
        ])
        for idx, o in enumerate(whole_objects, 1):
            writer.writerow([
                idx,
                o["name"],
                o.get("review_score") or "",
                o.get("capacity_total") or "",
                o.get("beds_regular") or "",
                o.get("beds_extra") or "",
                o.get("bedrooms_count") or "",
                o.get("locality") or "",
                o.get("region") or "",
                "YES" if o.get("has_sauna") else "NO",
                o.get("sauna_type") or "none",
                "YES" if o.get("has_pool") else "NO",
                "YES" if o.get("has_hot_tub_or_whirlpool") else "NO",
                "YES" if o.get("beer_tap_available") else "NO",
                o.get("photos_count") or "",
                "; ".join(o.get("bedroom_layout") or []),
                "YES" if o["is_dual_listed"] else "NO",
                o.get("echalupy_match_id") or "",
                o.get("echalupy_match_url") or "",
                o["url"]
            ])

    print("==================================================")
    print("      BOOKING WHOLE-OBJECT EXPORT SUMMARY         ")
    print("==================================================")
    print(f"Total Whole-Object Accommodations: {len(whole_objects)}")
    print(f"  • Cross-Listed on e-chalupy.cz:  {len([o for o in whole_objects if o['is_dual_listed']])}")
    print(f"  • Booking-Exclusive:             {len([o for o in whole_objects if not o['is_dual_listed']])}")
    print(f"  • With Sauna:                    {len([o for o in whole_objects if o.get('has_sauna')])}")
    print(f"  • With Pool:                     {len([o for o in whole_objects if o.get('has_pool')])}")
    print(f"  • With Hot Tub:                  {len([o for o in whole_objects if o.get('has_hot_tub_or_whirlpool')])}")
    print(f"  • Rated 9.0+ / 10:               {len([o for o in whole_objects if (o.get('review_score') or 0) >= 9.0])}")
    print("==================================================")
    print(f"Saved: {OUTPUT_JSON}")
    print(f"Saved: {OUTPUT_CSV}")

    # Copy to Google Drive
    if os.path.exists(GDRIVE_DIR):
        gdrive_dest = os.path.join(GDRIVE_DIR, OUTPUT_CSV)
        shutil.copy2(OUTPUT_CSV, gdrive_dest)
        print(f"✓ Uploaded CSV to Google Drive: {gdrive_dest}")


if __name__ == "__main__":
    main()
