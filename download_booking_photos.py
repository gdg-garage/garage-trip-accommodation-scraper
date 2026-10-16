#!/usr/bin/env python3
"""
Photo Downloader for Booking.com accommodations.
Extracts high-resolution gallery photo URLs from downloaded Booking HTML files
and downloads them into booking_images/<slug>/ with rate-limiting, retries, and verification.
"""

import argparse
import glob
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Set, Optional


DEFAULT_HTML_DIR = "booking_html"
DEFAULT_OUTPUT_DIR = "booking_images"
DEFAULT_LIMIT_PER_PROPERTY = 25
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


def extract_photos_from_html(html: str) -> List[Dict[str, str]]:
    """
    Extracts unique high-resolution photo URLs and descriptions from Booking HTML.
    Returns list of dicts with 'url', 'caption', 'photo_id'.
    """
    # 1. Look for all bstatic hotel images
    # e.g., https://cf.bstatic.com/xdata/images/hotel/max1024x768/618784262.jpg?k=...&o=
    raw_urls = re.findall(r'https?://[^"\'\s]+bstatic\.com/xdata/images/hotel/[^"\'\s]+', html)

    # Also check image tags with alt descriptions
    # e.g., alt: "a large kitchen with a wooden table and chairs..."
    alt_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\']', html)
    alt_map = {}
    for src, alt in alt_matches:
        if 'bstatic.com' in src and '/images/hotel/' in src:
            # normalize photo id
            m_id = re.search(r'/hotel/(?:max\w+|square\w+|[0-9x]+)/(\d+)', src)
            if m_id and alt:
                alt_map[m_id.group(1)] = alt.strip()

    seen_ids = set()
    photos = []

    for raw in raw_urls:
        clean = raw.replace('\\u0026', '&').replace('&amp;', '&')
        m = re.search(r'/hotel/(?:max\w+|square\w+|[0-9x]+)/(\d+)\.(jpg|jpeg|webp|png)(?:\?k=([a-f0-9]+))?', clean)
        if not m:
            continue
        photo_id = m.group(1)
        ext = m.group(2)
        key = m.group(3)

        if photo_id in seen_ids:
            continue
        seen_ids.add(photo_id)

        # Build highest resolution URL
        if key:
            hi_res_url = f"https://cf.bstatic.com/xdata/images/hotel/max1280x900/{photo_id}.{ext}?k={key}&o=&hp=1"
        else:
            hi_res_url = f"https://cf.bstatic.com/xdata/images/hotel/max1280x900/{photo_id}.{ext}?o="

        caption = alt_map.get(photo_id, "")
        photos.append({
            'photo_id': photo_id,
            'url': hi_res_url,
            'caption': caption,
            'extension': ext
        })

    return photos


def download_single_photo(url: str, output_path: str, timeout: int = 15) -> bool:
    """Download and verify image data."""
    if os.path.exists(output_path) and os.path.getsize(output_path) > 5000:
        return True  # already cached

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    data = response.read()
                    if len(data) > 5000:
                        with open(output_path, "wb") as f:
                            f.write(data)
                        return True
        except Exception:
            time.sleep(1.0 + attempt)
    return False


def download_property_photos(slug: str, html_path: str, output_dir: str, limit: int = 25, delay: float = 0.3) -> int:
    """Download photos for a single accommodation."""
    if not os.path.exists(html_path):
        print(f"Error: {html_path} does not exist!")
        return 0

    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    photos = extract_photos_from_html(html)
    if not photos:
        print(f"[{slug}] No photos found in HTML.")
        return 0

    target_dir = os.path.join(output_dir, slug)
    os.makedirs(target_dir, exist_ok=True)

    # Save manifest with captions
    manifest_path = os.path.join(target_dir, "photos_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(photos, f, indent=2, ensure_ascii=False)

    downloaded = 0
    target_photos = photos[:limit] if limit > 0 else photos

    for idx, p in enumerate(target_photos, 1):
        fn = f"{p['photo_id']}.{p['extension']}"
        fp = os.path.join(target_dir, fn)
        if not (os.path.exists(fp) and os.path.getsize(fp) > 5000):
            success = download_single_photo(p['url'], fp)
            if success:
                downloaded += 1
            time.sleep(delay * random.uniform(0.8, 1.4))
        else:
            downloaded += 1

    print(f"[{slug}] Processed {len(target_photos)} photos (cached/downloaded: {downloaded})")
    return downloaded


def main():
    parser = argparse.ArgumentParser(description="Download Booking photos from detail HTML pages")
    parser.add_argument("--slug", "-s", default=None, help="Specific property slug to download")
    parser.add_argument("--html-dir", "-d", default=DEFAULT_HTML_DIR, help="Directory containing Booking HTML files")
    parser.add_argument("--output-dir", "-o", default=DEFAULT_OUTPUT_DIR, help="Destination directory for photos")
    parser.add_argument("--limit-photos", "-l", type=int, default=DEFAULT_LIMIT_PER_PROPERTY, help="Max photos per property")
    parser.add_argument("--limit-properties", "-p", type=int, default=None, help="Max properties to process")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between photo downloads")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    if args.slug:
        html_file = os.path.join(args.html_dir, f"{args.slug}.html")
        download_property_photos(args.slug, html_file, args.output_dir, limit=args.limit_photos, delay=args.delay)
        return

    html_files = sorted(glob.glob(os.path.join(args.html_dir, "*.html")))
    if not html_files:
        print(f"No HTML files found in {args.html_dir}!")
        return

    if args.limit_properties and args.limit_properties > 0:
        html_files = html_files[:args.limit_properties]

    print(f"Processing photos for {len(html_files)} properties...")
    total_downloaded = 0
    for idx, fp in enumerate(html_files, 1):
        slug = os.path.splitext(os.path.basename(fp))[0]
        count = download_property_photos(slug, fp, args.output_dir, limit=args.limit_photos, delay=args.delay)
        total_downloaded += count

    print(f"\nDone! Downloaded/verified {total_downloaded} photos across {len(html_files)} properties.")


if __name__ == "__main__":
    main()
