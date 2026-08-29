import argparse
import copy
import csv
import glob
import json
import logging
import os
import re
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple, Iterable

from bs4 import BeautifulSoup
from utils import numeric_stats

# Filter defaults
DEFAULT_MIN_BEDS = 22
DEFAULT_MAX_BEDS = 42
DEFAULT_MIN_ROOMS = 7
DEFAULT_MAX_RESTAURANT_DISTANCE = 1500
DEFAULT_MAX_PRICE = 15000

distance_extractor = re.compile(r"(\d*[.,]?\d+)\s*(min|m|km)")
price_extractor = re.compile(r"(\d+\.? ?\d+)\s?(?:,\-)?Kč")


def clean(s: Optional[str]) -> str:
    """Clean newlines, carriage returns, and excess whitespace."""
    if s is None:
        return ""
    return s.replace('\r', '').replace('\n', '').strip()


def parse_html_content(html_text: str, source_filename: str = "") -> Optional[Dict[str, Any]]:
    """Parse raw HTML string and extract structured accommodation details."""
    soup = BeautifulSoup(html_text, 'html.parser')
    prop = soup.find(class_="chata")
    if not prop:
        return None

    # URL / Canonical
    canonical_link = soup.find("link", rel="canonical")
    if canonical_link and canonical_link.get("href"):
        url = canonical_link.get("href")
    else:
        # Fallback based on filename
        base_name = os.path.basename(source_filename).replace(".html", "")
        parts = base_name.split("_", 1)
        if len(parts) == 2:
            url = f"https://www.e-chalupy.cz/{parts[0]}/{parts[1]}.php"
        else:
            url = f"https://www.e-chalupy.cz/{base_name}.php"

    # ID, Name, Locality
    cislo_elem = prop.find(id="cislo_o")
    prop_id = cislo_elem.text.strip() if cislo_elem else ""

    h1_elem = prop.find("h1")
    name = h1_elem.text.strip() if h1_elem else ""

    h2_elem = prop.find("h2")
    locality = h2_elem.text.strip() if h2_elem else ""

    # Capacity & Rooms
    kapacita_elem = prop.find(id="kapacita")
    capacity_text = clean(kapacita_elem.text) if kapacita_elem else ""
    capacity_match = re.search(r"(?:\d*\saž\s)?(\d+)\sosob(?:\s\|\s(\d+)?)?", capacity_text)
    capacity_val = capacity_match.group(1) if capacity_match else None
    rooms_val = capacity_match.group(2) if capacity_match else None

    # Icons & Equipment
    ikony_elem = prop.find(id="ikony")
    icons = [i.get("alt") for i in ikony_elem.find_all() if i.get("alt")] if ikony_elem else []
    equipment = [j.get("alt") for i in prop.find_all(class_="prehled") for j in i.find_all("img") if j.get("alt")]

    # Contacts
    contact_elem = prop.find(id="kontakty")
    contact_raw = clean(contact_elem.text) if contact_elem else ""
    contact_links = [i.get("href") for i in contact_elem.find_all("a") if i.get("href")] if contact_elem else []

    # Map link
    vetsi_mapa = prop.find(id="vetsi_mapa")
    map_link = vetsi_mapa.get("href") if vetsi_mapa else ""

    # Distances
    dest_elem = prop.find(id="dest")
    distances: List[Tuple[str, str]] = []
    if dest_elem:
        for tr in dest_elem.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 2:
                distances.append((clean(tds[0].text), clean(tds[1].text)))

    # Reviews & Numeric Ratings
    ratings = [i.text.strip() for i in prop.find_all(class_="recenze")]
    rating_match_pattern = r"Celkové hodnocení:\s+(\d+)%"
    numeric_ratings = []
    for r in ratings:
        m = re.search(rating_match_pattern, r, re.UNICODE)
        if m:
            numeric_ratings.append(m.group(1))

    kamdal_elem = prop.find(class_="kamdal")
    place = clean(kamdal_elem.text) if kamdal_elem else ""

    # Pricelist
    cenik_elem = prop.find(id="cenik")
    pricelist = [clean(i.text) for i in cenik_elem.find_all("td")] if cenik_elem else []

    # Images
    nahledy_elem = prop.find(id="nahledy")
    images: List[Tuple[str, str]] = []
    if nahledy_elem:
        for a in nahledy_elem.find_all("a"):
            href = a.get("href")
            if href:
                if not href.startswith("http"):
                    href = "https://www.e-chalupy.cz/" + href.lstrip("/")
                images.append((a.get("title") or "", href))

    gps_match = re.search(r"GPS .*: (\d+\.\d+)N, (\d+\.\d+)E", prop.text)

    data: Dict[str, Any] = {
        "url": url,
        "id": prop_id,
        "name": name,
        "locality": locality,
        "capacity": capacity_val,
        "rooms": rooms_val,
        "icons": icons,
        "contact_raw": contact_raw,
        "contact_links": contact_links,
        "map_link": map_link,
        "distances": distances,
        "equipment": equipment,
        "ratings": ratings,
        "numeric_ratings": numeric_ratings,
        "place": place,
        "pricelist": pricelist,
        "images": images,
        "text": prop.text,
    }

    if gps_match:
        data["GPS"] = {
            "N": gps_match.group(1),
            "E": gps_match.group(2),
        }

    return data


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


def add_homepage(properties: Iterable[Dict[str, Any]], counters: Dict[str, int]):
    """Extract homepage URL from contact links."""
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
    """Calculate review rating statistics."""
    for i in properties:
        stats = i.get("numeric_ratings", [])
        if not stats:
            continue
        stats_ints = [int(j) for j in stats]
        i["numeric_ratings"] = stats_ints
        i["rating_stats"] = numeric_stats(stats_ints)
        global_ratings.extend(stats_ints)
        counters["rating_present"] += 1


def add_distances(properties: Iterable[Dict[str, Any]], counters: Dict[str, int], distances: Dict[str, List[float]]):
    """Calculate and normalize distances to POIs."""
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


def extract_normalized_price(properties: Iterable[Dict[str, Any]], counters: Dict[str, int], prices: List[float]):
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


def is_equipment_present(wanted_equip: List[str], property_dict: Dict[str, Any]) -> bool:
    """Check if equipment keyword is present."""
    for equip in property_dict.get("equipment", []):
        for wanted in wanted_equip:
            if wanted in equip.lower():
                return True
    return False


def filter_out(reason: str, item: Dict[str, Any], counters: Dict[str, int], soft: bool = False):
    """Tag a property with a filter reason."""
    if soft:
        reason += "_soft"
    counters[f"filtered_{reason}"] += 1
    if "filtered_reasons" not in item:
        item["filtered_reasons"] = set()
    item["filtered_reasons"].add(reason)
    if not soft:
        item["filtered"] = True


def apply_heuristics_and_filtering(
    properties: List[Dict[str, Any]],
    counters: Dict[str, int],
    min_beds: int = DEFAULT_MIN_BEDS,
    max_beds: int = DEFAULT_MAX_BEDS,
    min_rooms: int = DEFAULT_MIN_ROOMS,
    max_restaurant_distance: int = DEFAULT_MAX_RESTAURANT_DISTANCE,
    max_price: int = DEFAULT_MAX_PRICE,
):
    """Enrich and filter property objects."""
    global_ratings: List[int] = []
    prices: List[float] = []
    distances: Dict[str, List[float]] = {"les": [], "restaurace": [], "obchod": []}

    add_homepage(properties, counters)
    ratings_stats(properties, counters, global_ratings)
    distances_to_map(properties)
    add_distances(properties, counters, distances)
    extract_normalized_price(properties, counters, prices)

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


def parse_all_html_files(html_dir: str) -> List[Dict[str, Any]]:
    """Parse all .html files found in html_dir."""
    html_files = sorted(glob.glob(os.path.join(html_dir, "*.html")))
    properties: List[Dict[str, Any]] = []
    print(f"Parsing {len(html_files)} local HTML files in '{html_dir}'...")

    for fpath in html_files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            data = parse_html_content(content, source_filename=fpath)
            if data:
                properties.append(data)
        except Exception as e:
            logging.warning(f"Failed to parse {fpath}: {e}")

    print(f"Successfully extracted {len(properties)} structured property records.")
    return properties


def store_results(
    properties: List[Dict[str, Any]],
    output_properties_json: Optional[str] = "properties.json",
    output_csv: Optional[str] = "out.csv",
    output_json: Optional[str] = "out.json",
):
    """Export processed properties to JSON and CSV files."""
    def serialize_sets(x):
        obj = copy.deepcopy(x)
        for k, v in obj.items():
            if isinstance(v, set):
                obj[k] = sorted(list(v))
        return obj

    serializable = [serialize_sets(p) for p in properties]

    if output_properties_json:
        with open(output_properties_json, "w", encoding="utf-8") as f:
            for item in serializable:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"Exported {len(serializable)} raw properties to {output_properties_json}")

    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        print(f"Exported JSON dataset to {output_json}")

    if output_csv:
        fieldnames = [
            "name", "locality", "capacity", "rooms", "price (per day per object)",
            "homepage", "url", "breakfast", "half-board", "rating_mean",
            "rating_median", "rating_samples", "les_distance_m",
            "restaurace_distance_m", "obchod_distance_m", "filtered", "filtered_reasons"
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
                if "filtered_reasons" in prop_copy and isinstance(prop_copy["filtered_reasons"], (set, list)):
                    prop_copy["filtered_reasons"] = ",".join(sorted(list(prop_copy["filtered_reasons"])))
                writer.writerow(prop_copy)
        print(f"Exported CSV table to {output_csv}")


def parse_args():
    parser = argparse.ArgumentParser(description="Step 4: Offline DOM parser and heuristic filter for downloaded HTML files.")
    parser.add_argument("--html-dir", "-d", type=str, default="html", help="Directory containing downloaded HTML files (default: html)")
    parser.add_argument("--output-properties", "-p", type=str, default="properties.json", help="Output raw properties JSON lines (default: properties.json)")
    parser.add_argument("--output-csv", "-c", type=str, default="out.csv", help="Output CSV dataset path (default: out.csv)")
    parser.add_argument("--output-json", "-j", type=str, default="out.json", help="Output candidates JSON path (default: out.json)")
    parser.add_argument("--min-beds", type=int, default=DEFAULT_MIN_BEDS, help=f"Min capacity beds (default: {DEFAULT_MIN_BEDS})")
    parser.add_argument("--max-beds", type=int, default=DEFAULT_MAX_BEDS, help=f"Max capacity beds (default: {DEFAULT_MAX_BEDS})")
    parser.add_argument("--min-rooms", type=int, default=DEFAULT_MIN_ROOMS, help=f"Min room count (default: {DEFAULT_MIN_ROOMS})")
    parser.add_argument("--max-price", type=int, default=DEFAULT_MAX_PRICE, help=f"Max daily price in CZK (default: {DEFAULT_MAX_PRICE})")
    parser.add_argument("--max-restaurant-dist", type=int, default=DEFAULT_MAX_RESTAURANT_DISTANCE, help=f"Max restaurant distance in meters (default: {DEFAULT_MAX_RESTAURANT_DISTANCE})")
    return parser.parse_args()


def main():
    args = parse_args()
    counters: Dict[str, int] = defaultdict(int)

    properties = parse_all_html_files(args.html_dir)
    if not properties:
        print(f"No properties found in '{args.html_dir}'. Run download_html.py first.")
        return

    apply_heuristics_and_filtering(
        properties,
        counters,
        min_beds=args.min_beds,
        max_beds=args.max_beds,
        min_rooms=args.min_rooms,
        max_restaurant_distance=args.max_restaurant_dist,
        max_price=args.max_price,
    )

    print(f"\nFiltered candidate count: {len([p for p in properties if not p.get('filtered', False)])}/{len(properties)}")
    store_results(
        properties,
        output_properties_json=args.output_properties,
        output_csv=args.output_csv,
        output_json=args.output_json,
    )


if __name__ == '__main__':
    main()
