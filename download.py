import argparse
import json
import logging
import re
from typing import Set, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

MAX_REGION_ID = 100
DEFAULT_TIMEOUT = 15
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"


def clean(s: Optional[str]) -> str:
    """Clean newlines, carriage returns, and leading/trailing whitespace from string."""
    if s is None:
        return ""
    return s.replace('\r', '').replace('\n', '').strip()


def get_links_in_region(
    region: int,
    capacity: int = 18,
    rooms: int = 2,
    session: Optional[requests.Session] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Set[str]:
    """Fetch all accommodation URLs listed in a specific e-chalupy.cz region."""
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
        logging.info(f"Region {region} status: {response.status_code}")
    except requests.RequestException as e:
        logging.warning(f"Failed to fetch region {region}: {e}")
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
                if href:
                    urls.add(href)
    logging.info(f"Found {len(urls)} properties in region {region}")
    return urls


def get_urls(
    max_region: int = MAX_REGION_ID,
    capacity: int = 18,
    rooms: int = 2,
    session: Optional[requests.Session] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Set[str]:
    """Iterate over all regions and collect unique accommodation property URLs."""
    property_urls: Set[str] = set()
    for region in range(1, max_region):
        # Filter out regions (keep only links ending with .php)
        region_urls = get_links_in_region(
            region=region,
            capacity=capacity,
            rooms=rooms,
            session=session,
            timeout=timeout,
        )
        property_urls |= set(filter(lambda x: x.endswith(".php"), region_urls))
    logging.info(f"Total properties found: {len(property_urls)}")
    return property_urls


def get_property_info(
    url: str,
    session: Optional[requests.Session] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Scrape and parse structured accommodation details from a property URL."""
    client = session or requests.Session()
    logging.info(f"Scraping property: {url}")
    try:
        response = client.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.warning(f"Error fetching {url}: {e}")
        return {"url": url, "error": str(e)}

    soup = BeautifulSoup(response.text, 'html.parser')
    prop = soup.find(class_="chata")
    if not prop:
        return {"url": url, "error": "No .chata container found"}

    kapacita_elem = prop.find(id="kapacita")
    capacity_text = clean(kapacita_elem.text) if kapacita_elem else ""
    capacity_match = re.search(r"(?:\d*\saž\s)?(\d+)\sosob(?:\s\|\s(\d+)?)?", capacity_text)

    capacity_val = capacity_match.group(1) if capacity_match else None
    rooms_val = capacity_match.group(2) if capacity_match else None

    contact_elem = prop.find(id="kontakty")
    contact_raw = clean(contact_elem.text) if contact_elem else ""
    contact_links = [i.get("href") for i in contact_elem.find_all("a") if i.get("href")] if contact_elem else []

    cislo_elem = prop.find(id="cislo_o")
    prop_id = cislo_elem.text.strip() if cislo_elem else ""

    h1_elem = prop.find("h1")
    name = h1_elem.text.strip() if h1_elem else ""

    h2_elem = prop.find("h2")
    locality = h2_elem.text.strip() if h2_elem else ""

    ikony_elem = prop.find(id="ikony")
    icons = [i.get("alt") for i in ikony_elem.find_all() if i.get("alt")] if ikony_elem else []

    vetsi_mapa = prop.find(id="vetsi_mapa")
    map_link = vetsi_mapa.get("href") if vetsi_mapa else ""

    dest_elem = prop.find(id="dest")
    distances = []
    if dest_elem:
        for tr in dest_elem.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 2:
                distances.append((clean(tds[0].text), clean(tds[1].text)))

    equipment = [j.get("alt") for i in prop.find_all(class_="prehled") for j in i.find_all("img") if j.get("alt")]
    ratings = [i.text.strip() for i in prop.find_all(class_="recenze")]

    rating_match_pattern = r"Celkové hodnocení:\s+(\d+)%"
    numeric_ratings = []
    for i in ratings:
        m = re.search(rating_match_pattern, i, re.UNICODE)
        if m:
            numeric_ratings.append(m.group(1))

    kamdal_elem = prop.find(class_="kamdal")
    place = clean(kamdal_elem.text) if kamdal_elem else ""

    cenik_elem = prop.find(id="cenik")
    pricelist = [clean(i.text) for i in cenik_elem.find_all("td")] if cenik_elem else []

    nahledy_elem = prop.find(id="nahledy")
    images = []
    if nahledy_elem:
        for a in nahledy_elem.find_all("a"):
            href = a.get("href")
            if href:
                images.append((a.get("title") or "", href))

    gps_match = re.search(r"GPS .*: (\d+\.\d+)N, (\d+\.\d+)E", prop.text)

    data: Dict[str, Any] = {
        "url": url,
        "id": prop_id,
        "name": name,
        "locality": locality,
        "capacity": capacity_val,
        "rooms": rooms_val,
        "icons": icons,
        "contact_raw": contact_raw,
        "contact_links": contact_links,
        "map_link": map_link,
        "distances": distances,
        "equipment": equipment,
        "ratings": ratings,
        "numeric_ratings": numeric_ratings,
        "place": place,
        "pricelist": pricelist,
        "images": images,
        "text": prop.text,
    }

    if gps_match:
        data["GPS"] = {
            "N": gps_match.group(1),
            "E": gps_match.group(2),
        }

    return data


def parse_args():
    parser = argparse.ArgumentParser(description="Scrape accommodation properties from e-chalupy.cz")
    parser.add_argument("--capacity", type=int, default=18, help="Minimum capacity filter (default: 18)")
    parser.add_argument("--rooms", type=int, default=2, help="Minimum rooms filter (default: 2)")
    parser.add_argument("--max-region", type=int, default=MAX_REGION_ID, help="Maximum region ID to scan (default: 100)")
    parser.add_argument("--output", "-o", type=str, default="properties.json", help="Output JSON lines file (default: properties.json)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of properties to scrape")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds (default: 15)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()


def main():
    args = parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    urls = get_urls(
        max_region=args.max_region,
        capacity=args.capacity,
        rooms=args.rooms,
        session=session,
        timeout=args.timeout,
    )

    if args.limit:
        urls = set(list(urls)[:args.limit])
        logging.info(f"Limited scraping to {len(urls)} properties")

    with open(args.output, "w", encoding="utf-8") as f:
        for idx, link in enumerate(urls, 1):
            prop_data = get_property_info(link, session=session, timeout=args.timeout)
            f.write(json.dumps(prop_data, ensure_ascii=False) + "\n")
            if idx % 10 == 0 or idx == len(urls):
                logging.info(f"Progress: {idx}/{len(urls)} properties scraped")

    logging.info(f"Scraping complete. Results written to {args.output}")


if __name__ == '__main__':
    main()

