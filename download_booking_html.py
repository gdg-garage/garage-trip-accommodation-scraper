#!/usr/bin/env python3
"""
Download Booking.com accommodation detail pages using headless Chrome via Playwright.
Handles AWS WAF challenge on launch, reuses session cookies, respects rate limits,
and caches pages to booking_html/<slug>.html.
"""

import argparse
import os
import random
import sys
import time
from typing import List, Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


DEFAULT_URLS_FILE = "booking_urls_20_40.txt"
DEFAULT_OUTPUT_DIR = "booking_html"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


def url_to_slug(url: str) -> str:
    path = url.split("?")[0].rstrip("/")
    slug = path.split("/")[-1]
    if slug.endswith(".html"):
        slug = slug[:-5]
    for lang in [".en-gb", ".cs", ".en-us", ".de"]:
        if slug.endswith(lang):
            slug = slug[:-len(lang)]
    return slug


def is_valid_cache(file_path: str) -> bool:
    if not os.path.exists(file_path):
        return False
    if os.path.getsize(file_path) < 30000:
        return False
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            snippet = f.read(1500)
            if "challenge.js" in snippet or "awsWafCookieDomainList" in snippet:
                return False
            if "<title></title>" in snippet:
                return False
    except Exception:
        return False
    return True


def download_pages(urls: List[str], output_dir: str, limit: Optional[int] = None, delay: float = 1.0):
    os.makedirs(output_dir, exist_ok=True)

    pending = []
    for u in urls:
        slug = url_to_slug(u)
        fp = os.path.join(output_dir, f"{slug}.html")
        if not is_valid_cache(fp):
            pending.append((u, slug, fp))

    print(f"Total target URLs: {len(urls)}")
    print(f"Already cached: {len(urls) - len(pending)}")
    print(f"Pending download: {len(pending)}")

    if limit and limit > 0:
        pending = pending[:limit]
        print(f"Limiting to first {len(pending)} pending downloads.")

    if not pending:
        print("All pages are already downloaded and cached!")
        return

    print("\nStarting Playwright with Chrome...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")

        # Solve challenge on first target
        first_url, first_slug, first_fp = pending[0]
        print(f"\n[1/{len(pending)}] Initializing session & clearing WAF: {first_slug}...")
        t0 = time.time()
        try:
            page.goto(first_url, timeout=35000)
            page.wait_for_timeout(6500)
            html = page.content()
            if len(html) > 50000 and "challenge.js" not in html[:2000]:
                with open(first_fp, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  ✓ Saved {first_slug}.html ({len(html):,} bytes) in {time.time()-t0:.2f}s")
            else:
                print(f"  ⚠ WAF challenge took longer, retrying 5s wait...")
                page.wait_for_timeout(5000)
                html = page.content()
                with open(first_fp, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  ✓ Saved {first_slug}.html ({len(html):,} bytes)")
        except Exception as e:
            print(f"  ✗ Failed initial page: {e}")

        # Download remaining pages
        for idx, (u, slug, fp) in enumerate(pending[1:], 2):
            jitter = random.uniform(0.7, 1.6)
            time.sleep(delay * jitter)
            t_start = time.time()
            success = False
            for attempt in range(3):
                try:
                    page.goto(u, wait_until="domcontentloaded", timeout=25000)
                    html = page.content()
                    if len(html) < 30000 or "challenge.js" in html[:2000]:
                        time.sleep(3.0)
                        html = page.content()
                    if len(html) > 30000:
                        with open(fp, "w", encoding="utf-8") as f:
                            f.write(html)
                        elapsed = time.time() - t_start
                        print(f"[{idx}/{len(pending)}] ✓ {slug} ({len(html):,} bytes) in {elapsed:.2f}s")
                        success = True
                        break
                except Exception as e:
                    print(f"[{idx}/{len(pending)}] ⚠ Attempt {attempt+1} error for {slug}: {e}")
                    time.sleep(2.0)

            if not success:
                print(f"[{idx}/{len(pending)}] ✗ Failed after 3 attempts: {slug}")

        browser.close()
    print("\nDownload batch completed!")


def main():
    parser = argparse.ArgumentParser(description="Download Booking detail pages with Playwright stealth")
    parser.add_argument("--urls", "-u", default=DEFAULT_URLS_FILE, help="URLs file path")
    parser.add_argument("--output-dir", "-o", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--limit", "-l", type=int, default=None, help="Max pages to download")
    parser.add_argument("--delay", "-d", type=float, default=1.0, help="Base delay between downloads")
    args = parser.parse_args()

    if not os.path.exists(args.urls):
        print(f"Error: URLs file {args.urls} not found!")
        sys.exit(1)

    with open(args.urls, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    download_pages(urls, args.output_dir, limit=args.limit, delay=args.delay)


if __name__ == "__main__":
    main()
