import argparse
import copy
import csv
import gzip
import json
import os
import re
from collections import defaultdict
from typing import Iterable, Dict, Any, List, Optional

from utils import numeric_stats

# Default filter limits
DEFAULT_MIN_BEDS = 22
DEFAULT_MAX_BEDS = 42
DEFAULT_MIN_ROOMS = 7
DEFAULT_MAX_RESTAURANT_DISTANCE = 1500
DEFAULT_MAX_PRICE = 15000

# Regex patterns
distance_extractor = re.compile(r"(\d*[.,]?\d+)\s*(min|m|km)")
price_extractor = re.compile(r"(\d+\.? ?\d+)\s?(?:,\-)?Kč")


def load_data(filepath: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load scraped property data from a JSON or gzipped JSON file.
    If no filepath is given, tries 'properties.json.gz' then 'properties.json'.
    """
    if filepath is None:
        if os.path.exists("properties.json.gz"):
            filepath = "properties.json.gz"
        elif os.path.exists("properties.json"):
            filepath = "properties.json"
        else:
            raise FileNotFoundError(
                "Could not find 'properties.json.gz' or 'properties.json'. "
                "Run `python3 download.py` first."
            )

    properties: List[Dict[str, Any]] = []
    if filepath.endswith(".gz"):
        with gzip.open(filepath, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    properties.append(json.loads(line))
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content.startswith("["):
                properties = json.loads(content)
            else:
                for line in content.splitlines():
                    line = line.strip()
                    if line:
                        properties.append(json.loads(line))
    return properties


def add_homepage(properties: Iterable[Dict[str, Any]], counters: Dict[str, int]):
    """Extract homepage URL from contact links if uniquely identifiable."""
    for i in properties:
        i["contact_links"] = list(set(i.get("contact_links", [])) - {"#"})
        links = [l for l in i.get("contact_links", []) if "face" not in l]
        if len(links) == 1:
            i["homepage"] = links[0]
            counters["homepage_present"] += 1
        elif len(links) > 1:
            counters["too_many_links_for_homepage_detection"] += 1


def distances_to_map(properties: Iterable[Dict[str, Any]]):
    """Convert distance pairs list to a lowercase dictionary map."""
    for i in properties:
        i["distances_map"] = {d[0].lower(): d[1] for d in i.get("distances", []) if len(d) >= 2}


def ratings_stats(properties: Iterable[Dict[str, Any]], counters: Dict[str, int], global_ratings: List[int]):
    """Calculate per-property and global review rating statistics."""
    for i in properties:
        stats = i.get("numeric_ratings", [])
        if not stats:
            continue
        stats_ints = [int(j) for j in stats]
        i["numeric_ratings"] = stats_ints
        i["rating_stats"] = numeric_stats(stats_ints)
        global_ratings.extend(stats_ints)
        counters["rating_present"] += 1


def extract_normalized_distance(dist: str) -> float:
    """Extract and normalize distance string into meters."""
    if not dist:
        return -1
    found_dist = distance_extractor.search(dist)
    if not found_dist:
        return -1
    val_str, unit = found_dist.group(1), found_dist.group(2)
    val = float(val_str.replace(',', '.'))
    if unit == "m":
        return val
    if unit == "km":
        return val * 1000.0
    if unit == "min":
        walking_speed_kmh = 5.0
        walking_speed_m_per_min = walking_speed_kmh * 1000.0 / 60.0
        return round(val * walking_speed_m_per_min, 1)
    return -1


def add_distances(
    properties: Iterable[Dict[str, Any]],
    counters: Dict[str, int],
    distances: Dict[str, List[float]],
):
    """Normalize and record distances to forest (les), restaurant (restaurace), and shop (obchod)."""
    for i in properties:
        for place in distances.keys():
            poi_dist = i.get("distances_map", {}).get(place)
            if not poi_dist:
                counters[f"distance_to_{place}_missing"] += 1
                continue
            counters[f"{place}_distance_present"] += 1
            distance = extract_normalized_distance(poi_dist)
            if distance == -1:
                counters[f"distance_to_{place}_malformed"] += 1
                continue
            i[f"{place}_distance_m"] = distance
            distances[place].append(distance)


def extract_normalized_price(
    properties: Iterable[Dict[str, Any]],
    counters: Dict[str, int],
    prices: List[float],
):
    """Parse pricelist tables and compute normalized per-day object rental price."""
    for prop in properties:
        price_list = prop.get("pricelist", [])
        if not price_list:
            counters["pricelist_missing"] += 1
            continue

        price_header = price_list[0].lower()
        if "apartmán" in price_header:
            prop["apartman"] = True
            continue
        if "polop" in price_header:
            prop["half-board"] = True
            counters["half_board"] += 1
        if "snídaní" in price_header:
            prop["breakfast"] = True
            counters["breakfast"] += 1

        price = -1.0
        for price_candidate in price_list[1:]:
            cand_lower = price_candidate.lower()
            if not (cand_lower.startswith("let") or cand_lower.startswith("mimo")):
                continue
            if cand_lower.startswith("cen"):
                break
            price_search = price_extractor.search(price_candidate)
            if not price_search:
                counters["idiotic_price_format"] += 1
                continue
            raw_val = price_search.group(1).replace('.', '').replace(' ', '')
            try:
                price = float(raw_val)
            except ValueError:
                continue
            break

        if price == -1.0:
            counters["price_not_found"] += 1
            continue

        if "za týden" in price_header:
            price /= 7.0
        if "za osobu" in price_header:
            if not prop.get("capacity"):
                continue
            try:
                price *= int(prop.get("capacity"))
            except ValueError:
                continue
        if "pokoj" in price_header:
            if not prop.get("rooms"):
                continue
            try:
                price *= int(prop.get("rooms"))
            except ValueError:
                continue

        rounded_price = round(price)
        prop["price (per day per object)"] = rounded_price
        prices.append(rounded_price)


def enhance(
    properties: Iterable[Dict[str, Any]],
    counters: Dict[str, int],
    global_ratings: List[int],
    distances: Dict[str, List[float]],
    prices: List[float],
):
    """Run all data enrichment steps on properties."""
    add_homepage(properties, counters)
    ratings_stats(properties, counters, global_ratings)
    distances_to_map(properties)
    add_distances(properties, counters, distances)
    extract_normalized_price(properties, counters, prices)


def filter_out(reason: str, item: Dict[str, Any], counters: Dict[str, int], soft: bool = False):
    """Mark a property as filtered with a specific reason tag."""
    if soft:
        reason += "_soft"
    counters[f"filtered_{reason}"] += 1
    if "filtered_reasons" not in item:
        item["filtered_reasons"] = set()
    item["filtered_reasons"].add(reason)
    if not soft:
        item["filtered"] = True


def is_equipment_present(wanted_equip: List[str], property_dict: Dict[str, Any]) -> bool:
    """Check if any wanted keyword is in property equipment list."""
    for equip in property_dict.get("equipment", []):
        for wanted in wanted_equip:
            if wanted in equip.lower():
                return True
    return False


def filtering(
    properties: Iterable[Dict[str, Any]],
    counters: Dict[str, int],
    min_beds: int = DEFAULT_MIN_BEDS,
    max_beds: int = DEFAULT_MAX_BEDS,
    min_rooms: int = DEFAULT_MIN_ROOMS,
    max_restaurant_distance: int = DEFAULT_MAX_RESTAURANT_DISTANCE,
    max_price: int = DEFAULT_MAX_PRICE,
):
    """Apply hard and soft filtering criteria to properties."""
    for i in properties:
        gps = i.get("GPS")
        if gps and isinstance(gps, dict) and "E" in gps:
            counters["gps_present"] += 1
            try:
                if float(gps["E"]) > 19.0:
                    filter_out("too_much_east", i, counters)
            except (ValueError, TypeError):
                pass

        if i.get("apartman"):
            filter_out("apartman", i, counters)

        try:
            capacity = int(i.get("capacity", -1))
        except (ValueError, TypeError):
            capacity = -1

        if capacity == -1:
            filter_out("capacity_missing", i, counters)
        elif capacity < min_beds:
            filter_out(f"small_capacity_<{min_beds}", i, counters)
        elif capacity > max_beds:
            filter_out(f"too_big_>{max_beds}", i, counters)

        try:
            rooms = int(i.get("rooms", -1)) if i.get("rooms") else -1
        except (ValueError, TypeError):
            rooms = -1

        if rooms == -1:
            filter_out("missing_rooms", i, counters)
        elif rooms < min_rooms:
            filter_out(f"not_enough_rooms_<{min_rooms}", i, counters)

        restaurant_dist = i.get("restaurace_distance_m", -1)
        if restaurant_dist == -1:
            filter_out("restaurant_distance_invalid", i, counters, soft=True)
        elif restaurant_dist > max_restaurant_distance:
            filter_out(f"restaurant_distance_too_big_>{max_restaurant_distance}", i, counters, soft=True)

        if not is_equipment_present(["inter", "wi-fi", "wifi"], i):
            filter_out("no_internet", i, counters)
        if not is_equipment_present(["společenská místnost"], i):
            filter_out("no_shared_room", i, counters)
        if not is_equipment_present(["parko"], i):
            filter_out("no_parking", i, counters)
        if not is_equipment_present(["gril"], i):
            filter_out("no_grill", i, counters, soft=True)

        # Check normalized calculated price or fallback price
        price = i.get("price (per day per object)") or i.get("price")
        if price is not None:
            try:
                if int(price) > max_price:
                    filter_out("expensive", i, counters)
            except (ValueError, TypeError):
                pass

        url = i.get("url", "")
        parts = url.split('/')
        area = parts[3] if len(parts) > 3 else ""
        i["area"] = area
        if area in {"jeseniky", "slovensko_chaty"}:
            filter_out("blocklisted_area", i, counters)

    for i in properties:
        if i.get("filtered", False):
            counters["filtered"] += 1


def store(
    properties: List[Dict[str, Any]],
    output_csv: Optional[str] = "out.csv",
    output_json: Optional[str] = "out.json",
):
    """Save enriched and filtered property data to CSV and JSON files."""
    if output_csv:
        fieldnames = [
            "name",
            "locality",
            "capacity",
            "rooms",
            "price (per day per object)",
            "homepage",
            "url",
            "breakfast",
            "half-board",
            "rating_mean",
            "rating_median",
            "rating_samples",
            "les_distance_m",
            "restaurace_distance_m",
            "obchod_distance_m",
            "filtered"
        ]
        all_fieldnames = set()
        for prop in properties:
            all_fieldnames |= set(prop.keys())
        for fn in all_fieldnames:
            if fn not in fieldnames:
                fieldnames.append(fn)

        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for csv_prop in properties:
                prop_copy = copy.deepcopy(csv_prop)
                prop_copy.pop("text", None)
                rating = prop_copy.get("rating_stats")
                if rating:
                    prop_copy["rating_mean"] = rating.get("mean")
                    prop_copy["rating_median"] = rating.get("median")
                    prop_copy["rating_samples"] = rating.get("samples")
                if "filtered_reasons" in prop_copy and isinstance(prop_copy["filtered_reasons"], set):
                    prop_copy["filtered_reasons"] = ",".join(sorted(prop_copy["filtered_reasons"]))
                writer.writerow(prop_copy)
        print(f"Saved CSV output to {output_csv}")

    if output_json:
        def serialize_sets(x):
            obj = copy.deepcopy(x)
            for k, v in obj.items():
                if isinstance(v, set):
                    obj[k] = sorted(list(v))
            return obj

        serializable = [serialize_sets(p) for p in properties]
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        print(f"Saved JSON output to {output_json}")


def counter_stats(properties: List[Dict[str, Any]], counters: Dict[str, int]):
    """Print filter and enhancement statistics summary."""
    ln = len(properties)
    if ln == 0:
        print("No properties loaded.")
        return
    print("\n--- Processing Statistics ---")
    for name, count in sorted(counters.items()):
        print(f"{name:<45} {count:>5}/{ln:<5} ({count / ln * 100:>6.2f}%)")


def parse_args():
    parser = argparse.ArgumentParser(description="Process, enrich, and filter scraped accommodation data.")
    parser.add_argument("--input", "-i", type=str, default=None, help="Input properties JSON or JSON.GZ path")
    parser.add_argument("--output-csv", type=str, default="out.csv", help="Output CSV path (default: out.csv)")
    parser.add_argument("--output-json", type=str, default="out.json", help="Output JSON path (default: out.json)")
    parser.add_argument("--min-beds", type=int, default=DEFAULT_MIN_BEDS, help=f"Minimum beds (default: {DEFAULT_MIN_BEDS})")
    parser.add_argument("--max-beds", type=int, default=DEFAULT_MAX_BEDS, help=f"Maximum beds (default: {DEFAULT_MAX_BEDS})")
    parser.add_argument("--min-rooms", type=int, default=DEFAULT_MIN_ROOMS, help=f"Minimum rooms (default: {DEFAULT_MIN_ROOMS})")
    parser.add_argument("--max-restaurant-dist", type=int, default=DEFAULT_MAX_RESTAURANT_DISTANCE, help=f"Max restaurant distance in m (default: {DEFAULT_MAX_RESTAURANT_DISTANCE})")
    parser.add_argument("--max-price", type=int, default=DEFAULT_MAX_PRICE, help=f"Max daily price in CZK (default: {DEFAULT_MAX_PRICE})")
    parser.add_argument("--no-csv", action="store_true", help="Skip CSV export")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON export")
    return parser.parse_args()


def main():
    args = parse_args()

    counters: Dict[str, int] = defaultdict(int)
    global_ratings: List[int] = []
    prices: List[float] = []
    distances: Dict[str, List[float]] = {
        "les": [],
        "restaurace": [],
        "obchod": [],
    }

    properties = load_data(args.input)
    print(f"Loaded {len(properties)} properties")

    enhance(properties, counters, global_ratings, distances, prices)
    filtering(
        properties,
        counters,
        min_beds=args.min_beds,
        max_beds=args.max_beds,
        min_rooms=args.min_rooms,
        max_restaurant_distance=args.max_restaurant_dist,
        max_price=args.max_price,
    )

    print("\n--- Summary Metrics ---")
    if global_ratings:
        print(f"Global ratings stats: {numeric_stats(global_ratings)}")
    if prices:
        print(f"Prices stats: {numeric_stats(prices)}")
    for name, samples in distances.items():
        if samples:
            print(f"Distance to {name} stats: {numeric_stats(samples)}")

    counter_stats(properties, counters)

    store(
        properties,
        output_csv=None if args.no_csv else args.output_csv,
        output_json=None if args.no_json else args.output_json,
    )


if __name__ == '__main__':
    main()

