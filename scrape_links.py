import argparse
import json
import logging
import os
import time
from typing import Set, List, Optional
import requests
from bs4 import BeautifulSoup

DEFAULT_MAX_REGION = 100
DEFAULT_DELAY_SECONDS = 0.5
DEFAULT_OUTPUT_FILE = "urls.txt"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


def get_links_in_region(
    region: int,
    capacity: int = 18,
    rooms: int = 2,
    session: Optional[requests.Session] = None,
    timeout: int = 15,
) -> Set[str]:
    """Scrape accommodation URLs for a given region from e-chalupy.cz search results."""
    urls: Set[str] = set()
    client = session or requests.Session()
    try:
        response = client.post(
            "https://www.e-chalupy.cz/hledam/#zalozka_prehled",
            data={
                "fkapacita": str(capacity),
                "fpokoje": str(rooms),
                "ftyp": "0",
                "fid_oblasti": str(region),
                "furl_okres": "0",
                "fid_obec": "0",
                "finternet": "",
                "hledej_podrobne": "HLEDEJ",
            },
            timeout=timeout,
        )
        logging.debug(f"Region {region} status code: {response.status_code}")
    except requests.RequestException as e:
        logging.warning(f"Error fetching region {region}: {e}")
        return urls

    soup = BeautifulSoup(response.text, 'html.parser')
    results = soup.find(id="vysledky_hledani")
    if not results:
        return urls

    for prop in results.find_all(class_="pl"):
        h3 = prop.find("h3")
        if h3:
            for link in h3.find_all("a"):
                href = link.get("href")
                if href and href.endswith(".php"):
                    if not href.startswith("http"):
                        href = "https://www.e-chalupy.cz/" + href.lstrip("/")
                    urls.add(href)
    return urls


def scrape_all_links(
    max_region: int = DEFAULT_MAX_REGION,
    capacity: int = 18,
    rooms: int = 2,
    delay: float = DEFAULT_DELAY_SECONDS,
    session: Optional[requests.Session] = None,
) -> List[str]:
    """Iterate through regions and collect all unique accommodation URLs."""
    all_urls: Set[str] = set()
    client = session or requests.Session()
    client.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    print(f"Scraping accommodation links across regions 1..{max_region} (capacity >= {capacity}, rooms >= {rooms})...")
    for region in range(1, max_region):
        region_urls = get_links_in_region(
            region=region,
            capacity=capacity,
            rooms=rooms,
            session=client,
        )
        new_count = len(region_urls - all_urls)
        all_urls.update(region_urls)
        logging.info(f"Region {region:02d}: found {len(region_urls)} links (+{new_count} new, total unique: {len(all_urls)})")
        if delay > 0 and region < max_region - 1:
            time.sleep(delay)

    sorted_urls = sorted(list(all_urls))
    print(f"Done! Collected {len(sorted_urls)} total unique accommodation URLs.")
    return sorted_urls


def save_links(urls: List[str], output_path: str, append: bool = False):
    """Save URLs to file (supports .txt or .json format)."""
    existing_urls: Set[str] = set()
    if append and os.path.exists(output_path):
        if output_path.endswith(".json"):
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    existing_urls = set(json.load(f))
            except Exception:
                pass
        else:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_urls = {line.strip() for line in f if line.strip()}

    combined_urls = sorted(list(existing_urls | set(urls)))

    if output_path.endswith(".json"):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(combined_urls, f, indent=2, ensure_ascii=False)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            for url in combined_urls:
                f.write(url + "\n")

    print(f"Saved {len(combined_urls)} URLs to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Step 1: Extract all accommodation URLs from e-chalupy.cz search pages.")
    parser.add_argument("--capacity", type=int, default=18, help="Minimum capacity filter for search (default: 18)")
    parser.add_argument("--rooms", type=int, default=2, help="Minimum rooms filter for search (default: 2)")
    parser.add_argument("--max-region", type=int, default=DEFAULT_MAX_REGION, help=f"Max region ID to scan (default: {DEFAULT_MAX_REGION})")
    parser.add_argument("--output", "-o", type=str, default=DEFAULT_OUTPUT_FILE, help=f"Output file (default: {DEFAULT_OUTPUT_FILE})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help=f"Polite delay between region queries in seconds (default: {DEFAULT_DELAY_SECONDS})")
    parser.add_argument("--append", action="store_true", help="Merge with existing output file instead of overwriting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main():
    args = parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    urls = scrape_all_links(
        max_region=args.max_region,
        capacity=args.capacity,
        rooms=args.rooms,
        delay=args.delay,
    )
    save_links(urls, args.output, append=args.append)


if __name__ == '__main__':
    main()
