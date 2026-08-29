import argparse
import os
import parse_dom
from parse_dom import (
    parse_html_content,
    parse_all_html_files,
    extract_normalized_distance,
    extract_normalized_price,
    is_equipment_present,
    filter_out,
    apply_heuristics_and_filtering,
    add_homepage,
    distances_to_map,
    ratings_stats,
    add_distances,
    clean,
    store_results,
    DEFAULT_MIN_BEDS,
    DEFAULT_MAX_BEDS,
    DEFAULT_MIN_ROOMS,
    DEFAULT_MAX_RESTAURANT_DISTANCE,
    DEFAULT_MAX_PRICE,
)

# Aliases for compatibility
filtering = apply_heuristics_and_filtering
store = store_results


def main():
    parser = argparse.ArgumentParser(description="Process accommodation data (from HTML directory or JSON files).")
    parser.add_argument("--html-dir", "-d", type=str, default="html", help="Directory with raw HTML files")
    parser.add_argument("--input", "-i", type=str, default=None, help="Input properties JSON or JSON.GZ path")
    parser.add_argument("--output-csv", type=str, default="out.csv", help="Output CSV path (default: out.csv)")
    parser.add_argument("--output-json", type=str, default="out.json", help="Output JSON path (default: out.json)")
    parser.add_argument("--min-beds", type=int, default=DEFAULT_MIN_BEDS, help=f"Minimum beds (default: {DEFAULT_MIN_BEDS})")
    parser.add_argument("--max-beds", type=int, default=DEFAULT_MAX_BEDS, help=f"Maximum beds (default: {DEFAULT_MAX_BEDS})")
    parser.add_argument("--min-rooms", type=int, default=DEFAULT_MIN_ROOMS, help=f"Minimum rooms (default: {DEFAULT_MIN_ROOMS})")
    parser.add_argument("--max-restaurant-dist", type=int, default=DEFAULT_MAX_RESTAURANT_DISTANCE, help=f"Max restaurant distance in m (default: {DEFAULT_MAX_RESTAURANT_DISTANCE})")
    parser.add_argument("--max-price", type=int, default=DEFAULT_MAX_PRICE, help=f"Max daily price in CZK (default: {DEFAULT_MAX_PRICE})")
    args = parser.parse_args()

    if os.path.exists(args.html_dir) and any(os.scandir(args.html_dir)):
        parse_dom.main()
    else:
        print(f"HTML directory '{args.html_dir}' not found or empty. Please run download_html.py first or use parse_dom.py directly.")


if __name__ == '__main__':
    main()



