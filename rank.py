import argparse
import json
import logging
import os
import re
import urllib.parse
from typing import Dict, Any, List, Optional
import ollama

DEFAULT_OBJECTS_JSON_PATH = "out.json"
DEFAULT_RATINGS_JSON_PATH = "ratings.json"
DEFAULT_MODEL = "llama3.2"
DEFAULT_PROMPT_VERSION = "v3"

# Fallback reference descriptions if reference cottages are missing from current dataset
FALLBACK_REFERENCE_CENTRUM_SLAPY = {
    "name": "Drevníky Resort Slapy",
    "capacity": "32",
    "rooms": "8",
    "icons": ["Wi-Fi", "Parkování", "Společenská místnost"],
    "equipment": ["Gril", "Koupelna", "Kuchyně", "Jídelní kout"],
    "price (per day per object)": 12000,
    "filtered_reasons": [],
    "text": "Velký rekreační resort s prostornou společenskou místností, venkovním posezením a grilem v klidné přírodě.",
    "ratings": ["Skvělé místo pro velkou partu přátel, dostatek místa i stolů."],
}

FALLBACK_REFERENCE_SIMIA = {
    "name": "Chalupa Simia",
    "capacity": "28",
    "rooms": "7",
    "icons": ["Wi-Fi", "Parkoviště", "Zahrada"],
    "equipment": ["Společenská místnost", "Gril", "Krb", "Plně vybavená kuchyň"],
    "price (per day per object)": 9500,
    "filtered_reasons": [],
    "text": "Krásná roubená chalupa s velkým obývacím pokojem s masivními stoly, ideální pro deskovky i víkendové setkání.",
    "ratings": ["Výborná chalupa pro společné akce s přáteli, rychlý internet."],
}

PROMPTS = {
    "v2": """
I want to organize an event for more than 25 of my friends. 
Anything with lower capacity would need to be really amazing for us to consider. In general capacity around 30 places is ideal because we have more flexibility.
We are looking for accommodation and we need something with a nice common room to play board games, therefore we need many chairs and tables. 
We prefer not to have more than 5 people in one room.
We also love PC games so we need a place where to put the desktops and ideally a good internet connection.
Places where the owner stays with us are probably not great because we have long nights and that may be uncomfortable for the owner. So places like guesthouses (penzion in Czech) are not great.
Also apartments are a no-go for us we need to rent the whole property.

The descriptions I will provide will be in Czech but always reply in English.

Make sure to take the visitor reviews with a grain of salt mainly when there is not enough of them.

We already visited the following 2 accommodations with my friends and we really liked it.

The structured description of the first accommodation follows:
{}

The structured description of the second accommodation follows:
{}

The structured description of the accommodation which should be rated follows:
{}

Your task is to rate the described object based on our requirements in JSON format containing the following fields (and only that):
* "rating": which is a number between 0 and 1 where 1 means very suitable object for the event.
* "description": max one sentence description for the object. Examples: "Fancy wooden cottage with sauna.", "Moldy dump."
* "owner_in_house": boolean, if the owner is present in the house which may be mentioned in the equipment or visitor reviews.
* "explanation": Explain the motivation for the rating.

{}
Make sure to reply with only the valid JSON and nothing more and only in English!
""",
    "v3": """
I want to organize an event for more than 25 of my friends. 
Anything with lower capacity would need to be really amazing for us to consider. In general capacity around 30 places is ideal because we have more flexibility.
We are looking for accommodation and we need something with a nice common room to play board games, therefore we need many chairs and tables. 
We prefer not to have more than 5 people in one room.
We also love PC games so we need a place where to put the desktops and ideally a good internet connection.
Places where the owner stays with us are probably not great because we have long nights and that may be uncomfortable for the owner. So places like guesthouses (penzion in Czech) are not great.
Also apartments are a no-go for us we need to rent the whole property.
We do not care about winter amenities because our event is happening in September.

The descriptions I will provide will be in Czech but always reply in English.

Make sure to take the visitor reviews with a grain of salt mainly when there is not enough of them.

We already visited the following 2 accommodations with my friends and we really liked it.

The structured description of the first accommodation follows:
{}

The structured description of the second accommodation follows:
{}

The structured description of the accommodation which should be rated follows:
{}

Your task is to rate the described object based on our requirements in JSON format containing the following fields (and only that):
* "rating": which is a number between 0 and 1 where 1 means very suitable object for the event.
* "description": max one sentence description for the object. Examples: "Fancy wooden cottage with sauna.", "Moldy dump."
* "owner_in_house": boolean, if the owner is present in the house which may be mentioned in the equipment or visitor reviews.
* "explanation": Explain the motivation for the rating.

{}
Make sure to reply with only the valid JSON and nothing more and only in English!
""",
}


def format_property(p: Dict[str, Any]) -> str:
    """Format property attributes and text into a structured prompt section."""
    raw_ratings = p.get("ratings", [])
    ratings_formatted = ["  * " + str(i).replace("\r\n", " ").replace("\n", "") for i in raw_ratings]
    
    desc = p.get("text", "")
    if "Kontakt na pronajímatele nebo provozovatele" in desc:
        desc = desc.split("Kontakt na pronajímatele nebo provozovatele")[0]
    if "kontakty  mapa" in desc:
        parts = desc.split("kontakty  mapa")
        if len(parts) > 1:
            desc = parts[1]
    desc = desc.replace("\r\n", " ").replace("\n", " ").strip()

    icons = p.get("icons", [])
    equipment = p.get("equipment", [])
    filtered_reasons = p.get("filtered_reasons", [])
    if isinstance(filtered_reasons, set):
        filtered_reasons = sorted(list(filtered_reasons))

    return f"""
Name: {p.get("name", "Unknown")}
Capacity: {p.get("capacity", "Unknown")}
Rooms: {p.get("rooms", "Unknown")}
Features: {', '.join(icons) if isinstance(icons, list) else str(icons)}
Equipment: {', '.join(equipment) if isinstance(equipment, list) else str(equipment)}
Price: {p.get("price (per day per object)", 0)}
Bad features: {', '.join(filtered_reasons)}
Description: {desc}
Visitor reviews: 
{chr(10).join(ratings_formatted)}
"""


def extract_json_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Safely extract and parse JSON object from LLM response text,
    stripping markdown code blocks and surrounding chatter.
    """
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    
    # Remove markdown code blocks if present
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()

    # Try direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Extract outermost JSON object { ... }
    json_match = re.search(r"\{[\s\S]*\}", cleaned)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return None


def load_objects(filepath: str = DEFAULT_OBJECTS_JSON_PATH) -> List[Dict[str, Any]]:
    """Load objects from JSON file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Objects file not found: {filepath}. Run process.py first.")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def find_by_name(name: str, properties: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Search properties by substring in name (case-insensitive)."""
    for p in properties:
        if name.lower() in p.get("name", "").lower():
            return p
    return None


def parse_args():
    parser = argparse.ArgumentParser(description="Rank scraped accommodations using Ollama LLMs.")
    parser.add_argument("--input", "-i", type=str, default=DEFAULT_OBJECTS_JSON_PATH, help=f"Input objects JSON (default: {DEFAULT_OBJECTS_JSON_PATH})")
    parser.add_argument("--ratings-file", "-r", type=str, default=DEFAULT_RATINGS_JSON_PATH, help=f"Ratings output JSON (default: {DEFAULT_RATINGS_JSON_PATH})")
    parser.add_argument("--model", "-m", type=str, default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--prompt-version", "-p", type=str, choices=list(PROMPTS.keys()), default=DEFAULT_PROMPT_VERSION, help=f"Prompt template version (default: {DEFAULT_PROMPT_VERSION})")
    parser.add_argument("--with-images", action="store_true", help="Include downloaded images in LLM prompt (for multimodal models like llava)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of unrated properties to process")
    parser.add_argument("--dry-run", action="store_true", help="Format prompts and print without calling Ollama")
    return parser.parse_args()


def main():
    args = parse_args()

    all_properties = load_objects(args.input)
    print(f"Loaded {len(all_properties)} total objects from {args.input}")

    properties = [p for p in all_properties if not p.get("filtered", False)]
    print(f"Candidate properties for ranking: {len(properties)}")

    # Locate reference properties or use defaults
    simia = find_by_name("chalupa simia", all_properties) or FALLBACK_REFERENCE_SIMIA
    centrum_slapy = find_by_name("drevníky resort slapy", all_properties) or FALLBACK_REFERENCE_CENTRUM_SLAPY

    ratings: Dict[str, Any] = {}
    if os.path.exists(args.ratings_file):
        try:
            with open(args.ratings_file, "r", encoding="utf-8") as f:
                ratings = json.load(f)
        except Exception as e:
            logging.warning(f"Could not load existing {args.ratings_file}: {e}. Starting fresh.")

    result_id = f"{args.model}_{args.prompt_version}"
    processed = 0

    for p in properties:
        prop_id = p.get("id", p.get("url", ""))
        name = p.get("name", "Unknown")
        url = p.get("url", "")
        print(f"\nEvaluating: {name} ({url})")

        present_ratings = ratings.get(prop_id, {})
        if result_id in present_ratings:
            print(f"Already rated with {result_id}, skipping.")
            continue

        prompt = PROMPTS[args.prompt_version].format(
            format_property(centrum_slapy),
            format_property(simia),
            format_property(p),
            "Do not forget to use attached images of the accommodation for the analysis.\n" if args.with_images else ""
        )

        images = []
        if args.with_images:
            for img_pair in p.get("images", []):
                if len(img_pair) >= 2:
                    img_url = img_pair[1]
                    img_filename = urllib.parse.quote(img_url, safe='')
                    img_path = os.path.abspath(os.path.join("imgs", img_filename))
                    if os.path.exists(img_path):
                        images.append(img_path)

        if args.dry_run:
            print("[DRY RUN] Prompt sample:")
            print(prompt[:400] + "...\n")
            processed += 1
            if args.limit and processed >= args.limit:
                break
            continue

        try:
            generate_kwargs: Dict[str, Any] = {
                "model": args.model,
                "prompt": prompt,
            }
            if images:
                generate_kwargs["images"] = images

            response = ollama.generate(**generate_kwargs)
            raw_response = response.get("response", "")
            rating_data = extract_json_response(raw_response)

            if rating_data:
                print(f"Rating result: {rating_data}")
                present_ratings[result_id] = rating_data
                ratings[prop_id] = present_ratings
                with open(args.ratings_file, "w", encoding="utf-8") as f:
                    json.dump(ratings, f, ensure_ascii=False, indent=2)
            else:
                print(f"Rating failed to produce valid JSON. Raw output: {raw_response[:200]}")
        except Exception as e:
            print(f"Ollama rating call failed: {e}")

        processed += 1
        print(f"Processed: {processed} unrated items (Total candidate count: {len(properties)})")

        if args.limit and processed >= args.limit:
            print(f"Reached processing limit of {args.limit}")
            break


if __name__ == '__main__':
    main()

