import argparse
import glob
import json
import logging
import os
import random
import time
import urllib.parse
from typing import List, Tuple, Set, Optional, Dict, Any

from download_html import (
    get_authenticated_session,
    DEFAULT_SESSION_FILE,
    DEFAULT_USER_AGENT,
    CHALLENGE_TITLE,
    HAS_CURL_CFFI,
)

DEFAULT_OUTPUT_DIR = "imgs"
DEFAULT_DELAY = 0.2
DEFAULT_TIMEOUT = 15


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
    from bs4 import BeautifulSoup

    images: List[Tuple[str, str]] = []
    html_files = sorted(glob.glob(os.path.join(html_dir, "*.html")))
    for html_file in html_files:
        try:
            with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            
            # 1. Legacy nahledy container
            nahledy = soup.find(id="nahledy")
            if nahledy:
                for a in nahledy.find_all("a"):
                    href = a.get("href")
                    if href:
                        if not href.startswith("http"):
                            href = "https://www.e-chalupy.cz/" + href.lstrip("/")
                        title = a.get("title") or ""
                        images.append((title, href))
            
            # 2. Full-size photo links (/foto/...)
            for a in soup.find_all("a"):
                href = a.get("href")
                if href and "/foto/" in href and any(href.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    if not href.startswith("http"):
                        href = "https://www.e-chalupy.cz/" + href.lstrip("/")
                    title = a.get("title") or a.get("alt") or ""
                    images.append((title, href))

            # 3. Direct /foto/ img tags
            for img in soup.find_all("img"):
                src = img.get("src")
                if src and "/foto/" in src and any(src.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    if not src.startswith("http"):
                        src = "https://www.e-chalupy.cz/" + src.lstrip("/")
                    title = img.get("alt") or img.get("title") or ""
                    images.append((title, src))

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
    session: Any,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 3,
) -> Tuple[Optional[bytes], int, bool]:
    """
    Download image with retry on network error and Cloudflare challenge detection.
    Returns (image_bytes, status_code, is_challenge_blocked).
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            
            # Check for Cloudflare challenge in body or status
            is_cf_blocked = response.status_code == 403 or (
                response.content and b"Just a moment..." in response.content[:1000]
            )
            if is_cf_blocked:
                return None, response.status_code, True

            if response.status_code == 200:
                # Validate it's not an HTML error response disguised as 200
                if response.content.startswith(b"<!DOCTYPE html>") and b"Just a moment" in response.content[:1000]:
                    return None, response.status_code, True
                return response.content, response.status_code, False
            elif response.status_code == 404:
                return None, 404, False
            elif response.status_code in (429, 503):
                time.sleep(1.0 * attempt)
        except Exception as e:
            logging.debug(f"Error downloading {url}: {e}")
            time.sleep(0.5 * attempt)
            
    return None, 0, False


def parse_args():
    parser = argparse.ArgumentParser(description="Step 3: Download property images with distributed sharding and Cloudflare session support.")
    parser.add_argument("--input-json", "-j", type=str, default=None, help="Input JSON file (e.g. out.json or properties.json)")
    parser.add_argument("--html-dir", "-d", type=str, default="html", help="Directory containing downloaded HTML pages (used if --input-json is not given)")
    parser.add_argument("--output-dir", "-o", type=str, default=DEFAULT_OUTPUT_DIR, help=f"Destination images directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--total-shards", "-n", type=int, default=1, help="Total number of distributed worker shards (default: 1)")
    parser.add_argument("--shard-id", "-s", type=int, default=0, help="Zero-indexed shard ID for this worker (0..total_shards-1)")
    parser.add_argument("--delay", type=float, default=2.0, help="Base delay in seconds between image downloads (default: 2.0s)")
    parser.add_argument("--delay-minutes", type=float, default=None, help="Delay in minutes between image downloads (e.g. 0.5 for 30s)")
    parser.add_argument("--jitter", type=float, default=1.0, help="Random jitter in seconds added to delay (default: 1.0s)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"HTTP request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of images to download in this run")
    parser.add_argument("--force", action="store_true", help="Overwrite existing cached images instead of skipping")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")

    # Cloudflare session options
    parser.add_argument("--cf-clearance", type=str, default=None, help="Manual Cloudflare cf_clearance cookie value")
    parser.add_argument("--user-agent", type=str, default=None, help="User-Agent string matching cf_clearance")
    parser.add_argument("--session-file", type=str, default=DEFAULT_SESSION_FILE, help=f"Path to session cache file (default: {DEFAULT_SESSION_FILE})")
    parser.add_argument("--no-browser", action="store_true", help="Do not attempt to open a browser for Cloudflare challenge solving")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode when solving challenge")
    parser.add_argument("--force-auth", action="store_true", help="Force re-running Cloudflare browser solver even if session cache exists")

    return parser.parse_args()


def main():
    args = parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    base_delay = (args.delay_minutes * 60.0) if args.delay_minutes is not None else args.delay

    os.makedirs(args.output_dir, exist_ok=True)

    if args.input_json and os.path.exists(args.input_json):
        images = collect_images_from_json(args.input_json)
    elif os.path.exists(args.html_dir):
        images = collect_images_from_html_dir(args.html_dir)
    else:
        print(f"Error: Neither valid JSON file '{args.input_json}' nor HTML directory '{args.html_dir}' found.")
        return

    # Deduplicate image URLs
    seen = set()
    unique_images = []
    for title, url in images:
        if url not in seen:
            seen.add(url)
            unique_images.append((title, url))

    shard_images = get_shard_items(unique_images, args.total_shards, args.shard_id)

    if args.limit:
        shard_images = shard_images[:args.limit]

    total_count = len(shard_images)
    print(f"--- Ultra-Polite Image Downloader ---")
    print(f"Total unique images found: {len(unique_images)}")
    print(f"Assigned shard: {args.shard_id + 1}/{args.total_shards} ({total_count} images assigned to this worker)")
    print(f"Output directory: {args.output_dir}/")
    print(f"Rate limiting: {base_delay:.1f}s base delay + up to {args.jitter:.1f}s random jitter between downloads\n")

    session = get_authenticated_session(
        cf_clearance=args.cf_clearance,
        user_agent=args.user_agent,
        session_file=args.session_file,
        no_browser=args.no_browser,
        headless=args.headless,
        force_refresh=args.force_auth,
    )

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

        print(f"[{idx}/{total_count}] Downloading image: {img_url} ...")
        content, status_code, is_blocked = download_image_with_retry(img_url, session=session, timeout=args.timeout)

        # Handle Cloudflare block
        if is_blocked:
            print(f"  ⚠️ Cloudflare challenge encountered on image download. Cooling down for 2 minutes...")
            time.sleep(120)
            if not args.no_browser:
                logging.info("Refreshing session...")
                session = get_authenticated_session(
                    session_file=args.session_file,
                    no_browser=False,
                    headless=args.headless,
                    target_url=img_url,
                    force_refresh=True,
                )
                content, status_code, is_blocked = download_image_with_retry(img_url, session=session, timeout=args.timeout)

        if content and not is_blocked:
            with open(target_path, "wb") as f:
                f.write(content)
            downloaded += 1
            print(f"  ✓ Saved to {filename} ({len(content):,} bytes)")
        else:
            failed += 1
            print(f"  ✗ Failed ({status_code})")

        print(f"Progress: [{idx}/{total_count}] (Downloaded: {downloaded}, Cached: {skipped}, Failed: {failed})")

        if idx < total_count:
            sleep_duration = base_delay + random.uniform(0, args.jitter)
            if sleep_duration >= 60:
                print(f"  ⏳ Sleeping for {sleep_duration / 60:.1f} minutes ({sleep_duration:.0f}s) before next image...\n")
            elif sleep_duration > 0:
                print(f"  ⏳ Sleeping for {sleep_duration:.1f}s before next image...\n")
            time.sleep(sleep_duration)

    print("\n--- Image Shard Download Finished ---")
    print(f"Total processed in this shard: {total_count}")
    print(f"New downloads: {downloaded}")
    print(f"Cached (skipped): {skipped}")
    print(f"Failed: {failed}")


if __name__ == '__main__':
    main()
