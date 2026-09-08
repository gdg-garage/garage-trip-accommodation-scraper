#!/usr/bin/env python3
"""
Pass 1: Extract structured, normalized property features using Ollama (Gemma 2).
Extracts capacity, beds, bedroom distribution, toilets, showers, sauna, common room,
tables, and pricing from raw accommodation descriptions.
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import ollama

DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_INPUT_DIR = "html"
DEFAULT_OUTPUT = "properties_structured.json"

EXTRACTION_SYSTEM_PROMPT = """You are a precise data extractor analyzing Czech cottage accommodations for a 25-35 person group retreat (garage-trip.cz).
Analyze the accommodation details and return ONLY a valid JSON object matching the requested schema.
Keep all string values concise (1-2 sentences max). Do not output markdown fences or explanatory text.

JSON Schema to follow:
{
  "capacity_total": <integer: max total guests>,
  "beds_regular": <integer: regular fixed beds>,
  "beds_extra": <integer: přistýlky / sofa beds>,
  "bedrooms_count": <integer: number of separate bedrooms>,
  "bedroom_layout": [<list of short strings, e.g. "4x 2-bed", "2x 4-bed">],
  "bunk_beds_count": <integer or null: count of bunk beds / palandy>,
  "toilets_count": <integer: number of separate WC/toilets>,
  "bathrooms_count": <integer: number of bathrooms>,
  "showers_count": <integer: number of showers>,
  "en_suite_bathrooms": <boolean or null: are bathrooms attached to individual bedrooms?>,
  "has_sauna": <boolean>,
  "sauna_type": <string: "finnish", "infra", "barrel", "steam", "none">,
  "sauna_capacity": <integer or null: max persons in sauna>,
  "has_hot_tub_or_whirlpool": <boolean: true if hot tub, outdoor bathing barrel / koupací sud, whirlpool or vířivka is present>,
  "hot_tub_notes": <string: brief note on hot tub / koupací sud capacity or type>,
  "has_pool": <boolean>,
  "pool_notes": <string or null: indoor/outdoor, heated, etc.>,
  "common_room_description": <string: brief note on main living room / společenská místnost size and feel>,
  "common_room_size_m2": <integer or null: size of common room in square meters>,
  "tables_and_workspace": <string: brief note on tables and seating capacity for laptops & board games>,
  "tables_seating_capacity": <integer or null: total number of chairs/seats around tables in common room>,
  "projector_or_large_tv": <boolean or null: TV, projector, or presentation screen available>,
  "kitchen_details": <string: brief note on stoves, fridges, dishwashers for large groups>,
  "fridges_count": <integer or null: number of refrigerators>,
  "dishwashers_count": <integer or null: number of dishwashers>,
  "beer_tap_available": <boolean or null: draft beer cooling & tap system / pípa / výčepní zařízení>,
  "grill_and_outdoor": <string or null: outdoor grill, fireplace, terrace equipment>,
  "wifi_available": <boolean>,
  "parking_spaces": <integer or null: number of parking spots>,
  "exclusive_private_rental": <boolean: is the whole house rented exclusively without other guests?>,
  "owner_lives_on_site": <boolean or null: does the owner live in the house or on the property?>,
  "price_weekend_czk": <integer or null: total weekend price for whole house in CZK>,
  "price_week_czk": <integer or null: total weekly price in CZK>,
  "security_deposit_czk": <integer or null: refundable deposit / kauce in CZK>,
  "price_notes": <string: brief note on pricing, electricity, heating fees>
}
"""



def parse_echalupy_metadata(soup: BeautifulSoup) -> Dict[str, Any]:
    """Deterministically extract verified overview metadata from dedicated e-chalupy HTML elements."""
    meta: Dict[str, Any] = {}

    # 1. Total capacity (e.g. div.item.persons -> "až 32 Počet osob")
    persons_tag = soup.find(class_=re.compile(r"\bpersons\b"))
    if persons_tag:
        m = re.search(r"(\d+)", persons_tag.text)
        if m:
            meta["capacity_persons"] = int(m.group(1))

    # 2. Beds badge (e.g. div.item.icon-beds -> "30 lůžek + 4 přistýlky" or "32 lůžek")
    beds_tag = soup.find(class_=re.compile(r"\bicon-beds\b"))
    if beds_tag:
        beds_txt = beds_tag.text.strip()
        meta["beds_text"] = beds_txt
        m_reg = re.search(r"(\d+)\s*lůž", beds_txt)
        if m_reg:
            meta["beds_regular"] = int(m_reg.group(1))
        m_extra = re.search(r"\+\s*(\d+)\s*přistýl", beds_txt)
        if m_extra:
            meta["beds_extra"] = int(m_extra.group(1))
        elif meta.get("beds_regular") and meta.get("capacity_persons"):
            meta["beds_extra"] = max(0, meta["capacity_persons"] - meta["beds_regular"])

    # 3. Bedrooms badge (e.g. div.item.icon-rooms or div.item.rooms -> "14 ložnic")
    rooms_tag = soup.find(class_=re.compile(r"\bicon-rooms\b")) or soup.find(class_=re.compile(r"\bitem rooms\b"))
    if rooms_tag:
        meta["rooms_text"] = rooms_tag.text.strip()
        m_rooms = re.search(r"(\d+)", rooms_tag.text)
        if m_rooms:
            meta["bedrooms_count"] = int(m_rooms.group(1))

    # 4. Amenity icon badges (e.g. div.tags -> "finská sauna", "koupací sud", "vířivka")
    tags_container = soup.find("div", class_="tags")
    if tags_container:
        tag_items = [t.text.strip() for t in tags_container.find_all(class_="item") if t.text.strip()]
        meta["amenity_badges"] = tag_items

    return meta


def extract_text_sections_from_html(html_text: str, filename: str = "") -> Dict[str, Any]:
    """Extract clean property title, URL, ID, verified metadata, and text sections from raw HTML."""
    soup = BeautifulSoup(html_text, "html.parser")

    # Name and ID
    h1 = soup.find("h1")
    raw_title = h1.text.strip() if h1 else ""
    id_match = re.search(r"\((\d+)\)", raw_title) or re.search(r"-o(\d+)", filename)
    prop_id = id_match.group(1) if id_match else ""
    name = re.sub(r"\s*\(\d+\)\s*$", "", raw_title).strip() or "Ubytování"

    # Canonical URL
    canon = soup.find("link", rel="canonical")
    canonical_url = canon["href"] if canon and canon.get("href") else f"https://www.e-chalupy.cz/{filename.replace('.html', '')}"

    # First, decompose other properties / recommendation cards and non-content chrome
    for unwanted in soup.find_all(class_=re.compile(r"c-property|similar|recommended|footer|header|nav|menu|cookie|search", re.I)):
        unwanted.decompose()

    # Extract dedicated overview metadata
    official_meta = parse_echalupy_metadata(soup)

    # Extract all relevant text blocks under headings (Popis, Vybavení, Pokoje, Ceník, etc.)
    # Exclude external / irrelevant sections
    ignored_headings = [
        "další objekty", "podobné", "okolí", "výlety", "poloha",
        "hodnocení", "volné termíny", "sport a zábava", "kontakt"
    ]
    sec_map: Dict[str, str] = {}

    for h in soup.find_all(["h2", "h3"]):
        h_title = h.text.strip()
        if any(k in h_title.lower() for k in ignored_headings):
            continue
        body_parts = []
        sibling = h.find_next_sibling()
        while sibling and sibling.name not in ["h1", "h2", "h3", "footer"]:
            t = sibling.text.strip()
            if t and len(t) > 3:
                body_parts.append(t)
            sibling = sibling.find_next_sibling()
        if body_parts:
            content = "\n".join(body_parts)
            if h_title not in sec_map or len(content) > len(sec_map[h_title]):
                sec_map[h_title] = content

    full_text = "\n\n".join(f"### {k}\n{v}" for k, v in sec_map.items())
    if not full_text:
        main = soup.find("main") or soup.body
        full_text = main.text if main else ""

    # Keep up to 14,000 characters to capture the complete property specs
    return {
        "id": prop_id,
        "name": name,
        "url": canonical_url,
        "filename": os.path.basename(filename),
        "official_meta": official_meta,
        "text": full_text[:14000],
    }


FEATURE_SCHEMA = {
    "type": "object",
    "properties": {
        "capacity_total": {"type": ["integer", "null"]},
        "beds_regular": {"type": ["integer", "null"]},
        "beds_extra": {"type": ["integer", "null"]},
        "bedrooms_count": {"type": ["integer", "null"]},
        "bedroom_layout": {"type": "array", "items": {"type": "string"}},
        "bunk_beds_count": {"type": ["integer", "null"]},
        "toilets_count": {"type": ["integer", "null"]},
        "bathrooms_count": {"type": ["integer", "null"]},
        "showers_count": {"type": ["integer", "null"]},
        "en_suite_bathrooms": {"type": ["boolean", "null"]},
        "has_sauna": {"type": ["boolean", "null"]},
        "sauna_type": {"type": ["string", "null"]},
        "sauna_capacity": {"type": ["integer", "null"]},
        "has_hot_tub_or_whirlpool": {"type": ["boolean", "null"]},
        "hot_tub_notes": {"type": ["string", "null"]},
        "has_pool": {"type": ["boolean", "null"]},
        "pool_notes": {"type": ["string", "null"]},
        "common_room_description": {"type": ["string", "null"]},
        "common_room_size_m2": {"type": ["integer", "null"]},
        "tables_and_workspace": {"type": ["string", "null"]},
        "tables_seating_capacity": {"type": ["integer", "null"]},
        "projector_or_large_tv": {"type": ["boolean", "null"]},
        "kitchen_details": {"type": ["string", "null"]},
        "fridges_count": {"type": ["integer", "null"]},
        "dishwashers_count": {"type": ["integer", "null"]},
        "beer_tap_available": {"type": ["boolean", "null"]},
        "grill_and_outdoor": {"type": ["string", "null"]},
        "wifi_available": {"type": ["boolean", "null"]},
        "parking_spaces": {"type": ["integer", "null"]},
        "exclusive_private_rental": {"type": ["boolean", "null"]},
        "owner_lives_on_site": {"type": ["boolean", "null"]},
        "price_weekend_czk": {"type": ["integer", "null"]},
        "price_week_czk": {"type": ["integer", "null"]},
        "security_deposit_czk": {"type": ["integer", "null"]},
        "price_notes": {"type": ["string", "null"]}
    }
}
FEATURE_SCHEMA["required"] = list(FEATURE_SCHEMA["properties"].keys())


def extract_features_with_llm(property_info: Dict[str, Any], model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """Call Ollama to extract structured fields in JSON format with ground-truth verification."""
    official = property_info.get("official_meta", {})
    cap_str = f"{official.get('capacity_persons')} persons" if official.get('capacity_persons') else "Not specified in header"
    beds_str = official.get('beds_text') or "Not specified in header"
    rooms_str = f"{official.get('bedrooms_count')} bedrooms" if official.get('bedrooms_count') else "Not specified in header"
    badges_str = ", ".join(official.get('amenity_badges', [])) or "None"

    user_prompt = f"""Cottage: {property_info['name']} (ID: {property_info['id']})
URL: {property_info['url']}
Verified Header Parameters:
- Total Capacity: {cap_str}
- Beds: {beds_str}
- Bedrooms: {rooms_str}
- Amenity Badges: {badges_str}

Details & Description:
{property_info['text']}

Extract all features according to the JSON schema."""

    try:
        response = ollama.generate(
            model=model,
            prompt=f"{EXTRACTION_SYSTEM_PROMPT}\n\n{user_prompt}",
            format=FEATURE_SCHEMA,
            options={"temperature": 0.1, "num_predict": 2048}
        )
        raw_json = response.get("response", "{}")
        data = json.loads(raw_json)
    except Exception as e:
        # Fallback to general format="json" if model doesn't support schema enforcement
        response = ollama.generate(
            model=model,
            prompt=f"{EXTRACTION_SYSTEM_PROMPT}\n\n{user_prompt}",
            format="json",
            options={"temperature": 0.1, "num_predict": 2048}
        )
        raw_json = response.get("response", "{}")
        cleaned = re.sub(r"^```json\s*", "", raw_json.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)

    # Apply deterministic ground-truth overrides from verified HTML fields
    if official.get("capacity_persons") is not None:
        data["capacity_total"] = official["capacity_persons"]
    if official.get("beds_regular") is not None:
        data["beds_regular"] = official["beds_regular"]
    if official.get("beds_extra") is not None:
        data["beds_extra"] = official["beds_extra"]
    elif data.get("beds_extra") is None and data.get("capacity_total") and data.get("beds_regular"):
        data["beds_extra"] = max(0, data["capacity_total"] - data["beds_regular"])
    if official.get("bedrooms_count") is not None:
        data["bedrooms_count"] = official["bedrooms_count"]

    # Verify amenity badges (e.g. koupací sud, vířivka, sauna, bazén)
    badges_lower = [b.lower() for b in official.get("amenity_badges", [])]
    if any("sauna" in b for b in badges_lower):
        data["has_sauna"] = True
        if not data.get("sauna_type") or data.get("sauna_type") == "none":
            if any("finská" in b for b in badges_lower):
                data["sauna_type"] = "finnish"
            elif any("infra" in b for b in badges_lower):
                data["sauna_type"] = "infra"
    if any("sud" in b or "vířivk" in b for b in badges_lower):
        data["has_hot_tub_or_whirlpool"] = True
        if not data.get("hot_tub_notes"):
            matched = [b for b in official.get("amenity_badges", []) if any(k in b.lower() for k in ["sud", "vířivk"])]
            data["hot_tub_notes"] = ", ".join(matched)
    if any("bazén" in b for b in badges_lower):
        data["has_pool"] = True

    # Attach core identifiers
    data["property_id"] = property_info["id"]
    data["name"] = property_info["name"]
    data["url"] = property_info["url"]
    data["source_file"] = property_info["filename"]
    return data


def main():
    parser = argparse.ArgumentParser(description="Pass 1: Extract structured property features with Ollama.")
    parser.add_argument("property", nargs="?", default=None, help="Specific property HTML file or ID (e.g. 'o358' or 'html/benecko-...html')")
    parser.add_argument("--html-dir", "-d", default=DEFAULT_INPUT_DIR, help=f"Directory of HTML files (default: {DEFAULT_INPUT_DIR})")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT, help=f"Output structured JSON file (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--limit", "-l", type=int, default=None, help="Limit number of properties to process")
    parser.add_argument("--force", "-f", action="store_true", help="Re-extract already cached properties")
    args = parser.parse_args()

    # Load existing output if present
    cached_data: Dict[str, Any] = {}
    if os.path.exists(args.output):
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    cached_data = loaded
                elif isinstance(loaded, list):
                    for item in loaded:
                        cached_data[item.get("property_id") or item.get("url")] = item
        except Exception as e:
            print(f"Warning: could not read {args.output}: {e}")

    # Determine files to process
    if args.property:
        from extract_property_images import resolve_html_file
        try:
            target_file = resolve_html_file(args.property, args.html_dir)
            files = [target_file]
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        files = sorted(glob.glob(os.path.join(args.html_dir, "*.html")))

    if args.limit:
        files = files[:args.limit]

    print("=" * 68)
    print(f" 🧠 Pass 1: Structured Feature Extraction with Ollama ({args.model})")
    print(f" 📂 HTML Files:   {len(files)} properties")
    print(f" 💾 Output File:  {args.output}")
    print("=" * 68)

    processed = 0
    start_time = time.time()

    for idx, f in enumerate(files, 1):
        with open(f, "r", encoding="utf-8", errors="ignore") as fh:
            prop_info = extract_text_sections_from_html(fh.read(), filename=f)

        key = prop_info["id"] or prop_info["url"]
        if not args.force and key in cached_data and "beds_regular" in cached_data[key]:
            print(f"[{idx:03d}/{len(files):03d}] ⏭️  [Cached] {prop_info['name']} (ID: {prop_info['id']})")
            continue

        print(f"[{idx:03d}/{len(files):03d}] 🔍 Extracting: {prop_info['name']} (ID: {prop_info['id']})...", end="", flush=True)
        t0 = time.time()
        try:
            extracted = extract_features_with_llm(prop_info, model=args.model)
            cached_data[key] = extracted
            processed += 1
            dur = time.time() - t0
            print(f" done in {dur:.1f}s | Beds: {extracted.get('capacity_total')} ({extracted.get('bedrooms_count')}r) | WCs: {extracted.get('toilets_count')} | Sauna: {extracted.get('has_sauna')} | Tub/Sud: {extracted.get('has_hot_tub_or_whirlpool')} | Beer Tap: {extracted.get('beer_tap_available')}")
            
            # Save incrementally after each property
            with open(args.output, "w", encoding="utf-8") as out_f:
                json.dump(cached_data, out_f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f" ERROR: {e}")

    elapsed = time.time() - start_time
    print("=" * 68)
    print(f" 🎉 Completed in {elapsed:.1f}s. Extracted: {processed}, Total in {args.output}: {len(cached_data)}")
    print("=" * 68)


if __name__ == "__main__":
    main()
