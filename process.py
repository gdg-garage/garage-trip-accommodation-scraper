import copy
import csv
import gzip
import json
import re
from collections import defaultdict
from typing import Iterable, Dict, Any, List

from utils import numeric_stats

# global stats
counters = defaultdict(int)
ratings = []
prices = []
distances = {
    "les": [],
    "restaurace": [],
    "obchod": [],
}

# limits
MIN_BEDS = 22
MAX_BEDS = 42
MIN_ROOMS = 7
MAX_RESTAURANT_DISTANCE = 1500
MAX_PRICE = 15000

# regex
distance_extractor = re.compile(r"(\d*[.,]?\d+)\s*(min|m|km)")
price_extractor = re.compile(r"(\d+\.? ?\d+)\s?(?:,\-)?Kč")


def load_data() -> Iterable[Dict[str, Any]]:
    with gzip.open("properties.json.gz") as f:
        for line in f:
            yield json.loads(line)


def add_homepage(properties: Iterable[Dict[str, Any]]):
    """
    extract homepage link
    """
    for i in properties:
        i["contact_links"] = list(set(i.get("contact_links", [])) - {"#"})
        links = [l for l in i.get("contact_links", []) if "face" not in l]
        if len(links) == 1:
            i["homepage"] = links[0]
            counters["homepage_present"] += 1
        elif len(links) > 1:
            counters["too_many_links_for_homepage_detection"] += 1


def counter_stats(properties: Iterable[Dict[str, Any]]):
    ln = len(list(properties))
    for name, count in counters.items():
        print(f"{name} {count}/{ln}: {count / ln * 100:.2f}%")


def distances_to_map(properties: Iterable[Dict[str, Any]]):
    for i in properties:
        i["distances_map"] = {i[0].lower(): i[1] for i in i.get("distances", [])}


def ratings_stats(properties: Iterable[Dict[str, Any]]):
    global ratings
    for i in properties:
        stats = i.get("numeric_ratings", [])
        if not stats:
            continue
        stats = [int(j) for j in stats]
        i["numeric_ratings"] = stats
        i["rating_stats"] = numeric_stats(stats)
        ratings += stats
        counters["rating_present"] += 1


def add_distances(properties: Iterable[Dict[str, Any]]):
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


def extract_normalized_price(properties: Iterable[Dict[str, Any]]):
    global prices
    for prop in properties:
        price_list = prop.get("pricelist", [])
        if not price_list:
            counters["pricelist_missing"] += 1
            continue
        # todo: this may be massively improved by iterating over the sections
        price_header = price_list[0]
        if "apartmán" in price_header:
            prop["apartman"] = True
            continue
        if "polop" in price_header:
            prop["half-board"] = True
            counters["half_board"] += 1
        if "snídaní" in price_header:
            prop["breakfast"] = True
            counters["breakfast"] += 1
        price = -1
        for price_candidate in price_list[1:]:
            if not (price_candidate.lower().startswith("let") or price_candidate.lower().startswith("mimo")):
                continue
            # There is no price in the first section (continue may be ok)
            if price_candidate.lower().startswith("cen"):
                break
            price_search = price_extractor.search(price_candidate)
            if not price_search:
                counters["idiotic_price_format"] += 1
                continue
            price = int(price_search.group(1).replace('.', '').replace(' ', ''))
            break
        if price == -1:
            counters["price_not_found"] += 1
            continue
        if "za týden" in price_header:
            price /= 7
        # todo: za vikend
        # todo: when there is only prices per person we probably do not like the object (but we have to iterate all the price sections to determine this properly)
        if "za osobu" in price_header:
            if not prop.get("capacity"):
                continue
            price *= int(prop.get("capacity"))
        if "pokoj" in price_header:
            if not prop.get("rooms"):
                continue
            price *= int(prop.get("rooms"))
        prop["price (per day per object)"] = round(price)
        prices.append(price)


def enhance(properties: Iterable[Dict[str, Any]]):
    add_homepage(properties)
    ratings_stats(properties)
    distances_to_map(properties)
    add_distances(properties)
    extract_normalized_price(properties)


def filter_out(reason: str, item: Dict[str, Any], soft: bool = False):
    if soft:
        reason += "_soft"
    counters[f"filtered_{reason}"] += 1
    if "filtered_reasons" not in item:
        item["filtered_reasons"] = set()
    item["filtered_reasons"].add(reason)
    if not soft:
        item["filtered"] = True


def extract_normalized_distance(dist: str) -> float:
    """
    get distance in meters
    """
    found_dist = distance_extractor.search(dist)
    if not found_dist:
        return -1
    val, unit = found_dist.group(1), found_dist.group(2)
    val = float(val.replace(',', '.'))
    if unit == "m":
        return val
    if unit == "km":
        return val * 1000
    if unit == "min":
        walking_speed = 5  # km/h
        walking_speed_ms = walking_speed * 1000 / 60  # m/min
        return val * walking_speed_ms
    return -1


def is_equipment_present(wanted_equip: List[str], property: Dict[str, Any]):
    for equip in property.get("equipment", []):
        for wanted in wanted_equip:
            if wanted in equip.lower():
                return True
    return False


def filtering(properties: Iterable[Dict[str, Any]]):
    for i in properties:
        if i.get("GPS"):
            counters["gps_present"] += 1
            # 16.6 (moved because of Beskydy)
            if float(i.get("GPS").get("E")) > 19:
                filter_out("too_much_east", i)
        if i.get("apartman"):
            filter_out("apartman", i)
        capacity = int(i.get("capacity", -1))
        if capacity == -1:
            filter_out("capacity_missing", i)
        elif capacity < MIN_BEDS:
            filter_out(f"small_capacity_<{MIN_BEDS}", i)
        elif capacity > MAX_BEDS:
            filter_out(f"too_big_>{MAX_BEDS}", i)
        rooms = i.get("rooms", -1)
        if not rooms or rooms == -1:
            filter_out("missing_rooms", i)
        elif int(rooms) < MIN_ROOMS:
            filter_out(f"not_enough_rooms_<{MIN_ROOMS}", i)
        restaurant_dist = i.get("restaurace_distance_m", -1)
        if restaurant_dist == -1:
            filter_out("restaurant_distance_invalid", i, soft=True)
        if restaurant_dist > MAX_RESTAURANT_DISTANCE:
            filter_out(f"restaurant_distance_too_big_>{MAX_RESTAURANT_DISTANCE}", i, soft=True)
        if not is_equipment_present(["inter", "wi-fi", "wifi"], i):
            filter_out(f"no_internet", i)
        if not is_equipment_present(["společenská místnost"], i):
            filter_out(f"no_shared_room", i)
        if not is_equipment_present(["parko"], i):
            filter_out(f"no_parking", i)
        if not is_equipment_present(["gril"], i):
            filter_out(f"no_grill", i, soft=True)
        price = i.get("price")
        if price and int(price) > MAX_PRICE:
            filter_out(f"expensive", i)
        area = i.get("url").split('/')[3]
        i["area"] = area
        if area in {"jeseniky", "slovensko_chaty"}:
            filter_out(f"blocklisted_area", i)

    for i in properties:
        if i.get("filtered", False):
            counters["filtered"] += 1


def store(properties, store_csv=True, store_json=True):
    if store_csv:
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

        with open('out.csv', 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for csv_prop in properties:
                prop = copy.deepcopy(csv_prop)
                prop.pop("text")
                rating = prop.get("rating_stats")
                if rating:
                    prop["rating_mean"] = rating.get("mean")
                    prop["rating_median"] = rating.get("median")
                    prop["rating_samples"] = rating.get("samples")
                writer.writerow(prop)

    if store_json:
        def list_filtered_reasons(x):
            for k, v in x.items():
                if type(v) is set:
                    x[k] = list(v)
            return x
        json.dump(list(map(list_filtered_reasons, properties)), open("out.json", 'w'))


def main():
    properties = list(load_data())
    enhance(properties)
    filtering(properties)
    print()
    print(f"global ratings stats: {numeric_stats(ratings)}")
    print(f"prices stats: {numeric_stats(prices)}")
    print()
    for name, samples in distances.items():
        print(f"distance to {name} stats: {numeric_stats(samples)}")
    print()
    counter_stats(properties)
    store(properties)


if __name__ == '__main__':
    main()
