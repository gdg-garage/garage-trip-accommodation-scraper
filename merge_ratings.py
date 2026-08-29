import argparse
import csv
import json
import os
from typing import Dict, Any, List
from utils import numeric_stats

DEFAULT_RATINGS_JSON = "ratings.json"
DEFAULT_INPUT_CSV = "out.csv"
DEFAULT_OUTPUT_CSV = "out-rated.csv"


def merge(ratings_file: str, input_csv: str, output_csv: str):
    """Merge AI and manual ratings into processed CSV property dataset."""
    if not os.path.exists(ratings_file):
        raise FileNotFoundError(f"Ratings file '{ratings_file}' not found. Run rank.py first.")
    if not os.path.exists(input_csv):
        raise FileNotFoundError(f"Input CSV '{input_csv}' not found. Run process.py first.")

    with open(ratings_file, "r", encoding="utf-8") as f:
        ratings: Dict[str, Any] = json.load(f)

    properties: List[Dict[str, Any]] = []

    with open(input_csv, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for r in reader:
            prop_id = r.get("id", "")
            prop_ratings = []
            if prop_id in ratings:
                for rating_name, rating_value in ratings[prop_id].items():
                    if isinstance(rating_value, dict):
                        for k, v in rating_value.items():
                            r[f"{rating_name}_{k}"] = v
                        if "rating" in rating_value and "v3" in rating_name and "llama3.2_v3" != rating_name:
                            try:
                                prop_ratings.append(float(rating_value["rating"]))
                            except (ValueError, TypeError):
                                pass
                    else:
                        r[rating_name] = rating_value

            if prop_ratings:
                ratings_stats = numeric_stats(prop_ratings)
                for k, v in ratings_stats.items():
                    r[f"ratings_{k}"] = v

            properties.append(r)

    all_fieldnames = set()
    for prop in properties:
        all_fieldnames |= set(prop.keys())

    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=sorted(all_fieldnames))
        writer.writeheader()
        for prop in properties:
            writer.writerow(prop)

    print(f"Merged {len(properties)} properties with ratings -> {output_csv}")


def parse_args():
    parser = argparse.ArgumentParser(description="Merge LLM and manual ratings with accommodation dataset.")
    parser.add_argument("--ratings", "-r", type=str, default=DEFAULT_RATINGS_JSON, help=f"Ratings JSON file (default: {DEFAULT_RATINGS_JSON})")
    parser.add_argument("--input-csv", "-i", type=str, default=DEFAULT_INPUT_CSV, help=f"Input CSV file (default: {DEFAULT_INPUT_CSV})")
    parser.add_argument("--output-csv", "-o", type=str, default=DEFAULT_OUTPUT_CSV, help=f"Output merged CSV file (default: {DEFAULT_OUTPUT_CSV})")
    return parser.parse_args()


def main():
    args = parse_args()
    merge(args.ratings, args.input_csv, args.output_csv)


if __name__ == '__main__':
    main()

