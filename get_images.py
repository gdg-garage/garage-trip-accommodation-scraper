import argparse
import json
import logging
import os
import urllib.parse
from typing import List, Dict, Any, Optional
import requests

DEFAULT_OBJECTS_JSON_PATH = "out.json"
DEFAULT_OUTPUT_DIR = "imgs"
DEFAULT_TIMEOUT = 15


def load_objects(filepath: str = DEFAULT_OBJECTS_JSON_PATH) -> List[Dict[str, Any]]:
    """Load property objects from JSON file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Objects file '{filepath}' not found. Run process.py first.")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def download_image(url: str, session: Optional[requests.Session] = None, timeout: int = DEFAULT_TIMEOUT) -> Optional[bytes]:
    """Download image content with error handling and timeout."""
    client = session or requests
    try:
        response = client.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        logging.warning(f"Failed to download image {url}: {e}")
        return None


def parse_args():
    parser = argparse.ArgumentParser(description="Download property images for visual LLM evaluation.")
    parser.add_argument("--input", "-i", type=str, default=DEFAULT_OBJECTS_JSON_PATH, help=f"Input objects JSON (default: {DEFAULT_OBJECTS_JSON_PATH})")
    parser.add_argument("--output-dir", "-o", type=str, default=DEFAULT_OUTPUT_DIR, help=f"Target images directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of properties to download images for")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Download timeout in seconds (default: {DEFAULT_TIMEOUT})")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    os.makedirs(args.output_dir, exist_ok=True)
    properties = load_objects(args.input)
    print(f"Loaded {len(properties)} objects from {args.input}")

    if args.limit:
        properties = properties[:args.limit]
        print(f"Limited processing to {len(properties)} objects")

    session = requests.Session()
    total = len(properties)
    total_downloaded = 0
    total_skipped = 0

    for i, p in enumerate(properties, 1):
        images = p.get("images", [])
        for _, image_url in images:
            if not image_url:
                continue
            filename = urllib.parse.quote(image_url, safe='')
            final_path = os.path.join(args.output_dir, filename)
            if os.path.exists(final_path):
                total_skipped += 1
                continue

            img_bytes = download_image(image_url, session=session, timeout=args.timeout)
            if img_bytes:
                with open(final_path, 'wb') as f:
                    f.write(img_bytes)
                total_downloaded += 1

        if i % 10 == 0 or i == total:
            print(f"Progress: {i}/{total} properties (Downloaded {total_downloaded} new images, skipped {total_skipped})")

    print(f"Done. Total new images downloaded: {total_downloaded}, total skipped (cached): {total_skipped}")


if __name__ == '__main__':
    main()

