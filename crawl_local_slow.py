import argparse
import datetime
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
DEFAULT_OUTPUT_DIR = "html"
USER_DATA_DIR = os.path.expanduser("~/.config/e_chalupy_crawler_profile")
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
    if not os.path.exists(path):
        raise FileNotFoundError(f"URL file '{path}' not found.")
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]


def parse_args():
    parser = argparse.ArgumentParser(description="Ultra-slow local crawler simulating natural human browsing.")
    parser.add_argument("--input", "-i", default=DEFAULT_INPUT, help=f"Input URL file (default: {DEFAULT_INPUT})")
    parser.add_argument("--output-dir", "-o", default=DEFAULT_OUTPUT_DIR, help=f"Output HTML directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--limit", "-l", type=int, default=50, help="Maximum number of pages to download in this run (default: 50)")
    parser.add_argument("--min-sleep", type=float, default=30.0, help="Minimum sleep between requests in seconds (default: 30.0)")
    parser.add_argument("--max-sleep", type=float, default=300.0, help="Maximum sleep between requests in seconds (default: 300.0)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    return parser.parse_args()


def solve_turnstile_if_needed(page, max_wait=180):
    for i in range(max_wait):
        title = page.title()
        if "Just a moment" not in title and "Security" not in title and len(title) > 0:
            return True
        try:
            iframe = page.locator('iframe[src*="challenges.cloudflare.com"]').first
            if iframe.is_visible():
                box = iframe.bounding_box()
                if box:
                    page.mouse.click(box['x'] + 30, box['y'] + 30)
        except Exception:
            pass
        time.sleep(1.0)
        if i > 0 and i % 15 == 0:
            print(f"       Waiting for Cloudflare verification... ({i}s / {max_wait}s)", flush=True)
    return "Just a moment" not in page.title()


def human_scroll(page):
    """Simulate realistic human scrolling behavior."""
    try:
        total_height = page.evaluate("() => document.body.scrollHeight")
        scroll_steps = random.randint(2, 4)
        for _ in range(scroll_steps):
            scroll_y = random.randint(200, min(800, total_height))
            page.evaluate(f"window.scrollBy(0, {scroll_y})")
            time.sleep(random.uniform(0.5, 1.5))
    except Exception:
        pass


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    all_urls = load_urls(args.input)
    target_urls = all_urls[:args.limit] if args.limit else all_urls
    total = len(target_urls)

    print(f"============================================================")
    print(f" 🏡 Ultra-Polite Human-Simulated Crawler")
    print(f"============================================================")
    print(f"Target count:       {total} pages (Limit: {args.limit})")
    print(f"Source URLs:        {args.input}")
    print(f"Destination:        {args.output_dir}/")
    print(f"Sleep interval:     {args.min_sleep:.0f}s – {args.max_sleep:.0f}s ({args.min_sleep/60:.1f} – {args.max_sleep/60:.1f} minutes)")
    print(f"Browser profile:    {USER_DATA_DIR}")
    print(f"============================================================\n", flush=True)

    downloaded = 0
    skipped = 0
    failed = 0

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="chrome",
            headless=args.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
            ],
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="cs-CZ",
            timezone_id="Europe/Prague",
        )
        page = context.new_page()
        stealth = Stealth()
        stealth.apply_stealth_sync(page)

        for idx, url in enumerate(target_urls, 1):
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            filename = url_to_filename(url)
            filepath = os.path.join(args.output_dir, filename)

            # Check existing cache
            if os.path.exists(filepath) and os.path.getsize(filepath) > 15000:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if "Just a moment" not in content:
                    skipped += 1
                    print(f"[{now_str}] [{idx:2d}/{total}] Cached: {filename} (Total downloaded: {downloaded}, Cached: {skipped})", flush=True)
                    continue

            print(f"[{now_str}] [{idx:2d}/{total}] Navigating to: {url} ...", flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # First navigation allows time for human solve if needed
                max_wait = 180 if idx == 1 else 30
                solved = solve_turnstile_if_needed(page, max_wait=max_wait)

                # Simulate human reading/scrolling
                time.sleep(random.uniform(2.0, 4.0))
                human_scroll(page)
                time.sleep(random.uniform(1.0, 2.0))

                html = page.content()
                if "Just a moment" in page.title() or len(html) < 15000:
                    print(f"  ⚠️ Challenge triggered or incomplete page ({len(html)} bytes). Cooling down for 3 minutes...", flush=True)
                    failed += 1
                    time.sleep(180)
                else:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(html)
                    downloaded += 1
                    soup = BeautifulSoup(html, "html.parser")
                    h1_text = soup.find("h1").text.strip() if soup.find("h1") else "Unknown"
                    print(f"  ✓ Saved '{h1_text}' -> {filename} ({len(html):,} bytes). Progress: [{idx}/{total}]", flush=True)

            except Exception as e:
                print(f"  ✗ Error fetching {url}: {e}", flush=True)
                failed += 1

            # Ultra-slow polite sleep between 30s and 300s
            if idx < total:
                sleep_seconds = random.uniform(args.min_sleep, args.max_sleep)
                sleep_min = sleep_seconds / 60.0
                next_time = datetime.datetime.now() + datetime.timedelta(seconds=sleep_seconds)
                print(f"  ⏳ Sleeping for {sleep_seconds:.1f}s ({sleep_min:.1f} min). Next request at ~{next_time.strftime('%H:%M:%S')}...\n", flush=True)
                time.sleep(sleep_seconds)

        context.close()

    print(f"\n============================================================")
    print(f" 🎉 Crawl Run Finished!")
    print(f"============================================================")
    print(f"Total Targets:      {total}")
    print(f"New Downloads:      {downloaded}")
    print(f"Cached (Skipped):   {skipped}")
    print(f"Failed:             {failed}")
    print(f"HTML Directory:     {args.output_dir}/")
    print(f"============================================================")


if __name__ == "__main__":
    main()
