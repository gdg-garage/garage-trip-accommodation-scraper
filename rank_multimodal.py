#!/usr/bin/env python3
"""
Pass 2: Multimodal Accommodation Scoring for garage-trip.cz.
Combines:
  1. Pass 1 structured features & ranking
  2. Full property text description
  3. Key gallery photos (common room, tables, sauna, kitchen, bedrooms)
Uses Ollama (gemma4:e4b) with vision to inspect actual photos of tables, common room,
wellness facilities, and bed arrangements.
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from typing import Dict, Any, List, Optional
import ollama

DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_RANKINGS_PASS1 = "rankings_text_pass1.json"
DEFAULT_OUTPUT = "rankings_final_multimodal.json"
DEFAULT_IMAGES_ROOT = "images"
DEFAULT_MAX_IMAGES = 6

GARAGE_TRIP_EVAL_PROMPT = """You are the lead organizer and evaluator for 'garage-trip.cz', an annual retreat for 25-35 tech enthusiasts, developers, and adult gamers.
Our retreat requirements:
1. COMMON ROOM & TABLES (CRITICAL): We need a large main common room where 25-30 people can sit together comfortably. We need large, sturdy tables and plenty of chairs for laptop hacking, workshops, and multi-player board games.
2. EXCLUSIVE WHOLE-OBJECT PRIVACY: Strictly private. No other guests, no owner living on-site sharing spaces.
3. SLEEPING ARRANGEMENTS: Reasonable distribution across bedrooms (avoid 10-person overcrowded bunk dorms). Comfortable regular beds.
4. TOILETS & BATHROOMS: At least 4-6+ toilets and multiple showers to avoid bottlenecks for 25-35 adults.
5. SAUNA & WELLNESS: High-bonus feature (Finnish sauna, hot tub/barrel).
6. KITCHEN & BEER TAP: Capability to cook meals for 25-35 people and beer tap availability.

Carefully inspect:
- The structured metadata from Pass 1
- The cottage description
- The attached photos of the property (common room, tables, bedrooms, wellness, kitchen)

Return ONLY a valid JSON object matching this schema (no markdown fences, no explanatory text):
{
  "property_id": "<string>",
  "name": "<string>",
  "final_score": <float: 0.0 to 100.0>,
  "common_room_score": <float: 0.0 to 25.0: size of main room and gathering space>,
  "tables_score": <float: 0.0 to 25.0: size and count of tables for laptops & board games>,
  "sleeping_score": <float: 0.0 to 20.0: bedroom count, bed types, privacy, avoiding bunks>,
  "wellness_score": <float: 0.0 to 15.0: sauna, hot tub, pool>,
  "facilities_score": <float: 0.0 to 15.0: toilets ratio, kitchen, beer tap>,
  "image_reasoning": "<string: detailed observations from inspecting the photos: what tables/chairs are visible in the common room, room setups, sauna quality, and kitchen equipment>",
  "tables_confirmed_by_images": <boolean: do the photos confirm adequate large tables and seating?>,
  "pros": [<list of 3-5 concise key advantages for garage-trip>],
  "cons": [<list of 1-4 concise drawbacks or concerns>],
  "verdict": "<string: 2-3 sentence final recommendation for garage-trip organizers>"
}
"""


def select_key_photos_for_evaluation(images_dir: str, max_photos: int = DEFAULT_MAX_IMAGES) -> List[str]:
    """Select the most relevant gallery photos for garage-trip evaluation."""
    if not os.path.isdir(images_dir):
        return []

    all_files = sorted([
        f for f in os.listdir(images_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".webp", ".png"))
    ])
    if not all_files:
        return []

    priority_patterns = [
        re.compile(r"spolecensk|jideln|obyvak|stul|stoly|hala", re.I),
        re.compile(r"sauna|virivk|sud|bazen|wellness", re.I),
        re.compile(r"kuchyn|sporak|lednic|vycep|pipa", re.I),
        re.compile(r"pokoj|loznice|luzk|postel", re.I),
        re.compile(r"terasa|pergola|zahrada|venk", re.I),
    ]

    selected: List[str] = []
    seen = set()

    for pattern in priority_patterns:
        for f in all_files:
            if pattern.search(f) and f not in seen:
                seen.add(f)
                selected.append(os.path.abspath(os.path.join(images_dir, f)))
                if len(selected) >= max_photos:
                    return selected

    if len(selected) < max_photos and all_files:
        step = max(1, len(all_files) // (max_photos - len(selected) + 1))
        for i in range(0, len(all_files), step):
            f = all_files[i]
            if f not in seen:
                seen.add(f)
                selected.append(os.path.abspath(os.path.join(images_dir, f)))
                if len(selected) >= max_photos:
                    break

    return selected[:max_photos]


def evaluate_property_garage_trip(
    property_data: Dict[str, Any],
    html_file: Optional[str] = None,
    images_dir: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    max_photos: int = DEFAULT_MAX_IMAGES,
) -> Dict[str, Any]:
    property_id = str(property_data.get("property_id"))
    name = property_data.get("name", f"Property {property_id}")
    source_file = property_data.get("source_file", "")
    slug = source_file.replace(".html", "")

    if not images_dir:
        candidate_dir = os.path.join(DEFAULT_IMAGES_ROOT, slug)
        if os.path.isdir(candidate_dir):
            images_dir = candidate_dir
        else:
            for d in glob.glob(os.path.join(DEFAULT_IMAGES_ROOT, f"*{property_id}*")):
                if os.path.isdir(d):
                    images_dir = d
                    break

    selected_images = select_key_photos_for_evaluation(images_dir, max_photos=max_photos) if images_dir else []
    image_names = [os.path.basename(p) for p in selected_images]

    raw_desc = ""
    if html_file and os.path.isfile(html_file):
        from extract_features_llm import extract_text_sections_from_html
        with open(html_file, "r", encoding="utf-8", errors="ignore") as fh:
            raw_desc = extract_text_sections_from_html(fh.read())["text"][:10000]

    user_prompt = f"""=== ACCOMMODATION DATA ===
Property Name: {name} (ID: {property_id})
URL: {property_data.get('url')}

=== PASS 1 STRUCTURED FEATURES & PRELIMINARY SCORE ===
Preliminary Pass 1 Score: {property_data.get('score_total')}/100
Capacity: {property_data.get('capacity_total')} guests ({property_data.get('beds_regular')} regular beds, {property_data.get('bedrooms_count')} bedrooms)
Bathrooms/Toilets: {property_data.get('toilets_count')} toilets
Sauna: {property_data.get('has_sauna')} ({property_data.get('sauna_type', 'none')})
Hot tub: {property_data.get('has_hot_tub_or_whirlpool')}
Beer tap: {property_data.get('beer_tap_available')}
Tables seating: {property_data.get('tables_seating_capacity')}

=== DETAILED DESCRIPTION ===
{raw_desc if raw_desc else 'See structured specs above.'}

=== ATTACHED PHOTOS INSPECTION ===
Total photos in cottage gallery: {len(glob.glob(os.path.join(images_dir, '*.jpg'))) if images_dir else 0}
Selected key photos for inspection: {len(selected_images)}
Photo filenames: {image_names}

Evaluate this cottage for garage-trip.cz according to our requirements and the JSON schema.
Reason specifically about the tables, seating, bedrooms, and sauna visible in the photos."""

    generate_kwargs: Dict[str, Any] = {
        "model": model,
        "prompt": f"{GARAGE_TRIP_EVAL_PROMPT}\n\n{user_prompt}",
        "format": "json",
        "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 1800},
    }

    if selected_images:
        generate_kwargs["images"] = selected_images

    response = ollama.generate(**generate_kwargs)
    raw_json = response.response if hasattr(response, "response") else response.get("response", "{}")

    # Clean potential markdown wrapping
    cleaned_json = raw_json.strip()
    if cleaned_json.startswith("```"):
        cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
        cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

    eval_data = json.loads(cleaned_json, strict=False)

    eval_data["property_id"] = property_id
    eval_data["name"] = name
    eval_data["url"] = property_data.get("url")
    eval_data["source_file"] = source_file
    eval_data["pass1_score"] = property_data.get("score_total")
    eval_data["evaluated_images_count"] = len(selected_images)
    eval_data["model_used"] = model
    return eval_data


def main():
    parser = argparse.ArgumentParser(description="Pass 2: Score cottage for garage-trip.cz with multimodal image reasoning.")
    parser.add_argument("--rankings", "-r", default=DEFAULT_RANKINGS_PASS1, help=f"Pass 1 rankings JSON (default: {DEFAULT_RANKINGS_PASS1})")
    parser.add_argument("--top", "-n", type=int, default=42, help="Number of candidates to evaluate (default: 42)")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT, help=f"Output rankings JSON (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--html-dir", "-d", default="html", help="Directory of HTML files (default: 'html')")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--max-photos", "-p", type=int, default=DEFAULT_MAX_IMAGES, help=f"Max photos per property (default: {DEFAULT_MAX_IMAGES})")
    parser.add_argument("--force", "-f", action="store_true", help="Re-evaluate already rated cottages")
    args = parser.parse_args()

    if not os.path.isfile(args.rankings):
        print(f"Error: Rankings input file '{args.rankings}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(args.rankings, "r", encoding="utf-8") as fh:
        ranked_list = json.load(fh)

    candidates = ranked_list[:args.top]

    ratings: Dict[str, Any] = {}
    if os.path.isfile(args.output) and not args.force:
        try:
            with open(args.output, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
                if isinstance(existing, list):
                    ratings = {str(item.get("property_id")): item for item in existing}
                elif isinstance(existing, dict):
                    ratings = existing
        except Exception as e:
            print(f"Warning: could not load existing {args.output}: {e}")

    print("=" * 72)
    print(f" 🏆 Pass 2: garage-trip.cz Multimodal Scoring ({args.model})")
    print(f" 📂 Candidates to evaluate: {len(candidates)}")
    print(f" 💾 Output File:           {args.output}")
    print("=" * 72)

    for idx, prop in enumerate(candidates, 1):
        prop_id = str(prop.get("property_id"))
        name = prop.get("name", prop_id)
        if not args.force and prop_id in ratings:
            print(f"[{idx}/{len(candidates)}] ⏭️  [Cached] {name} (ID: {prop_id})")
            continue

        source_file = prop.get("source_file", f"{prop_id}.html")
        html_path = os.path.join(args.html_dir, source_file) if not os.path.isabs(source_file) else source_file

        print(f"\n[{idx}/{len(candidates)}] Evaluating: {name} (ID: {prop_id}, Pass1: {prop.get('score_total')})...", flush=True)
        t0 = time.time()
        try:
            result = evaluate_property_garage_trip(
                property_data=prop,
                html_file=html_path,
                model=args.model,
                max_photos=args.max_photos,
            )
            ratings[prop_id] = result
            dur = time.time() - t0

            print(f"✓ Final Score: {result.get('final_score')} (Tables: {result.get('tables_score')}, Room: {result.get('common_room_score')}, Wellness: {result.get('wellness_score')}) [{dur:.1f}s]")
            print(f"  Tables Confirmed: {result.get('tables_confirmed_by_images')}")
            print(f"  Verdict: {result.get('verdict')}")
            print(f"  Image Reasoning: {str(result.get('image_reasoning', ''))[:140]}...")

            # Save progress as list sorted by final_score descending
            sorted_ratings = sorted(ratings.values(), key=lambda x: x.get("final_score", 0), reverse=True)
            with open(args.output, "w", encoding="utf-8") as out_f:
                json.dump(sorted_ratings, out_f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"  ✗ Error evaluating {name}: {e}")

    print("\n" + "=" * 72)
    print(f" 🎉 Multimodal Scoring Complete. Total rated properties: {len(ratings)}")
    print("=" * 72)


if __name__ == "__main__":
    main()
