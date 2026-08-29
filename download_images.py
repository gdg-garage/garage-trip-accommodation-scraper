import argparse
import glob
import json
import logging
import os
import random
import time
import urllib.parse
from typing import List, Tuple, Set, Optional, Dict, Any
import requests
from bs4 import BeautifulSoup

DEFAULT_OUTPUT_DIR = "imgs"
DEFAULT_DELAY = 0.2
DEFAULT_TIMEOUT = 15
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


def collect_images_from_json(json_path: str) -> List[Tuple[str, str]]:
    """Collect image list from parsed JSON file (out.json or properties.json)."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    results = []
    for prop in data:
        for img in prop.get("images", []):
            if isinstance(img, (list, tuple)) and len(img) >= 2:
                results.append((img[0] or "", img[1]))
            elif isinstance(img, str):
                results.append(("", img))
    return results


def collect_images_from_html_dir(html_dir: str) -> List[Tuple[str, str]]:
    """Scan local HTML files and extract image thumbnail and full-size links."""
    images: List[Tuple[str, str]] = []
    html_files = sorted(glob.glob(os.path.join(html_dir, "*.html")))
    for html_file in html_files:
        try:
            with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            nahledy = soup.find(id="nahledy")
            if nahledy:
                for a in nahledy.find_all("a"):
                    href = a.get("href")
                    if href:
                        if not href.startswith("http"):
                            href = "https://www.e-chalupy.cz/" + href.lstrip("/")
                        title = a.get("title") or ""
                        images.append((title, href))
        except Exception as e:
            logging.warning(f"Error reading {html_file}: {e}")
    return images


def image_url_to_filename(image_url: str) -> str:
    """Generate safe filename for an image URL."""
    return urllib.parse.quote(image_url, safe='')


def get_shard_items(items: List[Any], total_shards: int, shard_id: int) -> List[Any]:
    """Return slice of items for this worker shard."""
    if total_shards <= 1:
        return items
    if shard_id < 0 or shard_id >= total_shards:
        raise ValueError(f"shard-id ({shard_id}) must be in range [0, {total_shards - 1}]")
    return [item for i, item in enumerate(items) if i % total_shards == shard_id]


def download_image_with_retry(
    url: str,
    session: requests.Session,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 3,
) -> Optional[bytes]:
    """Download image with retry on network error."""
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.content
            elif response.status_code == 404:
                return None
            elif response.status_code in (429, 503):
                time.sleep(1.0 * attempt)
        except requests.RequestException:
            time.sleep(0.5 * attempt)
    return None


def parse_args():
    parser = argparse.ArgumentParser(description="Step 3: Download property images with distributed sharding and polite rate-limiting.")
    parser.add_argument("--input-json", "-j", type=str, default=None, help="Input JSON file (e.g. out.json or properties.json)")
    parser.add_argument("--html-dir", "-d", type=str, default="html", help="Directory containing downloaded HTML pages (used if --input-json is not given)")
    parser.add_argument("--output-dir", "-o", type=str, default=DEFAULT_OUTPUT_DIR, help=f"Destination images directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--total-shards", "-n", type=int, default=1, help="Total number of distributed worker shards (default: 1)")
    parser.add_argument("--shard-id", "-s", type=int, default=0, help="Zero-indexed shard ID for this worker (0..total_shards-1)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Polite delay between image requests in seconds (default: {DEFAULT_DELAY})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"HTTP request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of images to download in this run")
    parser.add_argument("--force", action="store_true", help="Overwrite existing cached images instead of skipping")
    return parser.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    if args.input_json and os.path.exists(args.input_json):
        raw_images = collect_images_from_json(args.input_json)
    elif os.path.exists(args.html_dir):
        raw_images = collect_images_from_html_dir(args.html_dir)
    elif os.path.exists("out.json"):
        raw_images = collect_images_from_json("out.json")
    else:
        raise FileNotFoundError(f"Neither --input-json nor HTML dir '{args.html_dir}' was found. Run download_html.py first.")

    # Deduplicate image URLs
    unique_images: List[Tuple[str, str]] = []
    seen_urls: Set[str] = set()
    for title, img_url in raw_images:
        if img_url and img_url not in seen_urls:
            seen_urls.add(img_url)
            unique_images.append((title, img_url))

    shard_images = get_shard_items(unique_images, args.total_shards, args.shard_id)
    if args.limit:
        shard_images = shard_images[:args.limit]

    total_count = len(shard_images)
    print(f"--- Image Downloader ---")
    print(f"Total unique images: {len(unique_images)}")
    print(f"Assigned shard: {args.shard_id + 1}/{args.total_shards} ({total_count} images assigned to this worker)")
    print(f"Output directory: {args.output_dir}/")
    print(f"Delay: {args.delay}s\n")

    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    downloaded = 0
    skipped = 0
    failed = 0

    for idx, (title, img_url) in enumerate(shard_images, 1):
        filename = image_url_to_filename(img_url)
        target_path = os.path.join(args.output_dir, filename)

        if not args.force and os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            skipped += 1
            if idx % 50 == 0 or idx == total_count:
                print(f"Progress: [{idx}/{total_count}] (Downloaded: {downloaded}, Cached/Skipped: {skipped}, Failed: {failed})")
            continue

        content = download_image_with_retry(img_url, session=session, timeout=args.timeout)
        if content:
            with open(target_path, "wb") as f:
                f.write(content)
            downloaded += 1
        else:
            failed += 1

        if idx % 25 == 0 or idx == total_count:
            print(f"Progress: [{idx}/{total_count}] (Downloaded: {downloaded}, Cached/Skipped: {skipped}, Failed: {failed})")

        if args.delay > 0 and idx < total_count:
            time.sleep(args.delay)

    print("\n--- Image Shard Download Finished ---")
    print(f"Total processed in this shard: {total_count}")
    print(f"New downloads: {downloaded}")
    print(f"Cached (skipped): {skipped}")
    print(f"Failed: {failed}")


if __name__ == '__main__':
    main()
