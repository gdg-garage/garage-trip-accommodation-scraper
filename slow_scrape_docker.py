import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.parse
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

DEFAULT_INPUT = "urls_whole_object.txt"
DEFAULT_OUTPUT_DIR = "html_whole_object"
DEFAULT_DELAY = 45.0
DEFAULT_JITTER = 20.0
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"


def url_to_filename(url: str) -> str:
    p = urllib.parse.urlparse(url)
    path = p.path.strip("/")
    if path.endswith(".php"):
        path = path[:-4]
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", path)
    if not slug:
        slug = hashlib.md5(url.encode("utf-8")).hexdigest()
    return f"{slug}.html"


def load_urls(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]


def parse_args():
    parser = argparse.ArgumentParser(description="Slow remote scraper for whole object accommodations on docker.tivvit.cz")
    parser.add_argument("--input", "-i", default=DEFAULT_INPUT, help=f"Input URL file (default: {DEFAULT_INPUT})")
    parser.add_argument("--output-dir", "-o", default=DEFAULT_OUTPUT_DIR, help=f"Output HTML directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--delay", "-d", type=float, default=DEFAULT_DELAY, help=f"Base delay in seconds between requests (default: {DEFAULT_DELAY}s)")
    parser.add_argument("--jitter", "-j", type=float, default=DEFAULT_JITTER, help=f"Random jitter in seconds (default: {DEFAULT_JITTER}s)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of downloads for testing")
    return parser.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    urls = load_urls(args.input)
    if args.limit:
        urls = urls[:args.limit]

    total = len(urls)
    print(f"============================================================")
    print(f" 🚀 Remote Slow Scraper starting on docker.tivvit.cz")
    print(f"============================================================")
    print(f"Total URLs to process: {total}")
    print(f"Destination:           {args.output_dir}/")
    print(f"Base delay:            {args.delay:.1f}s (+ up to {args.jitter:.1f}s jitter)\n", flush=True)

    downloaded = 0
    skipped = 0
    failed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="cs-CZ",
            timezone_id="Europe/Prague",
        )
        page = context.new_page()
        stealth = Stealth()
        stealth.apply_stealth_sync(page)

        for idx, url in enumerate(urls, 1):
            filename = url_to_filename(url)
            filepath = os.path.join(args.output_dir, filename)

            if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if "Just a moment" not in content:
                    skipped += 1
                    if idx % 10 == 0 or idx == total:
                        print(f"[{idx:3d}/{total}] Cached: {filename} (Total downloaded: {downloaded}, Cached: {skipped})", flush=True)
                    continue

            print(f"[{idx:3d}/{total}] Fetching: {url} ...", flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3.0)

                # Solve / wait for turnstile if present
                for _ in range(8):
                    title = page.title()
                    if "Just a moment" not in title and "Security" not in title and len(title) > 0:
                        break
                    try:
                        iframe = page.locator('iframe[src*="challenges.cloudflare.com"]').first
                        if iframe.is_visible():
                            box = iframe.bounding_box()
                            if box:
                                page.mouse.click(box['x'] + 30, box['y'] + 30)
                    except Exception:
                        pass
                    time.sleep(1.0)

                html = page.content()
                if "Just a moment" in page.title() or len(html) < 15000:
                    print(f"  ⚠️ Challenge triggered or empty response ({len(html)} bytes). Cooling down for 2 minutes...", flush=True)
                    failed += 1
                    time.sleep(120)
                else:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(html)
                    downloaded += 1
                    print(f"  ✓ Saved {filename} ({len(html):,} bytes). Progress: [{idx}/{total}]", flush=True)

            except Exception as e:
                print(f"  ✗ Error fetching {url}: {e}", flush=True)
                failed += 1

            if idx < total:
                sleep_time = args.delay + random.uniform(0, args.jitter)
                print(f"  ⏳ Sleeping for {sleep_time:.1f}s ({sleep_time/60:.1f} min) before next request...\n", flush=True)
                time.sleep(sleep_time)

        browser.close()

    print(f"\n============================================================")
    print(f" Scraper Finished on docker.tivvit.cz")
    print(f"============================================================")
    print(f"Total:      {total}")
    print(f"Downloaded: {downloaded}")
    print(f"Cached:     {skipped}")
    print(f"Failed:     {failed}")
    print(f"============================================================")


if __name__ == "__main__":
    main()
