#!/usr/bin/env python3
"""
Pass 2: Multimodal Accommodation Scoring for garage-trip.cz.
Combines:
  1. Pass 1 structured features (beds, toilets, saunas, tables)
  2. Full property text description
  3. Key gallery photos (common room, tables, sauna, bedrooms)
Instructs Ollama to reason about the images (confirming table capacity, seating, room comfort,
and wellness facilities) and produce a detailed evaluation tailored to garage-trip.cz.
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

DEFAULT_MODEL = "gemma2"
DEFAULT_STRUCTURED_JSON = "properties_structured.json"
DEFAULT_RATINGS_OUTPUT = "ratings_garage_trip.json"
DEFAULT_IMAGES_ROOT = "images"
DEFAULT_MAX_IMAGES = 8


GARAGE_TRIP_EVAL_PROMPT = """You are the lead organizer and evaluator for 'garage-trip.cz', an annual retreat for 25-30 tech enthusiasts, developers, and makers.
Our retreat requirements:
1. EXCLUSIVE WHOLE-OBJECT RENTAL: Strictly private. No other guests, no owner living on-site or sharing common spaces.
2. COMMON ROOM & TABLES (MOST CRITICAL): We need a large main common room where all 25-30 people can gather together comfortably. We need large, sturdy tables and plenty of chairs for laptop hacking, workshops, and multi-player board games.
3. SLEEPING ARRANGEMENTS: Reasonable distribution across bedrooms (avoid 10-person overcrowded bunk dorms). Comfortable regular beds.
4. TOILETS & BATHROOMS: At least 3-6 toilets and multiple showers to avoid morning bottlenecks for 25+ adults.
5. SAUNA & WELLNESS: High-bonus feature (Finnish sauna, wood-fired hot tub/barrel, swimming pool).
6. KITCHEN: Capability to cook meals for 25-30 people (multiple fridges, ovens, dishwashers).

Carefully analyze:
- The structured metadata from Pass 1
- The cottage description
- The attached photos of the property (common room, tables, bedrooms, sauna, kitchen)

Return ONLY a valid JSON object matching this schema (no markdown formatting, no comments):
{
  "property_id": "<string>",
  "name": "<string>",
  "overall_score": <float: 0.00 to 1.00>,
  "common_room_score": <float: 0.00 to 1.00: size of main room and gathering space>,
  "tables_and_workspace_score": <float: 0.00 to 1.00: size and count of tables for laptops & board games>,
  "sleeping_comfort_score": <float: 0.00 to 1.00: bedroom count, bed types, privacy>,
  "toilets_ratio_score": <float: 0.00 to 1.00: WC and shower capacity for 25-30 people>,
  "wellness_score": <float: 0.00 to 1.00: sauna, hot tub, pool, relaxation facilities>,
  "image_reasoning": "<string: detailed observations from inspecting the photos: what tables/chairs are visible in the common room, room setups, sauna quality, and kitchen equipment>",
  "tables_confirmed_by_images": <boolean: do the photos confirm adequate large tables and seating?>,
  "owner_on_site_risk": <boolean: is there any indication or risk of owner living on the property?>,
  "pros": [<list of 3-5 concise key advantages for garage-trip>],
  "cons": [<list of 1-4 concise drawbacks or concerns>],
  "verdict": "<string: 2-3 sentence final recommendation for garage-trip organizers>"
}
"""


def select_key_photos_for_evaluation(images_dir: str, max_photos: int = DEFAULT_MAX_IMAGES) -> List[str]:
    """
    Select the most relevant gallery photos for garage-trip evaluation:
    prioritizes common room, tables, sauna, kitchen, and bedrooms.
    """
    if not os.path.isdir(images_dir):
        return []

    all_files = sorted([
        f for f in os.listdir(images_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".webp", ".png"))
    ])
    if not all_files:
        return []

    # Priority categories by filename keywords
    priority_patterns = [
        re.compile(r"spolecensk|jideln|obyvak|stul|stoly|hala", re.I),  # Common room / tables
        re.compile(r"sauna|virivk|sud|bazen|wellness", re.I),           # Wellness
        re.compile(r"kuchyn|sporak|lednic", re.I),                      # Kitchen
        re.compile(r"pokoj|loznice|luzk|postel", re.I),                 # Bedrooms
        re.compile(r"terasa|pergola|zahrada|venk", re.I),               # Outdoor
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

    # Fill remaining slots with evenly spaced photos across gallery
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
    property_id: str,
    structured_data: Dict[str, Any],
    html_file: Optional[str] = None,
    images_dir: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    max_photos: int = DEFAULT_MAX_IMAGES,
) -> Dict[str, Any]:
    """Run Pass 2 evaluation combining structured facts, description, and photos."""
    name = structured_data.get("name", f"Property {property_id}")
    slug = structured_data.get("slug") or structured_data.get("source_file", "").replace(".html", "")

    # Locate images directory if not explicitly provided
    if not images_dir:
        candidate_dir = os.path.join(DEFAULT_IMAGES_ROOT, slug)
        if os.path.isdir(candidate_dir):
            images_dir = candidate_dir
        else:
            # Search in images/ for directory matching property_id
            for d in glob.glob(os.path.join(DEFAULT_IMAGES_ROOT, f"*{property_id}*")):
                if os.path.isdir(d):
                    images_dir = d
                    break

    selected_images = select_key_photos_for_evaluation(images_dir, max_photos=max_photos) if images_dir else []
    image_names = [os.path.basename(p) for p in selected_images]

    # Description from HTML if available
    raw_desc = ""
    if html_file and os.path.isfile(html_file):
        from extract_features_llm import extract_text_sections_from_html
        with open(html_file, "r", encoding="utf-8", errors="ignore") as fh:
            raw_desc = extract_text_sections_from_html(fh.read())["text"][:3500]

    user_prompt = f"""=== ACCOMMODATION DATA ===
Property Name: {name} (ID: {property_id})
URL: {structured_data.get('url')}

=== PASS 1 STRUCTURED FEATURES ===
{json.dumps(structured_data, indent=2, ensure_ascii=False)}

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
        "options": {"temperature": 0.2, "num_predict": 1500},
    }

    # If images exist, pass them if the model supports images
    if selected_images:
        generate_kwargs["images"] = selected_images

    try:
        response = ollama.generate(**generate_kwargs)
        raw_json = response.get("response", "{}")
        eval_data = json.loads(raw_json)
    except Exception as e:
        # Fallback if model doesn't support direct image bytes: run text-guided analysis of photo list
        if "images" in generate_kwargs:
            print(f" (Model did not accept images parameter directly, falling back to text photo analysis: {e})", end="", flush=True)
            del generate_kwargs["images"]
            response = ollama.generate(**generate_kwargs)
            raw_json = response.get("response", "{}")
            eval_data = json.loads(raw_json)
        else:
            raise e

    eval_data["property_id"] = str(property_id)
    eval_data["name"] = name
    eval_data["evaluated_images_count"] = len(selected_images)
    eval_data["model_used"] = model
    return eval_data


def main():
    parser = argparse.ArgumentParser(description="Pass 2: Score cottage for garage-trip.cz with multimodal image reasoning.")
    parser.add_argument("property", nargs="?", default=None, help="Property ID or slug to score (e.g. '358' or 'o3649')")
    parser.add_argument("--structured-input", "-s", default=DEFAULT_STRUCTURED_JSON, help=f"Input Pass 1 JSON (default: {DEFAULT_STRUCTURED_JSON})")
    parser.add_argument("--output", "-o", default=DEFAULT_RATINGS_OUTPUT, help=f"Output ratings JSON (default: {DEFAULT_RATINGS_OUTPUT})")
    parser.add_argument("--html-dir", "-d", default="html", help="Directory of HTML files (default: 'html')")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--max-photos", "-p", type=int, default=DEFAULT_MAX_IMAGES, help=f"Max photos to attach per property (default: {DEFAULT_MAX_IMAGES})")
    parser.add_argument("--force", "-f", action="store_true", help="Re-evaluate already rated cottages")
    args = parser.parse_args()

    if not os.path.isfile(args.structured_input):
        print(f"Error: Structured input file '{args.structured_input}' not found. Run extract_features_llm.py first!", file=sys.stderr)
        sys.exit(1)

    with open(args.structured_input, "r", encoding="utf-8") as fh:
        all_structured = json.load(fh)

    # Load existing ratings if present
    ratings: Dict[str, Any] = {}
    if os.path.isfile(args.output) and not args.force:
        try:
            with open(args.output, "r", encoding="utf-8") as fh:
                ratings = json.load(fh)
        except Exception as e:
            print(f"Warning: could not load existing {args.output}: {e}")

    # Determine targets
    if args.property:
        clean_id = args.property.lstrip("o")
        targets = {k: v for k, v in all_structured.items() if k == clean_id or args.property in str(v.get("source_file", ""))}
        if not targets:
            print(f"Error: Property '{args.property}' not found in {args.structured_input}", file=sys.stderr)
            sys.exit(1)
    else:
        targets = all_structured

    print("=" * 68)
    print(f" 🏆 Pass 2: garage-trip.cz Multimodal Scoring ({args.model})")
    print(f" 📂 Properties to evaluate: {len(targets)}")
    print(f" 💾 Output File:           {args.output}")
    print("=" * 68)

    for prop_id, s_data in targets.items():
        if not args.force and prop_id in ratings:
            print(f"⏭️  [Cached] {s_data.get('name')} (ID: {prop_id})")
            continue

        name = s_data.get("name", prop_id)
        source_file = s_data.get("source_file", f"{prop_id}.html")
        html_path = os.path.join(args.html_dir, source_file) if not os.path.isabs(source_file) else source_file

        print(f"\nEvaluating: {name} (ID: {prop_id})...", flush=True)
        t0 = time.time()
        try:
            result = evaluate_property_garage_trip(
                property_id=prop_id,
                structured_data=s_data,
                html_file=html_path,
                model=args.model,
                max_photos=args.max_photos,
            )
            ratings[prop_id] = result
            dur = time.time() - t0

            print(f"✓ Score: {result.get('overall_score'):.2f} (Common Room: {result.get('common_room_score')}, Tables: {result.get('tables_and_workspace_score')}, Sauna: {result.get('wellness_score')}) [{dur:.1f}s]")
            print(f"  Verdict: {result.get('verdict')}")
            print(f"  Image Reasoning: {result.get('image_reasoning')[:140]}...")

            with open(args.output, "w", encoding="utf-8") as out_f:
                json.dump(ratings, out_f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"  ✗ Error evaluating {name}: {e}")

    print("\n" + "=" * 68)
    print(f" 🎉 Scoring Complete. Total rated properties: {len(ratings)}")
    print("=" * 68)


if __name__ == "__main__":
    main()
