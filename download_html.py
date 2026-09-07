import argparse
import hashlib
import json
import logging
import os
import random
import re
import time
import urllib.parse
from typing import List, Optional, Tuple, Dict, Any

# Try importing curl_cffi for Cloudflare TLS impersonation; fall back to standard requests if missing
try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests as cffi_requests
    HAS_CURL_CFFI = False

DEFAULT_INPUT_FILE = "urls.txt"
DEFAULT_OUTPUT_DIR = "html"
DEFAULT_SESSION_FILE = ".cf_session.json"
DEFAULT_DELAY = 0.5
DEFAULT_JITTER = 0.3
DEFAULT_TIMEOUT = 15
DEFAULT_MAX_RETRIES = 3
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
CHALLENGE_TITLE = "Just a moment..."


def url_to_filename(url: str) -> str:
    """
    Generate a clean, deterministic filename for a given property URL.
    Example: https://www.e-chalupy.cz/cesky_raj/chalupa-pecka-1234.php -> cesky_raj_chalupa-pecka-1234.html
    """
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip("/")
    if path.endswith(".php"):
        path = path[:-4]
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", path)
    if not slug:
        slug = hashlib.md5(url.encode("utf-8")).hexdigest()
    return f"{slug}.html"


def load_urls(input_path: str) -> List[str]:
    """Load URL list from text file or JSON."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input URLs file '{input_path}' not found. Run scrape_links.py first.")
    
    if input_path.endswith(".json"):
        with open(input_path, "r", encoding="utf-8") as f:
            urls = json.load(f)
    else:
        with open(input_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    return sorted(list(set(urls)))


def get_shard_urls(urls: List[str], total_shards: int, shard_id: int) -> List[str]:
    """Return the slice/partition of URLs assigned to this worker shard."""
    if total_shards <= 1:
        return urls
    if shard_id < 0 or shard_id >= total_shards:
        raise ValueError(f"shard-id ({shard_id}) must be in range [0, {total_shards - 1}]")
    return [url for i, url in enumerate(urls) if i % total_shards == shard_id]


def load_cached_session(session_file: str) -> Optional[Dict[str, Any]]:
    """Load cached cookies and user agent from session file."""
    if os.path.exists(session_file):
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "cookies" in data:
                    return data
        except Exception as e:
            logging.debug(f"Could not load session cache from {session_file}: {e}")
    return None


def save_cached_session(session_file: str, cookies: Dict[str, str], user_agent: str):
    """Persist cookies and user agent to session file."""
    try:
        data = {
            "cookies": cookies,
            "user_agent": user_agent,
            "saved_at": time.time(),
        }
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logging.debug(f"Saved session cache to {session_file}")
    except Exception as e:
        logging.warning(f"Could not save session cache to {session_file}: {e}")


def solve_cloudflare_challenge(
    target_url: str,
    session_file: str = DEFAULT_SESSION_FILE,
    headless: bool = False,
    timeout: int = 25,
) -> Tuple[Dict[str, str], str]:
    """
    Launch Playwright browser to solve Cloudflare Turnstile challenge and extract cf_clearance session.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright is not installed. Run 'pip install playwright' or pass a manual token via "
            "--cf-clearance <token> or CF_CLEARANCE env variable."
        )

    print("\n--- Solving Cloudflare Challenge ---")
    print(f"Opening browser to acquire cf_clearance session for {target_url}...")

    cookies: Dict[str, str] = {}
    user_agent = DEFAULT_USER_AGENT

    with sync_playwright() as p:
        browser = None
        # Try system Google Chrome first, fallback to bundled Chromium
        try:
            browser = p.chromium.launch(
                channel="chrome",
                headless=headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
        except Exception:
            try:
                browser = p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to launch browser: {e}. "
                    "Make sure Chrome or Chromium is installed (run 'playwright install chromium')."
                )

        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=timeout * 1000)
        except Exception as e:
            logging.debug(f"Initial navigation notice: {e}")

        # Poll and interact with challenge until solved or timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(1)
            title = page.title()
            
            # Check if solved by title
            if title and "Just a moment" not in title:
                break

            # Try clicking turnstile challenge frame
            for f in page.frames:
                if "challenges.cloudflare.com" in f.url:
                    try:
                        f.locator("body").click(position={"x": 30, "y": 30}, timeout=1000)
                    except Exception:
                        pass

        # Give 1-2 seconds for cookies to finalize
        time.sleep(1.5)
        cookies_list = context.cookies()
        try:
            user_agent = page.evaluate("() => navigator.userAgent") or DEFAULT_USER_AGENT
        except Exception:
            pass
        browser.close()

    cookies = {c["name"]: c["value"] for c in cookies_list}
    if "cf_clearance" in cookies:
        print(f"Cloudflare cf_clearance acquired successfully! (Token: {cookies['cf_clearance'][:15]}...)\n")
        save_cached_session(session_file, cookies, user_agent)
    else:
        logging.warning("Browser completed but cf_clearance cookie was not found. Capturing all available cookies.")

    return cookies, user_agent


def get_authenticated_session(
    cf_clearance: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_file: str = DEFAULT_SESSION_FILE,
    no_browser: bool = False,
    headless: bool = False,
    target_url: str = "https://www.e-chalupy.cz/",
    force_refresh: bool = False,
) -> Any:
    """
    Build and return an HTTP session configured with Cloudflare clearance tokens and headers.
    """
    cookies: Dict[str, str] = {}
    ua = user_agent or os.environ.get("USER_AGENT") or DEFAULT_USER_AGENT

    # 1. Check direct argument / env variable
    env_clearance = cf_clearance or os.environ.get("CF_CLEARANCE")
    if env_clearance:
        cookies["cf_clearance"] = env_clearance.strip()

    # 2. Check cached session file if not forcing refresh and no explicit token given
    if not env_clearance and not force_refresh:
        cached = load_cached_session(session_file)
        if cached:
            cookies.update(cached.get("cookies", {}))
            if "user_agent" in cached and not user_agent:
                ua = cached["user_agent"]

    # 3. If still missing cf_clearance and browser solver is allowed, solve via Playwright
    if "cf_clearance" not in cookies and not no_browser:
        solved_cookies, solved_ua = solve_cloudflare_challenge(
            target_url=target_url,
            session_file=session_file,
            headless=headless,
        )
        cookies.update(solved_cookies)
        ua = solved_ua

    if "cf_clearance" not in cookies and no_browser:
        logging.warning(
            "No cf_clearance token provided and --no-browser was specified. "
            "Requests may be blocked by Cloudflare (HTTP 403). Pass --cf-clearance <token> or set CF_CLEARANCE env var."
        )

    # Initialize session
    if HAS_CURL_CFFI:
        session = cffi_requests.Session(impersonate="chrome120")
    else:
        session = cffi_requests.Session()

    session.headers.update({"User-Agent": ua})
    session.cookies.update(cookies)
    return session


def download_page_with_retry(
    url: str,
    session: Any,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Tuple[Optional[str], int, bool]:
    """
    Download single HTML page with retry and exponential backoff.
    Returns (html_content, status_code, is_challenge_blocked).
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            
            # Check for Cloudflare challenge in body or status
            is_cf_blocked = response.status_code == 403 or (
                response.text and CHALLENGE_TITLE in response.text[:2000]
            )

            if is_cf_blocked:
                logging.warning(f"Cloudflare challenge encountered on {url} (status: {response.status_code}).")
                return None, response.status_code, True

            if response.status_code == 200:
                # Ensure correct encoding (e-chalupy typically uses windows-1250 or utf-8)
                if getattr(response, "encoding", None) in (None, "iso-8859-1", "ISO-8859-1"):
                    apparent = getattr(response, "apparent_encoding", None)
                    response.encoding = apparent or "utf-8"
                return response.text, response.status_code, False
            elif response.status_code in (429, 503, 502):
                wait_time = 2 ** attempt + random.uniform(0.5, 1.5)
                logging.warning(f"HTTP {response.status_code} for {url}. Backing off for {wait_time:.1f}s (attempt {attempt}/{max_retries})")
                time.sleep(wait_time)
            elif response.status_code == 404:
                logging.warning(f"HTTP 404 Not Found for {url}. Skipping.")
                return None, response.status_code, False
            else:
                logging.warning(f"Unexpected status {response.status_code} for {url} on attempt {attempt}")
        except Exception as e:
            wait_time = 2 ** attempt
            logging.warning(f"Network error downloading {url}: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    logging.error(f"Failed to download {url} after {max_retries} attempts.")
    return None, 0, False


def parse_args():
    parser = argparse.ArgumentParser(description="Step 2: Download raw HTML pages for all scraped URLs with distributed sharding and Cloudflare bypass.")
    parser.add_argument("--input", "-i", type=str, default=DEFAULT_INPUT_FILE, help=f"Input URL list file (default: {DEFAULT_INPUT_FILE})")
    parser.add_argument("--output-dir", "-o", type=str, default=DEFAULT_OUTPUT_DIR, help=f"Output directory for HTML files (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--total-shards", "-n", type=int, default=1, help="Total number of distributed worker shards (default: 1)")
    parser.add_argument("--shard-id", "-s", type=int, default=0, help="Zero-indexed shard ID for this worker (0..total_shards-1)")
    parser.add_argument("--delay", type=float, default=5.0, help="Base delay in seconds between requests (default: 5.0s)")
    parser.add_argument("--delay-minutes", type=float, default=None, help="Base delay in minutes between requests (e.g. 1.5 for 90s)")
    parser.add_argument("--jitter", type=float, default=3.0, help="Random extra jitter in seconds added to delay (default: 3.0s)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"HTTP request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of pages to download in this run")
    parser.add_argument("--force", action="store_true", help="Overwrite existing cached HTML files instead of skipping")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")

    # Cloudflare session options
    parser.add_argument("--cf-clearance", type=str, default=None, help="Manual Cloudflare cf_clearance cookie value (or set CF_CLEARANCE env var)")
    parser.add_argument("--user-agent", type=str, default=None, help="User-Agent string matching cf_clearance (or set USER_AGENT env var)")
    parser.add_argument("--session-file", type=str, default=DEFAULT_SESSION_FILE, help=f"Path to session cache file (default: {DEFAULT_SESSION_FILE})")
    parser.add_argument("--no-browser", action="store_true", help="Do not attempt to open a browser for Cloudflare challenge solving (pure HTTP mode)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode when solving challenge")
    parser.add_argument("--force-auth", action="store_true", help="Force re-running Cloudflare browser solver even if session cache exists")

    return parser.parse_args()


def main():
    args = parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    base_delay = (args.delay_minutes * 60.0) if args.delay_minutes is not None else args.delay

    os.makedirs(args.output_dir, exist_ok=True)

    all_urls = load_urls(args.input)
    shard_urls = get_shard_urls(all_urls, args.total_shards, args.shard_id)

    if args.limit:
        shard_urls = shard_urls[:args.limit]

    total_count = len(shard_urls)
    print(f"--- Ultra-Polite HTML Downloader ---")
    print(f"Total URLs in dataset: {len(all_urls)}")
    print(f"Assigned shard: {args.shard_id + 1}/{args.total_shards} ({total_count} URLs assigned to this worker)")
    print(f"Output directory: {args.output_dir}/")
    print(f"Engine: {'curl_cffi (Chrome impersonation)' if HAS_CURL_CFFI else 'standard requests'}")
    print(f"Rate limiting: {base_delay:.1f}s base delay + up to {args.jitter:.1f}s random jitter between requests\n")

    # Pick first URL as challenge target if solver is triggered
    first_url = shard_urls[0] if shard_urls else "https://www.e-chalupy.cz/"

    session = get_authenticated_session(
        cf_clearance=args.cf_clearance,
        user_agent=args.user_agent,
        session_file=args.session_file,
        no_browser=args.no_browser,
        headless=args.headless,
        target_url=first_url,
        force_refresh=args.force_auth,
    )

    downloaded = 0
    skipped = 0
    failed = 0

    for idx, url in enumerate(shard_urls, 1):
        filename = url_to_filename(url)
        target_path = os.path.join(args.output_dir, filename)

        # Skip if already downloaded and not empty
        if not args.force and os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            skipped += 1
            if idx % 20 == 0 or idx == total_count:
                print(f"Progress: [{idx}/{total_count}] (Downloaded: {downloaded}, Cached/Skipped: {skipped}, Failed: {failed})")
            continue

        print(f"[{idx}/{total_count}] Downloading {url} ...")
        html_text, status_code, is_blocked = download_page_with_retry(url, session=session, timeout=args.timeout)

        # If blocked by Cloudflare and auto-browser is enabled, attempt automatic session refresh
        if is_blocked:
            print(f"  ⚠️ Encountered Cloudflare challenge or rate limit. Cooling down for 2 minutes...")
            time.sleep(120)
            if not args.no_browser:
                logging.info("Attempting automatic session refresh...")
                session = get_authenticated_session(
                    session_file=args.session_file,
                    no_browser=False,
                    headless=args.headless,
                    target_url=url,
                    force_refresh=True,
                )
                html_text, status_code, is_blocked = download_page_with_retry(url, session=session, timeout=args.timeout)

        if html_text and not is_blocked:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(html_text)
            downloaded += 1
            print(f"  ✓ Saved to {filename} ({len(html_text):,} bytes)")
        else:
            failed += 1
            print(f"  ✗ Failed to download ({status_code})")

        print(f"Progress: [{idx}/{total_count}] (Downloaded: {downloaded}, Cached: {skipped}, Failed: {failed})")

        # Polite rate-limiting sleep
        if idx < total_count:
            sleep_duration = base_delay + random.uniform(0, args.jitter)
            if sleep_duration >= 60:
                print(f"  ⏳ Sleeping for {sleep_duration / 60:.1f} minutes ({sleep_duration:.0f}s) before next request...\n")
            else:
                print(f"  ⏳ Sleeping for {sleep_duration:.1f}s before next request...\n")
            time.sleep(sleep_duration)

    print("\n--- Shard Download Finished ---")
    print(f"Total processed in this shard: {total_count}")
    print(f"New downloads: {downloaded}")
    print(f"Cached (skipped): {skipped}")
    print(f"Failed: {failed}")


if __name__ == '__main__':
    main()


