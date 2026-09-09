#!/usr/bin/env python3
"""
Pass 1: Text & Structured Feature Scoring for garage-trip.cz.
Evaluates all properties in properties_structured.json against the retreat rubric:
  1. Capacity & Bedroom Privacy (25 pts)
  2. Common Room & Table Gaming Space (25 pts)
  3. Hygiene / Toilet Ratio (15 pts)
  4. Wellness (Sauna, Koupací Sud, Hot Tub) (15 pts)
  5. Kitchen & Beer Tap (10 pts)
  6. Privacy & Exclusive Rental (10 pts)

Outputs rankings_text_pass1.json, highlights pros/cons, and selects the top 42 candidates.
"""

import argparse
import json
import os
import re
from typing import Dict, Any, List, Tuple


def calculate_garage_trip_score(prop: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate the garage-trip.cz score (0-100) and pros/cons based on structured data."""
    subscores = {}
    pros = []
    cons = []

    # -------------------------------------------------------------
    # 1. Capacity & Sleeping Comfort (max 25 pts)
    # -------------------------------------------------------------
    cap = prop.get("capacity_total") or 0
    beds_reg = prop.get("beds_regular") or cap
    beds_extra = prop.get("beds_extra") or 0
    rooms = prop.get("bedrooms_count") or 0

    cap_score = 0.0
    if 28 <= cap <= 36:
        cap_score += 15.0
        pros.append(f"Ideal capacity for 30 adults ({cap} guests)")
    elif 25 <= cap <= 27:
        cap_score += 12.0
        pros.append(f"Good capacity ({cap} guests)")
    elif 37 <= cap <= 42:
        cap_score += 12.0
        pros.append(f"Spacious capacity ({cap} guests)")
    elif 23 <= cap <= 24:
        cap_score += 7.0
        cons.append(f"Slightly tight capacity ({cap} guests)")
    elif 43 <= cap <= 55:
        cap_score += 7.0
        pros.append(f"Very large capacity ({cap} guests)")
    elif cap > 55:
        cap_score += 3.0
        cons.append(f"Oversized ({cap} guests, potentially expensive or sprawling)")
    else:  # < 23
        cap_score += 0.0
        cons.append(f"Capacity too low ({cap} guests)")

    # Fixed beds bonus / penalty
    if cap > 0 and beds_reg > 0:
        reg_ratio = beds_reg / cap
        if reg_ratio >= 0.85:
            cap_score += 5.0
            pros.append(f"High fixed bed ratio ({beds_reg} regular beds)")
        elif reg_ratio >= 0.70:
            cap_score += 3.0
        else:
            cap_score += 1.0
            cons.append(f"High extra bed reliance ({beds_extra} extra beds)")

    # Bedrooms count (privacy for adults)
    if rooms >= 10:
        cap_score += 5.0
        pros.append(f"Excellent room privacy ({rooms} bedrooms)")
    elif rooms >= 7:
        cap_score += 4.0
        pros.append(f"Good bedroom privacy ({rooms} bedrooms)")
    elif rooms >= 5:
        cap_score += 2.5
    elif rooms > 0:
        cap_score += 1.0
        cons.append(f"Few bedrooms ({rooms} bedrooms for {cap} guests)")

    subscores["capacity_and_beds"] = min(25.0, round(cap_score, 1))

    # -------------------------------------------------------------
    # 2. Common Room, Tables & Workspaces (max 25 pts)
    # -------------------------------------------------------------
    table_score = 0.0
    seats = prop.get("tables_seating_capacity")
    tables_note = prop.get("tables_and_workspace") or ""
    room_desc = prop.get("common_room_description") or ""
    tv = prop.get("projector_or_large_tv")

    combined_text = (tables_note + " " + room_desc).lower()

    if seats:
        if seats >= 28:
            table_score += 15.0
            pros.append(f"Great table seating for games/laptops ({seats} seats)")
        elif seats >= 22:
            table_score += 11.0
            pros.append(f"Good table seating ({seats} seats)")
        elif seats >= 16:
            table_score += 7.0
            cons.append(f"Limited table seating ({seats} seats for {cap} guests)")
        else:
            table_score += 3.0
            cons.append(f"Insufficient table seating ({seats} seats)")
    else:
        # Infer from description
        if any(w in combined_text for w in ["velké stoly", "masivní stoly", "30 židlí", "velká jídelna"]):
            table_score += 12.0
            pros.append("Large tables and seating highlighted in common room")
        elif any(w in combined_text for w in ["společenská místnost", "jídelna"]):
            table_score += 7.0
        else:
            table_score += 4.0

    # Quality indicators
    if any(w in combined_text for w in ["masivní", "dřevěné stoly", "variabilní", "velký stůl", "stoly"]):
        table_score += 5.0

    # Presentation / Screen
    if tv:
        table_score += 5.0
        pros.append("Projector / large TV available for gaming & presentations")

    subscores["common_room_and_tables"] = min(25.0, round(table_score, 1))

    # -------------------------------------------------------------
    # 3. Hygiene & Toilets Ratio (max 15 pts)
    # -------------------------------------------------------------
    wc_score = 0.0
    toilets = prop.get("toilets_count")
    bathrooms = prop.get("bathrooms_count")
    showers = prop.get("showers_count")

    if toilets is not None:
        if toilets >= 7:
            wc_score += 10.0
            pros.append(f"Generous toilet capacity ({toilets} WCs)")
        elif toilets >= 5:
            wc_score += 8.0
            pros.append(f"Sufficient toilets ({toilets} WCs)")
        elif toilets >= 3:
            wc_score += 5.0
        elif toilets == 2:
            wc_score += 2.0
            cons.append(f"Only 2 toilets for {cap} guests (morning bottleneck)")
        elif toilets == 1:
            wc_score += 0.0
            cons.append(f"Critical bottleneck: only 1 toilet for {cap} guests")
    else:
        wc_score += 4.0

    # Showers / Bathrooms
    effective_showers = showers or bathrooms or 0
    if effective_showers >= 6:
        wc_score += 5.0
        pros.append(f"Plenty of showers ({effective_showers} showers/bathrooms)")
    elif effective_showers >= 4:
        wc_score += 4.0
    elif effective_showers >= 2:
        wc_score += 2.5
    elif effective_showers == 1:
        wc_score += 1.0
        cons.append("Only 1 shower/bathroom")

    subscores["hygiene_and_toilets"] = min(15.0, round(wc_score, 1))

    # -------------------------------------------------------------
    # 4. Wellness Facilities (max 15 pts)
    # -------------------------------------------------------------
    wellness_score = 0.0
    has_sauna = prop.get("has_sauna")
    sauna_type = prop.get("sauna_type") or ""
    has_tub = prop.get("has_hot_tub_or_whirlpool")
    tub_notes = prop.get("hot_tub_notes") or ""
    has_pool = prop.get("has_pool")

    if has_sauna:
        wellness_score += 7.0
        s_desc = f"{sauna_type.capitalize()} sauna" if sauna_type and sauna_type != "none" else "Sauna"
        pros.append(f"{s_desc} available")
        if "finsk" in sauna_type.lower() or "finnish" in sauna_type.lower():
            wellness_score += 1.5

    if has_tub:
        wellness_score += 6.0
        if any(k in tub_notes.lower() for k in ["sud", "barrel", "koupací"]):
            wellness_score += 1.0
            pros.append(f"Outdoor bathing barrel / koupací sud ({tub_notes})")
        else:
            pros.append(f"Hot tub / whirlpool ({tub_notes or 'available'})")

    if has_pool:
        wellness_score += 2.0
        pros.append("Swimming pool available")

    subscores["wellness"] = min(15.0, round(wellness_score, 1))

    # -------------------------------------------------------------
    # 5. Kitchen & Beer Tap (max 10 pts)
    # -------------------------------------------------------------
    kitchen_score = 0.0
    beer_tap = prop.get("beer_tap_available")
    fridges = prop.get("fridges_count") or 1
    dishwashers = prop.get("dishwashers_count") or 1

    if beer_tap is True:
        kitchen_score += 5.0
        pros.append("Draft beer tap system (pípa) available")

    if dishwashers >= 2:
        kitchen_score += 3.0
        pros.append(f"{dishwashers} dishwashers (great for group cleanup)")
    elif dishwashers >= 1:
        kitchen_score += 1.5

    if fridges >= 3:
        kitchen_score += 2.0
        pros.append(f"{fridges} refrigerators for group food & beverages")
    elif fridges >= 2:
        kitchen_score += 1.5

    subscores["kitchen_and_beer"] = min(10.0, round(kitchen_score, 1))

    # -------------------------------------------------------------
    # 6. Privacy & Exclusivity (max 10 pts)
    # -------------------------------------------------------------
    privacy_score = 0.0
    exclusive = prop.get("exclusive_private_rental")
    owner_on_site = prop.get("owner_lives_on_site")

    if exclusive is True:
        privacy_score += 8.0
        pros.append("Exclusive whole-property rental (strictly private)")
    elif exclusive is False:
        privacy_score += 2.0
        cons.append("Potential shared spaces or partial rental")
    else:
        privacy_score += 5.0

    if owner_on_site is True:
        privacy_score -= 8.0
        cons.append("Owner lives on-site / sharing property")
    elif owner_on_site is False:
        privacy_score += 2.0
        pros.append("No owner living on-site")

    subscores["privacy_and_exclusivity"] = max(0.0, min(10.0, round(privacy_score, 1)))

    # Total score (0-100)
    total_score = round(sum(subscores.values()), 1)

    # Clean duplicates in pros/cons
    dedup_pros = []
    for p in pros:
        if p not in dedup_pros:
            dedup_pros.append(p)

    dedup_cons = []
    for c in cons:
        if c not in dedup_cons:
            dedup_cons.append(c)

    return {
        "score_total": total_score,
        "subscores": subscores,
        "pros": dedup_pros[:6],
        "cons": dedup_cons[:4],
    }


def main():
    parser = argparse.ArgumentParser(description="Pass 1: Score properties based on structured text data.")
    parser.add_argument("--input", "-i", default="properties_structured.json", help="Path to properties_structured.json")
    parser.add_argument("--output", "-o", default="rankings_text_pass1.json", help="Output rankings JSON file")
    parser.add_argument("--top", "-t", type=int, default=42, help="Number of top candidates to highlight (default: 42)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found!")
        return

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 72)
    print(f" 📊 Scoring {len(data)} Accommodations for garage-trip.cz (Pass 1)")
    print(f" 🎯 Output File: {args.output}")
    print("=" * 72)

    scored_properties = []
    for prop_id, prop in data.items():
        eval_result = calculate_garage_trip_score(prop)
        combined = {
            "property_id": prop_id,
            "name": prop.get("name", "Unknown"),
            "url": prop.get("url", ""),
            "source_file": prop.get("source_file", ""),
            "capacity_total": prop.get("capacity_total"),
            "beds_regular": prop.get("beds_regular"),
            "bedrooms_count": prop.get("bedrooms_count"),
            "toilets_count": prop.get("toilets_count"),
            "has_sauna": prop.get("has_sauna"),
            "sauna_type": prop.get("sauna_type"),
            "has_hot_tub_or_whirlpool": prop.get("has_hot_tub_or_whirlpool"),
            "beer_tap_available": prop.get("beer_tap_available"),
            "tables_seating_capacity": prop.get("tables_seating_capacity"),
            "price_weekend_czk": prop.get("price_weekend_czk"),
            "price_week_czk": prop.get("price_week_czk"),
            "score_total": eval_result["score_total"],
            "subscores": eval_result["subscores"],
            "pros": eval_result["pros"],
            "cons": eval_result["cons"],
        }
        scored_properties.append(combined)

    # Sort descending by total score
    scored_properties.sort(key=lambda x: x["score_total"], reverse=True)

    for rank, p in enumerate(scored_properties, 1):
        p["rank_pass1"] = rank

    # Save all scored properties
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(scored_properties, f, indent=2, ensure_ascii=False)

    print(f" ✅ Successfully scored {len(scored_properties)} properties!")
    print(f"\n 🏆 TOP {args.top} CANDIDATES FOR GARAGE-TRIP.CZ:")
    print("-" * 105)
    print(f"{'#':<3} | {'Score':<5} | {'Name':<32} | {'Cap':<4} | {'Beds':<5} | {'Rms':<3} | {'WC':<3} | {'Sauna':<5} | {'Tub':<5} | {'Beer':<4}")
    print("-" * 105)

    top_candidates = scored_properties[:args.top]
    for p in top_candidates:
        sauna_str = "Yes" if p.get("has_sauna") else "No"
        tub_str = "Yes" if p.get("has_hot_tub_or_whirlpool") else "No"
        beer_str = "Yes" if p.get("beer_tap_available") else "No"
        wc_str = str(p.get("toilets_count") or "-")
        cap_str = str(p.get("capacity_total") or "-")
        beds_str = str(p.get("beds_regular") or "-")
        rms_str = str(p.get("bedrooms_count") or "-")
        name = p["name"][:32]
        print(f"{p['rank_pass1']:<3} | {p['score_total']:<5.1f} | {name:<32} | {cap_str:<4} | {beds_str:<5} | {rms_str:<3} | {wc_str:<3} | {sauna_str:<5} | {tub_str:<5} | {beer_str:<4}")

    print("-" * 105)
    print(f"Top {args.top} saved into {args.output}")


if __name__ == "__main__":
    main()
