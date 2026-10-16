#!/usr/bin/env python3
"""
Pass 2: Multimodal Accommodation Scoring for Booking.com accommodations for garage-trip.cz.
Combines:
  1. Pass 1 structured features & ranking (from rankings_booking_text_pass1.json)
  2. Booking detail description (from booking_html/<slug>.html)
  3. Key gallery photos (from booking_images/<slug>/) prioritized by AI/alt scene captions
Uses local Ollama (gemma4:e4b) on Apple Silicon GPU to inspect actual photos of
tables, common rooms, wellness facilities, and bedrooms.
"""

import argparse
import csv
import glob
import json
import os
import re
import sys
import time
from typing import Dict, Any, List, Optional
import ollama
from bs4 import BeautifulSoup

DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_RANKINGS_PASS1 = "rankings_booking_text_pass1.json"
DEFAULT_OUTPUT_JSON = "rankings_booking_final_multimodal.json"
DEFAULT_OUTPUT_CSV = "rankings_booking_final_multimodal.csv"
DEFAULT_HTML_DIR = "booking_html"
DEFAULT_IMAGES_DIR = "booking_images"
DEFAULT_MAX_IMAGES = 4

GARAGE_TRIP_EVAL_PROMPT = """You are the lead organizer and evaluator for 'garage-trip.cz', an annual retreat for 25-35 tech enthusiasts, developers, and adult gamers.
Our retreat requirements:
1. COMMON ROOM & TABLES (CRITICAL): We need a large main common room where 25-30 people can sit together comfortably. We need large, sturdy tables and plenty of chairs for laptop hacking, workshops, and multi-player board games.
2. EXCLUSIVE WHOLE-OBJECT PRIVACY: Strictly private. No other guests, no owner living on-site sharing spaces.
3. SLEEPING ARRANGEMENTS: Reasonable distribution across bedrooms (avoid 10-person overcrowded bunk dorms). Comfortable regular beds.
4. TOILETS & BATHROOMS: Multiple toilets and showers to avoid bottlenecks for 25-35 adults.
5. SAUNA & WELLNESS: High-bonus feature (Finnish sauna, hot tub/barrel, pool).
6. KITCHEN & DINING: Capability to cook meals for 25-35 people.

Carefully inspect:
- The structured metadata from Pass 1
- The property description
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
  "facilities_score": <float: 0.0 to 15.0: toilets ratio, kitchen>,
  "image_reasoning": "<string: detailed observations from inspecting the photos: what tables/chairs are visible in the common room, room setups, sauna quality, and kitchen equipment>",
  "tables_confirmed_by_images": <boolean: do the photos confirm adequate large tables and seating?>,
  "pros": [<list of 3-5 concise key advantages for garage-trip>],
  "cons": [<list of 1-4 concise drawbacks or concerns>],
  "verdict": "<string: 2-3 sentence final recommendation for garage-trip organizers>"
}
"""


def select_booking_photos(images_dir: str, max_photos: int = DEFAULT_MAX_IMAGES) -> List[str]:
    """Select the most relevant gallery photos for garage-trip evaluation using captions and file lists."""
    if not os.path.isdir(images_dir):
        return []

    manifest_file = os.path.join(images_dir, "photos_manifest.json")
    selected: List[str] = []
    seen = set()

    # 1. Use photo manifest captions to prioritize key spaces
    if os.path.isfile(manifest_file):
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            caption_patterns = [
                re.compile(r"table|dining|living|seating|lounge|hall|common", re.I),
                re.compile(r"sauna|hot tub|whirlpool|spa|wellness|pool|jacuzzi", re.I),
                re.compile(r"kitchen|bar|counter|beer", re.I),
                re.compile(r"bedroom|bed|bunk", re.I),
                re.compile(r"patio|terrace|garden|outdoor", re.I),
            ]
            for pattern in caption_patterns:
                for item in manifest:
                    caption = item.get("caption", "")
                    photo_id = str(item.get("photo_id", ""))
                    ext = item.get("extension", "jpg")
                    fn = f"{photo_id}.{ext}"
                    fp = os.path.join(images_dir, fn)
                    if pattern.search(caption) and fn not in seen and os.path.isfile(fp):
                        seen.add(fn)
                        selected.append(os.path.abspath(fp))
                        if len(selected) >= max_photos:
                            return selected
        except Exception:
            pass

    # 2. Fallback to existing jpg files in directory
    all_files = sorted([
        f for f in os.listdir(images_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".webp", ".png"))
    ])
    for f in all_files:
        if f not in seen:
            seen.add(f)
            selected.append(os.path.abspath(os.path.join(images_dir, f)))
            if len(selected) >= max_photos:
                break

    return selected[:max_photos]


def extract_description_from_booking_html(html_path: str) -> str:
    """Extract clean property description text from Booking detail HTML."""
    if not os.path.isfile(html_path):
        return ""
    try:
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        desc_el = soup.find(attrs={"data-testid": "property-description"}) or soup.find("div", id="property_description_content")
        if desc_el:
            return desc_el.get_text(separator="\n", strip=True)
    except Exception:
        pass
    return ""


def evaluate_booking_property(
    property_data: Dict[str, Any],
    html_dir: str = DEFAULT_HTML_DIR,
    images_dir: str = DEFAULT_IMAGES_DIR,
    model: str = DEFAULT_MODEL,
    max_photos: int = DEFAULT_MAX_IMAGES,
    host: str = "http://localhost:11434"
) -> Dict[str, Any]:
    """Run multimodal inference with Ollama on a Booking property."""
    slug = property_data.get("slug") or str(property_data.get("property_id"))
    prop_id = str(property_data.get("property_id") or slug)
    name = property_data.get("name", slug)

    prop_images_dir = os.path.join(images_dir, slug)
    selected_images = select_booking_photos(prop_images_dir, max_photos=max_photos)
    image_names = [os.path.basename(p) for p in selected_images]

    html_file = os.path.join(html_dir, f"{slug}.html")
    raw_desc = extract_description_from_booking_html(html_file)

    user_prompt = f"""=== ACCOMMODATION DATA ===
Property Name: {name} (Slug: {slug})
URL: {property_data.get('url')}

=== PASS 1 STRUCTURED FEATURES & PRELIMINARY SCORE ===
Preliminary Pass 1 Score: {property_data.get('score_total')}/100
Capacity: {property_data.get('capacity_total')} guests ({property_data.get('beds_regular')} regular beds, {property_data.get('bedrooms_count')} bedrooms)
Bathrooms/Toilets: {property_data.get('toilets_count')} toilets, {property_data.get('bathrooms_count')} bathrooms
Sauna: {property_data.get('has_sauna')} ({property_data.get('sauna_type', 'none')})
Hot tub: {property_data.get('has_hot_tub_or_whirlpool')}
Beer tap: {property_data.get('beer_tap_available')}
Tables seating: {property_data.get('tables_seating_capacity')}

=== DETAILED DESCRIPTION ===
{raw_desc if raw_desc else 'See structured specs above.'}

=== ATTACHED PHOTOS INSPECTION ===
Total photos in cottage gallery: {len(glob.glob(os.path.join(prop_images_dir, '*.jpg')))}
Selected key photos for inspection: {len(selected_images)}
Photo filenames: {image_names}

Evaluate this cottage for garage-trip.cz according to our requirements and the JSON schema.
Reason specifically about the tables, seating, bedrooms, and sauna visible in the photos."""

    client = ollama.Client(host=host)
    generate_kwargs: Dict[str, Any] = {
        "model": model,
        "prompt": f"{GARAGE_TRIP_EVAL_PROMPT}\n\n{user_prompt}",
        "format": "json",
        "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 800},
    }

    if selected_images:
        generate_kwargs["images"] = selected_images

    response = client.generate(**generate_kwargs)
    raw_json = response.response if hasattr(response, "response") else response.get("response", "{}")

    # Clean markdown fences or surrounding noise
    cleaned_json = raw_json.strip()
    if "```" in cleaned_json:
        cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
        cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

    # Extract JSON object if necessary
    try:
        eval_data = json.loads(cleaned_json, strict=False)
    except Exception:
        m = re.search(r"\{.*\}", cleaned_json, re.DOTALL)
        if m:
            eval_data = json.loads(m.group(0), strict=False)
        else:
            raise ValueError(f"Could not parse JSON from model output: {raw_json[:200]}")

    eval_data["property_id"] = prop_id
    eval_data["slug"] = slug
    eval_data["name"] = name
    eval_data["url"] = property_data.get("url")
    eval_data["capacity_total"] = property_data.get("capacity_total")
    eval_data["bedrooms_count"] = property_data.get("bedrooms_count")
    eval_data["beds_regular"] = property_data.get("beds_regular")
    eval_data["pass1_score"] = property_data.get("score_total")
    eval_data["evaluated_images_count"] = len(selected_images)
    eval_data["model_used"] = model
    return eval_data


def save_rankings(ratings: Dict[str, Any], json_path: str, csv_path: str):
    """Save sorted rankings to both JSON and CSV files."""
    sorted_ratings = sorted(ratings.values(), key=lambda x: x.get("final_score", 0), reverse=True)
    for rank, p in enumerate(sorted_ratings, 1):
        p["rank"] = rank

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sorted_ratings, f, indent=2, ensure_ascii=False)

    fieldnames = [
        "rank", "final_score", "pass1_score", "name", "slug", "capacity_total",
        "bedrooms_count", "beds_regular", "tables_confirmed_by_images",
        "common_room_score", "tables_score", "sleeping_score", "wellness_score",
        "facilities_score", "evaluated_images_count", "url", "verdict",
        "pros", "cons", "image_reasoning"
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in sorted_ratings:
            row = dict(r)
            if isinstance(row.get("pros"), list):
                row["pros"] = "; ".join(row["pros"])
            if isinstance(row.get("cons"), list):
                row["cons"] = "; ".join(row["cons"])
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Pass 2: Multimodal Scoring for Booking.com accommodations.")
    parser.add_argument("--rankings", "-r", default=DEFAULT_RANKINGS_PASS1, help=f"Pass 1 rankings JSON (default: {DEFAULT_RANKINGS_PASS1})")
    parser.add_argument("--top", "-n", type=int, default=None, help="Number of top candidates to evaluate (default: all)")
    parser.add_argument("--output-json", "-o", default=DEFAULT_OUTPUT_JSON, help=f"Output rankings JSON (default: {DEFAULT_OUTPUT_JSON})")
    parser.add_argument("--output-csv", "-c", default=DEFAULT_OUTPUT_CSV, help=f"Output rankings CSV (default: {DEFAULT_OUTPUT_CSV})")
    parser.add_argument("--html-dir", "-d", default=DEFAULT_HTML_DIR, help=f"Directory of HTML files (default: {DEFAULT_HTML_DIR})")
    parser.add_argument("--images-dir", "-i", default=DEFAULT_IMAGES_DIR, help=f"Directory of photos (default: {DEFAULT_IMAGES_DIR})")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--max-photos", "-p", type=int, default=DEFAULT_MAX_IMAGES, help=f"Max photos per property (default: {DEFAULT_MAX_IMAGES})")
    parser.add_argument("--host", default="http://localhost:11434", help="Ollama host URL")
    parser.add_argument("--force", "-f", action="store_true", help="Re-evaluate already rated cottages")
    args = parser.parse_args()

    if not os.path.isfile(args.rankings):
        print(f"Error: Rankings input file '{args.rankings}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(args.rankings, "r", encoding="utf-8") as fh:
        ranked_list = json.load(fh)

    candidates = ranked_list[:args.top] if args.top else ranked_list

    ratings: Dict[str, Any] = {}
    if os.path.isfile(args.output_json) and not args.force:
        try:
            with open(args.output_json, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
                if isinstance(existing, list):
                    ratings = {str(item.get("slug") or item.get("property_id")): item for item in existing}
                elif isinstance(existing, dict):
                    ratings = existing
        except Exception as e:
            print(f"Warning: could not load existing {args.output_json}: {e}")

    print("=" * 76)
    print(f" 🏆 Pass 2: Booking Multimodal Accommodation Scoring ({args.model})")
    print(f" 📂 Total Candidates to evaluate: {len(candidates)}")
    print(f" 💾 Output JSON:                   {args.output_json}")
    print(f" 📊 Output CSV:                    {args.output_csv}")
    print(f" 🖼️ Images Root:                   {args.images_dir}")
    print("=" * 76)

    for idx, prop in enumerate(candidates, 1):
        slug = prop.get("slug") or str(prop.get("property_id"))
        name = prop.get("name", slug)

        if not args.force and slug in ratings:
            print(f"[{idx}/{len(candidates)}] ⏭️  [Cached] {name} ({slug})")
            continue

        print(f"\n[{idx}/{len(candidates)}] 🔍 Evaluating: {name} ({slug}, Pass 1 Score: {prop.get('score_total')})...", flush=True)
        t0 = time.time()
        try:
            result = evaluate_booking_property(
                property_data=prop,
                html_dir=args.html_dir,
                images_dir=args.images_dir,
                model=args.model,
                max_photos=args.max_photos,
                host=args.host,
            )
            ratings[slug] = result
            dur = time.time() - t0

            print(f"  ✓ Final Score: {result.get('final_score')} (Tables: {result.get('tables_score')}, Room: {result.get('common_room_score')}, Wellness: {result.get('wellness_score')}) [{dur:.1f}s]")
            print(f"  Tables Confirmed: {result.get('tables_confirmed_by_images')}")
            print(f"  Verdict: {result.get('verdict')}")
            print(f"  Reasoning: {str(result.get('image_reasoning', ''))[:140]}...")

            save_rankings(ratings, args.output_json, args.output_csv)

        except Exception as e:
            print(f"  ✗ Error evaluating {name}: {e}")

    print("\n" + "=" * 76)
    print(f" 🎉 Multimodal Scoring Complete. Total rated properties: {len(ratings)}")
    print(f" Output saved to {args.output_json} and {args.output_csv}")
    print("=" * 76)


if __name__ == "__main__":
    main()
