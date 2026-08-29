import argparse
import csv
import json
import os
from typing import Dict, Any

DEFAULT_RATINGS_JSON = "ratings.json"
DEFAULT_MANUAL_CSV = "manual-ratings-9-2024.csv"


def add_manual_ratings(ratings_path: str, manual_csv_path: str, output_path: str):
    """Load manual reviewer feedback from CSV and merge into ratings JSON."""
    ratings: Dict[str, Any] = {}
    if os.path.exists(ratings_path):
        with open(ratings_path, "r", encoding="utf-8") as f:
            ratings = json.load(f)

    if not os.path.exists(manual_csv_path):
        raise FileNotFoundError(f"Manual ratings CSV '{manual_csv_path}' not found.")

    with open(manual_csv_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for r in reader:
            prop_id = r.get("id")
            if not prop_id:
                continue
            if prop_id not in ratings:
                ratings[prop_id] = {}
            if "tivvit like" in r or "tivvit veto" in r:
                ratings[prop_id]["tivvit"] = {
                    "like": r.get('tivvit like'),
                    "veto": r.get("tivvit veto")
                }
            for user in ["simon", "eve", "tomas"]:
                if user in r and r[user]:
                    ratings[prop_id][user] = r[user]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ratings, f, ensure_ascii=False, indent=2)

    print(f"Updated manual ratings saved to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Add manual human ratings from CSV to ratings.json.")
    parser.add_argument("--ratings", "-r", type=str, default=DEFAULT_RATINGS_JSON, help=f"Ratings JSON file (default: {DEFAULT_RATINGS_JSON})")
    parser.add_argument("--csv", "-c", type=str, default=DEFAULT_MANUAL_CSV, help=f"Manual ratings CSV (default: {DEFAULT_MANUAL_CSV})")
    parser.add_argument("--output", "-o", type=str, default=DEFAULT_RATINGS_JSON, help=f"Output ratings JSON (default: {DEFAULT_RATINGS_JSON})")
    return parser.parse_args()


def main():
    args = parse_args()
    add_manual_ratings(args.ratings, args.csv, args.output)


if __name__ == '__main__':
    main()

