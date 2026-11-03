#!/usr/bin/env python3
"""
Fact Cross-Examination Framework for Garage Trip Accommodation Candidates.

Uses lightweight LLM models (e.g. Gemini Flash-Lite) to execute an adversarial
cross-examination between:
  1. An Inquisitor: Skeptical auditor challenging claimed numbers (chairs, taps, beds, dates, rooms).
  2. A Defender: Grounded in raw HTML listings, photo logs, and structured specs.
  3. An Adjudicator: Delivers verified facts, confidence ratings, and score adjustments.

Can be run individually per property, in batch, or prepared as prompts for subagents.
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from typing import Dict, List, Any, Optional

QUEUE_JSON = "queue_candidates_50plus.json"
ALL_JSON = "data/candidates_must_nice_all.json"
OUTPUT_DIR = "data/cross_examinations"
SUMMARY_FILE = "data/cross_examinations_summary.json"


def get_html_content(listing: str) -> str:
    """Retrieve raw HTML text for the given listing."""
    if listing.startswith("e-chalupy"):
        m = re.search(r"\d+", listing)
        if m:
            oid = m.group(0)
            matches = glob.glob(f"html/*-o{oid}.html") or glob.glob(f"html/*_{oid}.html") or glob.glob(f"html/*{oid}*.html")
            if matches:
                with open(matches[0], "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
    elif listing.startswith("Booking"):
        slug = listing.replace("Booking", "").strip()
        matches = glob.glob(f"booking_html/{slug}.html") or glob.glob(f"booking_html/*{slug}*.html")
        if matches:
            with open(matches[0], "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    return ""


def build_cross_examination_dossier(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Compile the factual claim sheet for an accommodation."""
    html_raw = get_html_content(candidate.get("Listing", ""))
    
    # Extract plain text snippet around capacity, seating, beer taps, rooms
    clean_text = re.sub(r"<script[^>]*>.*?</script>", " ", html_raw, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r"<style[^>]*>.*?</style>", " ", clean_text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r"<[^>]+>", " ", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    dossier = {
        "listing": candidate.get("Listing"),
        "name": candidate.get("Name"),
        "url": candidate.get("Url"),
        "price_7_nights_czk": candidate.get("Price_7_Nights_CZK"),
        "price_per_person_7n": candidate.get("Price_Per_Person_7N"),
        "rank": candidate.get("Rank"),
        "total_score": candidate.get("Total_Score"),
        "must_haves_met": candidate.get("All_Must_Haves_Met"),
        "claims": {
            "chairs_in_common_area": candidate.get("Seating_Chairs_Count") or candidate.get("Chairs_Est"),
            "secondary_room": candidate.get("Secondary_Room_Details"),
            "capacity_total": candidate.get("Capacity_Total"),
            "bedrooms_count": candidate.get("Rooms_Count"),
            "extra_annex": candidate.get("Annex_Details"),
            "september_week_available": candidate.get("MH_Sept_Week"),
            "sept_continuous_days": candidate.get("Sept_Max_Continuous_Days"),
            "sept_free_ranges": candidate.get("Sept_Free_Ranges"),
            "beer_tap_count": candidate.get("NTH_Beer_Tap_Count", 0),
            "beer_tap_details": candidate.get("NTH_Beer_Tap_Details"),
            "wellness_features": candidate.get("NTH_Wellness_Details"),
            "pool": candidate.get("NTH_Pool_Type"),
            "toilets_count": candidate.get("NTH_Toilets_Count"),
            "catering_pro_kitchen": candidate.get("NTH_Catering_Details"),
            "child_corner": candidate.get("NTH_Child_Corner_Details"),
            "child_playground": candidate.get("NTH_Child_Playground_Details")
        },
        "photos_summary": {
            "has_local_photos": candidate.get("Has_Local_Photos"),
            "photos_count": candidate.get("Photos_Count"),
            "photos_folder": candidate.get("Photos_Folder")
        },
        "user_sentiment": {
            "top_votes": candidate.get("Score_User_Top_Votes"),
            "notes_sentiment": candidate.get("User_Notes_Sentiment_Label"),
            "tivvit_note": candidate.get("Tivvit_Note"),
            "team_comment": candidate.get("Team_Comment")
        },
        "listing_text_excerpt": clean_text[:3500] if clean_text else "No local HTML text available."
    }
    return dossier


def generate_cross_examination_prompt(dossier: Dict[str, Any]) -> str:
    """Generate the full prompt for Flash-Lite cross-examination."""
    claims = dossier["claims"]
    return f"""You are the Grand Inquisitor and Adjudicator verifying accommodation facts for a 25-30 person technical retreat (Garage Trip 2026).
Your goal is to ruthlessly cross-examine optimistic claims, check photos and listing text for hidden gotchas, and determine VERIFIED ground truth.

ACCOMMODATION DOSSIER:
- Name: {dossier['name']} ({dossier['listing']})
- Price (7 nights in Sept): {dossier['price_7_nights_czk']} CZK ({dossier['price_per_person_7n']} CZK/person)
- Claimed Capacity: {claims['capacity_total']} guests
- Claimed Bedrooms: {claims['bedrooms_count']} rooms (Annex/extra: {claims['extra_annex']})
- Claimed Dining/Common Seating: {claims['chairs_in_common_area']} chairs (Secondary room: {claims['secondary_room']})
- September Availability: {claims['september_week_available']} (Max continuous free: {claims['sept_continuous_days']} days, Ranges: {claims['sept_free_ranges']})
- Beer Tap: {claims['beer_tap_count']} taps (Benchmark: Nový Svět has 4 taps) - Details: {claims['beer_tap_details']}
- Wellness / Pool: {claims['wellness_features']} | Pool: {claims['pool']}
- Toilets: {claims['toilets_count']} WC
- Team Notes: Tivvit: "{dossier['user_sentiment']['tivvit_note']}" | Team: "{dossier['user_sentiment']['team_comment']}"

RAW LISTING TEXT EXCERPT:
\"\"\"{dossier['listing_text_excerpt']}\"\"\"

CROSS-EXAMINATION PROTOCOL:
Conduct a 3-round cross-examination:

ROUND 1: THE COMMON SEATING & WORKSPACE CHALLENGE
- Inquisitor Challenge: Challenge whether the claimed {claims['chairs_in_common_area']} seats are actually together in ONE main common room where 16+ people can dine and work, or if they are split between separate kitchens/apartments/outdoor patio.
- Defender Response: Cites specific listing text or room layouts.
- Adjudicator Verdict: Verified seat count in main room, whether must-have of 16+ seats (or secondary dance/office room) is truly met.

ROUND 2: BEDROOM PRIVACY & SEPTEMBER SLOT INTEGRITY
- Inquisitor Challenge: Challenge the {claims['bedrooms_count']} bedrooms and {claims['capacity_total']} capacity. Are there 7 separate real bedrooms or are pull-out couches in living rooms counted as bedrooms? Is the September slot genuinely a full 7-day uninterrupted week?
- Defender Response: Explains room distribution and availability integrity.
- Adjudicator Verdict: Verified bedroom count, confirmed September availability.

ROUND 3: AMENITIES BENCHMARK vs NOVÝ SVĚT (4 TAPS, WELLNESS, NO-VETO)
- Inquisitor Challenge: Compare the beer tap setup ({claims['beer_tap_count']} taps vs Nový Svět's 4 taps) and wellness. Is it a real draft bar with cooling, or just a portable tap on demand?
- Defender Response: Cites equipment details.
- Adjudicator Verdict: Verified tap count, verified wellness features.

OUTPUT FORMAT:
Return ONLY a valid JSON object matching this schema:
{{
  "property_name": "{dossier['name']}",
  "listing": "{dossier['listing']}",
  "confidence_score_0_to_100": <int: confidence in listing specs>,
  "must_haves_verified": {{
    "no_veto": <bool>,
    "september_week_confirmed": <bool>,
    "capacity_24_plus_confirmed": <bool>,
    "verified_capacity": <int>,
    "min_7_rooms_or_annex_confirmed": <bool>,
    "verified_rooms_count": <int>,
    "seating_16_plus_confirmed": <bool>,
    "verified_chairs_in_main_hall": <int>,
    "has_secondary_work_room": <bool>,
    "secondary_room_type": <string or null>
  }},
  "nice_to_haves_verified": {{
    "verified_beer_taps": <int>,
    "tap_system_type": <string: "commercial draft bar" | "portable cooling" | "none">,
    "verified_toilets_count": <int>,
    "has_pool": <bool>,
    "has_sauna": <bool>,
    "has_hot_tub": <bool>,
    "has_catering_or_pro_kitchen": <bool>
  }},
  "discrepancies": [<list of strings highlighting where claims differed from verified reality>],
  "dialogue": [
    {{"round": 1, "topic": "Seating & Common Room", "inquisitor": "...", "defender": "...", "verdict": "..."}},
    {{"round": 2, "topic": "Bedrooms & September Week", "inquisitor": "...", "defender": "...", "verdict": "..."}},
    {{"round": 3, "topic": "Amenities vs Nový Svět", "inquisitor": "...", "defender": "...", "verdict": "..."}}
  ],
  "final_adjudication": <string: summary 2-3 sentences evaluating fitness for Garage Trip retreat>
}}
"""


def save_cross_examination_result(result: Dict[str, Any]):
    """Save an adjudicated cross-examination."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    slug = re.sub(r"[^\w-]", "_", result.get("listing", "unknown")).lower()
    path = os.path.join(OUTPUT_DIR, f"{slug}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved cross-examination result to {path}")
    update_summary()


def update_summary():
    """Aggregate all completed cross-examinations into a single summary index."""
    files = glob.glob(os.path.join(OUTPUT_DIR, "*.json"))
    summary = []
    for f in sorted(files):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                summary.append({
                    "listing": data.get("listing"),
                    "name": data.get("property_name"),
                    "confidence_score": data.get("confidence_score_0_to_100"),
                    "must_haves_verified": data.get("must_haves_verified", {}),
                    "verified_chairs": data.get("must_haves_verified", {}).get("verified_chairs_in_main_hall"),
                    "verified_taps": data.get("nice_to_haves_verified", {}).get("verified_beer_taps"),
                    "discrepancies_count": len(data.get("discrepancies", [])),
                    "discrepancies": data.get("discrepancies", []),
                    "final_adjudication": data.get("final_adjudication")
                })
        except Exception as e:
            print(f"Error reading {f}: {e}")

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"📋 Updated summary manifest ({len(summary)} properties) at {SUMMARY_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Fact Cross-Examination Framework")
    parser.add_argument("--property", "-p", help="Specific listing ID or slug (e.g. 'e-chalupy 13716')")
    parser.add_argument("--top-n", "-n", type=int, default=15, help="Number of top candidates to examine (default: 15)")
    parser.add_argument("--export-prompts", action="store_true", help="Export ready-to-run prompts to data/cross_exam_prompts.json")
    parser.add_argument("--dry-run", action="store_true", help="Print sample prompt without executing model")
    args = parser.parse_args()

    if not os.path.exists(QUEUE_JSON):
        print(f"Error: {QUEUE_JSON} not found. Run extract_must_and_nice_haves.py first.")
        sys.exit(1)

    with open(QUEUE_JSON, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    if args.property:
        selected = [c for c in candidates if args.property.lower() in c.get("Listing", "").lower() or args.property.lower() in c.get("Name", "").lower()]
        if not selected:
            print(f"No candidate matching '{args.property}' found.")
            sys.exit(1)
    else:
        # Select top N eligible candidates
        eligible = [c for c in candidates if c.get("All_Must_Haves_Met")]
        selected = (eligible if eligible else candidates)[:args.top_n]

    print(f"🔍 Prepared {len(selected)} candidate properties for Fact Cross-Examination.")

    if args.export_prompts or args.dry_run:
        prompts = {}
        for c in selected:
            dossier = build_cross_examination_dossier(c)
            prompt = generate_cross_examination_prompt(dossier)
            prompts[c.get("Listing")] = {
                "name": c.get("Name"),
                "listing": c.get("Listing"),
                "prompt": prompt
            }
        
        out_prompts = "data/cross_exam_prompts.json"
        with open(out_prompts, "w", encoding="utf-8") as f:
            json.dump(prompts, f, indent=2, ensure_ascii=False)
        print(f"📝 Exported {len(prompts)} cross-examination prompts to {out_prompts}")

        if args.dry_run and selected:
            sample_l = selected[0].get("Listing")
            print("\n" + "=" * 60)
            print(f"SAMPLE PROMPT FOR {selected[0].get('Name')} ({sample_l}):")
            print("=" * 60)
            print(prompts[sample_l]["prompt"][:1800] + "\n... [truncated for preview]")
        return


if __name__ == "__main__":
    main()
