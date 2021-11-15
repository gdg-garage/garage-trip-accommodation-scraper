import gzip
import json
import statistics
from collections import defaultdict
from typing import Iterable, Dict, Any
import re

# global stats
counters = defaultdict(int)
ratings = []

# limits
MIN_BEDS = 22
MAX_BEDS = 30
MIN_ROOMS = 4
MAX_RESTAURANT_DISTANCE = 1500

# regex
distance_extractor = re.compile(r"(\d*[.,]?\d+)\s*(min|m|km)")


def numeric_stats(data):
    return {
        "max": max(data),
        "min": min(data),
        "mean": statistics.mean(data),
        "median": statistics.median(data),
    }


def load_data() -> Iterable[Dict[str, Any]]:
    with gzip.open("properties.json.gz") as f:
        for line in f:
            yield json.loads(line)


def add_homepage(properties: Iterable[Dict[str, Any]]):
    """
    extract homepage link
    """
    for i in properties:
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


def restaurant_distance(properties: Iterable[Dict[str, Any]]):
    for i in properties:
        restaurant_dist = i.get("distances_map", {}).get("restaurace")
        if restaurant_dist:
            counters["restaurant_distance_present"] += 1
            i["restaurant_distance_m"] = extract_normalized_distance(restaurant_dist)


def enhance(properties: Iterable[Dict[str, Any]]):
    add_homepage(properties)
    ratings_stats(properties)
    distances_to_map(properties)
    restaurant_distance(properties)


def filter_out(reason: str, item: Dict[str, Any]):
    counters[f"filtered_{reason}"] += 1
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


def filtering(properties: Iterable[Dict[str, Any]]):
    for i in properties:
        capacity = int(i.get("capacity", -1))
        if capacity == -1:
            filter_out("capacity_missing", i)
        elif capacity < MIN_BEDS:
            filter_out("small_capacity", i)
        elif capacity > MAX_BEDS:
            filter_out("too_big", i)
        rooms = i.get("rooms", -1)
        if not rooms or rooms == -1:
            filter_out("missing_rooms", i)
        elif int(rooms) < MIN_ROOMS:
            filter_out("not_enough_rooms", i)
        restaurant_dist = i.get("restaurant_distance_m", -1)
        if restaurant_dist == -1:
            filter_out("restaurant_distance_invalid", i)
        if restaurant_dist > MAX_RESTAURANT_DISTANCE:
            filter_out("restaurant_distance_too_big", i)

    for i in properties:
        if i.get("filtered", False):
            counters["filtered"] += 1


def main():
    properties = [i for i in load_data()]
    enhance(properties)
    filtering(properties)
    print()
    print(f"global ratings stats: {numeric_stats(ratings)}")
    print()
    counter_stats(properties)


if __name__ == '__main__':
    main()
