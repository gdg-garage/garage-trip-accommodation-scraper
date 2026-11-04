#!/usr/bin/env python3
"""
Download gallery images for properties missing local photos.

Supports:
- Cloudflare clearance cookie via --cf-clearance, --cookie, --session-file, or CF_CLEARANCE env var
- Top candidates only (--top-only, default) or all properties (--all)
- Targeted single property (--listing <id_or_name>)
- Resumable (skips already downloaded files)
- Automatic resync via sync_and_update_photos.py upon completion
"""

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional, Tuple
from download_html import solve_cloudflare_challenge

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

DEFAULT_DATA_FILE = "data/missing_property_images_urls.json"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def load_cookie_dict(cookie_str: str) -> Dict[str, str]:
    cookies = {}
    for part in cookie_str.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k] = v
    return cookies


def is_valid_image(data: bytes) -> bool:
    if len(data) < 500:
        return False
    if data.startswith(b"\xff\xd8\xff"): # JPEG
        return True
    if data.startswith(b"\x89PNG\r\n\x1a\n"): # PNG
        return True
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]: # WebP
        return True
    return False


def download_image(url: str, dest_path: str, session: Any = None, headers: Dict[str, str] = None, timeout: int = 15, session_file: str = ".cf_session.json") -> Tuple[bool, bool]:
    """Returns (success, is_challenge)."""
    try:
        if session is not None:
            r = session.get(url, timeout=timeout)
            is_challenge = r.status_code in (403, 429) or (r.content and b"Just a moment..." in r.content[:1000])
            if r.status_code == 200 and is_valid_image(r.content):
                tmp = dest_path + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(r.content)
                os.replace(tmp, dest_path)
                return True, False
            else:
                return False, is_challenge
        else:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read()
                if resp.status == 200 and is_valid_image(content):
                    tmp = dest_path + ".tmp"
                    with open(tmp, "wb") as f:
                        f.write(content)
                    os.replace(tmp, dest_path)
                    return True, False
                return False, False
    except urllib.error.HTTPError as e:
        return False, e.code in (403, 429)
    except Exception:
        return False, False


def main():
    parser = argparse.ArgumentParser(description="Download missing accommodation images.")
    parser.add_argument("--cf-clearance", help="cf_clearance cookie value")
    parser.add_argument("--cookie", help="Full Cookie header string (e.g. 'cf_clearance=...; ...')")
    parser.add_argument("--session-file", default=".cf_session.json", help="Path to session JSON file")
    parser.add_argument("--all", action="store_true", help="Download all 37 properties including disqualified (default: eligible top candidates only)")
    parser.add_argument("--listing", help="Download only for a specific listing ID or name (e.g. '22293' or 'Termix')")
    parser.add_argument("--data-file", default=DEFAULT_DATA_FILE, help="Path to missing_property_images_urls.json")
    parser.add_argument("--limit-per-property", type=int, default=None, help="Limit number of photos to download per property")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay in seconds between image downloads")
    parser.add_argument("--no-sync", action="store_true", help="Do not trigger sync_and_update_photos.py when done")

    args = parser.parse_args()

    if not os.path.exists(args.data_file):
        print(f"Error: {args.data_file} not found. Run export_missing_photos_urls.py first.")
        sys.exit(1)

    with open(args.data_file, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    properties = catalog.get("properties", [])
    if not args.all:
        properties = [p for p in properties if p.get("is_eligible")]

    if args.listing:
        target = args.listing.lower()
        properties = [p for p in properties if target in p.get("listing", "").lower() or target in p.get("name", "").lower() or target in str(p.get("property_id", "")).lower()]

    if not properties:
        print("No matching properties found to download.")
        sys.exit(0)

    # Prepare cookies and headers
    cookies = {}
    ua = DEFAULT_USER_AGENT

    # Check session file
    if os.path.exists(args.session_file):
        try:
            with open(args.session_file, "r", encoding="utf-8") as f:
                s_data = json.load(f)
                cookies.update(s_data.get("cookies", {}))
                if s_data.get("user_agent"):
                    ua = s_data["user_agent"]
        except Exception:
            pass

    # Check CLI or ENV clearance
    cf_token = args.cf_clearance or os.environ.get("CF_CLEARANCE")
    if cf_token:
        cookies["cf_clearance"] = cf_token.strip()

    if args.cookie:
        cookies.update(load_cookie_dict(args.cookie))

    headers = {
        "User-Agent": ua,
        "Referer": "https://www.e-chalupy.cz/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    }

    session = None
    if HAS_CURL_CFFI:
        session = cffi_requests.Session(impersonate="chrome120")
        session.headers.update(headers)
        session.cookies.update(cookies)
    elif cookies:
        cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        headers["Cookie"] = cookie_header

    print("=" * 72)
    print(f" 🚀 Downloading Photos for {len(properties)} Properties")
    print(f" 🍪 Cloudflare Clearance:     {'Loaded' if 'cf_clearance' in cookies else 'None (downloads may receive 403)'}")
    print(f" ⏱️  Pacing per Photo:         {args.delay:.1f}s")
    print("=" * 72)

    total_downloaded = 0
    total_cached = 0
    total_failed = 0
    challenge_attempts = 0

    for p_idx, prop in enumerate(properties, 1):
        name = prop.get("name", "Unknown")
        listing = prop.get("listing", "")
        target_dir = prop.get("target_directory", f"images/prop_{p_idx}")
        images = prop.get("images_detailed", [])
        if args.limit_per_property:
            images = images[:args.limit_per_property]

        os.makedirs(target_dir, exist_ok=True)
        print(f"\n[{p_idx}/{len(properties)}] {listing} - {name} ({len(images)} photos) -> {target_dir}")

        prop_downloaded = 0
        prop_failed = 0
        prop_cached = 0

        for img in images:
            dest = img["target_path"]
            url = img["url"]

            if os.path.exists(dest) and os.path.getsize(dest) > 1000:
                prop_cached += 1
                total_cached += 1
                continue

            success, is_challenge = download_image(url, dest, session=session, headers=headers)
            if not success and is_challenge and HAS_CURL_CFFI and challenge_attempts < 3:
                challenge_attempts += 1
                print(f"\n⚠️ Cloudflare challenge detected on {url}. Attempting to solve challenge (attempt {challenge_attempts}/3)...")
                solved = solve_cloudflare_challenge(url, session_file=args.session_file)
                if solved and os.path.exists(args.session_file):
                    try:
                        with open(args.session_file, "r", encoding="utf-8") as f:
                            s_data = json.load(f)
                        cf_cookies = s_data.get("cookies", {})
                        cf_ua = s_data.get("user_agent", DEFAULT_USER_AGENT)
                        headers["User-Agent"] = cf_ua
                        session = cffi_requests.Session(impersonate="chrome120")
                        session.headers.update(headers)
                        session.cookies.update(cf_cookies)
                        print("✓ Session refreshed, retrying download...")
                        success, _ = download_image(url, dest, session=session, headers=headers)
                    except Exception as e:
                        print(f"Failed to reload session: {e}")

            if success:
                prop_downloaded += 1
                total_downloaded += 1
                sys.stdout.write(".")
                sys.stdout.flush()
            else:
                prop_failed += 1
                total_failed += 1
                sys.stdout.write("x")
                sys.stdout.flush()

            time.sleep(args.delay)

        print(f" [Done: {prop_downloaded} new, {prop_cached} cached, {prop_failed} failed]")

        # Polite wait between properties if we downloaded new files
        if prop_downloaded > 0 and p_idx < len(properties):
            wait = random.uniform(2.0, 5.0)
            time.sleep(wait)

    print("\n" + "=" * 72)
    print(f" 🏁 Finished: {total_downloaded} downloaded, {total_cached} cached, {total_failed} failed")
    print("=" * 72)

    if total_downloaded > 0 and not args.no_sync:
        print("\n🔄 Resyncing candidate datasets with newly downloaded photos...")
        try:
            import subprocess
            subprocess.run([sys.executable, "sync_and_update_photos.py"], check=True)
            print("✓ Candidate datasets resynced successfully!")
        except Exception as e:
            print(f"Notice: sync_and_update_photos.py failed: {e}")


if __name__ == "__main__":
    main()
