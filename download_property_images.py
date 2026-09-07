#!/usr/bin/env python3
"""
Download full-resolution images for a single property with graceful timeouts,
exponential backoff retries, polite pacing, and content validation.
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional

from extract_property_images import extract_property_images, resolve_html_file

DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
DEFAULT_TIMEOUT = 15
DEFAULT_DELAY = 0.8
DEFAULT_JITTER = 0.4
DEFAULT_MAX_RETRIES = 3
DEFAULT_OUTPUT_ROOT = "images"


def is_valid_image_bytes(data: bytes) -> bool:
    """Validate that downloaded payload is a real image and not an HTML error page."""
    if len(data) < 500:
        return False
    # Check JPEG, PNG, or WebP magic headers
    if data.startswith(b"\xff\xd8\xff"):
        return True
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return True
    return False


def download_single_image(
    url: str,
    output_path: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    user_agent: str = DEFAULT_USER_AGENT,
) -> Dict[str, Any]:
    """
    Download a single image with graceful timeout and exponential backoff retries.
    Returns result dict with status, size, attempts, and error (if any).
    """
    headers = {
        "User-Agent": user_agent,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://www.e-chalupy.cz/",
    }

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status_code = resp.status
                content = resp.read()

            if status_code == 200:
                if not is_valid_image_bytes(content):
                    snippet = content[:300].decode("utf-8", errors="ignore")
                    if "Just a moment" in snippet or "challenge" in snippet.lower():
                        return {"success": False, "status": 403, "error": "Cloudflare challenge in body", "bytes": 0}
                    raise ValueError(f"Downloaded content is not a valid image ({len(content)} bytes)")

                # Atomic write to temporary file first, then rename
                tmp_path = output_path + ".tmp"
                with open(tmp_path, "wb") as fh:
                    fh.write(content)
                os.replace(tmp_path, output_path)

                return {
                    "success": True,
                    "status": 200,
                    "bytes": len(content),
                    "attempts": attempt,
                    "error": None,
                }
            elif status_code == 404:
                return {"success": False, "status": 404, "error": "Not Found (404)", "bytes": 0}
            else:
                last_error = f"HTTP {status_code}"

        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}: {e.reason}"
            if e.code in (403, 429):
                # Back off more aggressively on rate limit / challenge
                sleep_time = (2.0 ** attempt) + random.uniform(1.0, 3.0)
                time.sleep(sleep_time)
            elif e.code == 404:
                return {"success": False, "status": 404, "error": "Not Found (404)", "bytes": 0}
            else:
                time.sleep(1.0 * attempt)

        except urllib.error.URLError as e:
            last_error = f"Connection error: {e.reason}"
            time.sleep(1.0 * attempt)

        except Exception as e:
            last_error = str(e)
            time.sleep(1.0 * attempt)

    return {
        "success": False,
        "status": 0,
        "bytes": 0,
        "attempts": max_retries,
        "error": last_error or "Max retries exceeded",
    }


def download_property_images(
    property_data: Dict[str, Any],
    output_dir: Optional[str] = None,
    limit: Optional[int] = None,
    timeout: int = DEFAULT_TIMEOUT,
    delay: float = DEFAULT_DELAY,
    jitter: float = DEFAULT_JITTER,
    max_retries: int = DEFAULT_MAX_RETRIES,
    force: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
) -> Dict[str, Any]:
    """Download all or limited gallery images for a property into output_dir."""
    slug = property_data.get("slug", "property")
    target_dir = output_dir or os.path.join(DEFAULT_OUTPUT_ROOT, slug)
    os.makedirs(target_dir, exist_ok=True)

    images = property_data.get("images", [])
    if limit and limit > 0:
        images = images[:limit]

    total = len(images)
    downloaded = 0
    cached = 0
    failed = 0
    total_bytes = 0
    start_time = time.time()

    print("=" * 68)
    print(f" 📥 Downloading Images: {property_data.get('name', slug)} (ID: {property_data.get('property_id')})")
    print(f" 📁 Destination:        {target_dir}/")
    print(f" 🎯 Images to process:  {total}")
    print(f" ⏱️  Pacing:             {delay:.1f}s delay (+/- {jitter:.1f}s jitter), {timeout}s timeout")
    print("=" * 68)

    for idx, item in enumerate(images, 1):
        url = item["url"]
        filename = item.get("filename") or f"{idx:03d}.jpg"
        dest_path = os.path.join(target_dir, filename)

        # Check existing cached file
        if not force and os.path.exists(dest_path) and os.path.getsize(dest_path) > 5000:
            sz = os.path.getsize(dest_path)
            total_bytes += sz
            cached += 1
            print(f" [{idx:02d}/{total:02d}] ⏭️  [Cached] {filename} ({sz/1024:.1f} KB)")
            continue

        res = download_single_image(
            url=url,
            output_path=dest_path,
            timeout=timeout,
            max_retries=max_retries,
            user_agent=user_agent,
        )

        if res["success"]:
            downloaded += 1
            total_bytes += res["bytes"]
            sz_kb = res["bytes"] / 1024
            print(f" [{idx:02d}/{total:02d}] ✓  {filename} ({sz_kb:.1f} KB)")
        else:
            failed += 1
            print(f" [{idx:02d}/{total:02d}] ✗  {filename} -> Error: {res['error']}")

        # Polite sleep between requests if there are more items
        if idx < total:
            sleep_sec = max(0.1, delay + random.uniform(-jitter, jitter))
            time.sleep(sleep_sec)

    elapsed = time.time() - start_time
    print("=" * 68)
    print(f" 🎉 Completed in {elapsed:.1f}s")
    print(f"    • Newly downloaded: {downloaded}")
    print(f"    • Already cached:   {cached}")
    print(f"    • Failed:           {failed}")
    print(f"    • Total size:       {total_bytes / (1024 * 1024):.2f} MB")
    print("=" * 68)

    return {
        "property_id": property_data.get("property_id"),
        "slug": slug,
        "total_requested": total,
        "downloaded": downloaded,
        "cached": cached,
        "failed": failed,
        "total_bytes": total_bytes,
        "elapsed_seconds": elapsed,
        "target_dir": target_dir,
    }


def main():
    parser = argparse.ArgumentParser(description="Download property gallery images with graceful timeouts and polite pacing.")
    parser.add_argument("property", help="HTML file path, JSON manifest, property slug, or ID (e.g. 'html/benecko-chalupa-pronajmuti-hribek-o358.html' or 'o358')")
    parser.add_argument("--html-dir", "-d", default="html", help="Directory containing HTML files (default: 'html')")
    parser.add_argument("--output-dir", "-o", default=None, help="Custom output directory (default: images/<slug>/)")
    parser.add_argument("--limit", "-l", type=int, default=None, help="Download at most N images (useful for quick testing)")
    parser.add_argument("--timeout", "-t", type=int, default=DEFAULT_TIMEOUT, help=f"Timeout per image in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Base delay between downloads in seconds (default: {DEFAULT_DELAY})")
    parser.add_argument("--jitter", type=float, default=DEFAULT_JITTER, help=f"Random jitter added to delay (default: {DEFAULT_JITTER})")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help=f"Max retry attempts on error (default: {DEFAULT_MAX_RETRIES})")
    parser.add_argument("--force", "-f", action="store_true", help="Re-download already cached images")
    parser.add_argument("--user-agent", "-u", default=DEFAULT_USER_AGENT, help="Browser User-Agent header")
    args = parser.parse_args()

    # Load property data
    if args.property.endswith(".json") and os.path.isfile(args.property):
        with open(args.property, "r", encoding="utf-8") as fh:
            prop_data = json.load(fh)
    else:
        try:
            html_file = resolve_html_file(args.property, args.html_dir)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        with open(html_file, "r", encoding="utf-8", errors="ignore") as fh:
            prop_data = extract_property_images(fh.read(), source_filename=html_file)

    download_property_images(
        property_data=prop_data,
        output_dir=args.output_dir,
        limit=args.limit,
        timeout=args.timeout,
        delay=args.delay,
        jitter=args.jitter,
        max_retries=args.max_retries,
        force=args.force,
        user_agent=args.user_agent,
    )


if __name__ == "__main__":
    main()
