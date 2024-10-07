import requests
from bs4 import BeautifulSoup
from typing import Set, Dict, Any
import logging
import re
import json

MAX_REGION_ID = 100


def get_links_in_region(region: int, capacity: str = 18, rooms: int = 2) -> Set[str]:
    urls = set()
    response = requests.post("https://www.e-chalupy.cz/hledam/#zalozka_prehled",
                             data={"fkapacita": str(capacity),
                                   "fpokoje": str(rooms),
                                   "ftyp": "0",
                                   "fid_oblasti": str(region),
                                   "furl_okres": "0",
                                   "fid_obec": "0",
                                   "finternet": "",
                                   "hledej_podrobne": "HLEDEJ",
                                   })
    logging.info(f"status {response.status_code}")
    soup = BeautifulSoup(response.text, 'html.parser')
    results = soup.find(id="vysledky_hledani")
    if not results:
        return urls
    for prop in results.find_all(class_="pl"):
        for link in prop.find("h3").find_all("a"):
            urls.add(link.get("href"))
    logging.info(f"found {len(urls)} at {region}")
    return urls


def get_urls() -> Set[str]:
    property_urls = set()
    for region in range(1, MAX_REGION_ID):
        # filter out regions (not ending with .php)
        property_urls |= set(filter(lambda x: x.endswith(".php"), get_links_in_region(region)))
    logging.info(f"total found {len(property_urls)}")
    return property_urls


def clean(s: str) -> str:
    return s.replace('\r', '').replace('\n', '')


def get_property_info(url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(requests.get(url).text, 'html.parser')
    prop = soup.find(class_="chata")
    capacity = re.search("(?:\d*\saž\s)?(\d+)\sosob(?:\s\|\s(\d+)?)?", clean(prop.find(id="kapacita").text))
    contact = prop.find(id="kontakty")
    logging.info(url)
    gps = re.search("GPS .*: (\d+.\d+)N, (\d+.\d+)E", prop.text)
    rating_match = "Celkové hodnocení:\s+(\d+)%"
    data = {
        "url": url,
        "id": prop.find(id="cislo_o").text,
        "name": prop.find("h1").text,
        "locality": prop.find("h2").text,
        "capacity": capacity.group(1),
        "rooms": capacity.group(2),
        "icons": [i.get("alt") for i in prop.find(id="ikony").find_all()],
        "contact_raw": clean(contact.text),
        "contact_links": [i.get("href") for i in contact.find_all("a")],
        "map_link": prop.find(id="vetsi_mapa").get("href"),
        "distances": [(clean(i.find_all("td")[0].text), clean(i.find_all("td")[1].text)) for i in
                      prop.find(id="dest").find_all("tr")] if prop.find(id="dest") else [],
        "equipment": [j.get("alt") for i in prop.find_all(class_="prehled") for j in i.find_all("img")],
        "ratings": [i.text for i in prop.find_all(class_="recenze")],
        "numeric_ratings": [re.search(rating_match, i.text, re.UNICODE).group(1) for i in
                            prop.find_all(class_="recenze") if re.search(rating_match, i.text, re.UNICODE)],
        "place": clean(prop.find(class_="kamdal").text),
        "pricelist": [clean(i.text) for i in prop.find(id="cenik").find_all("td")] if prop.find(id="cenik") else [],
        "images": [(i.get("title"), i.get("href")) for i in prop.find(id="nahledy").find_all("a")],
        "text": prop.text,
    }
    # TODO there are extra ratings (on the main page there is a random subset), detect it and download them all.
    if gps:
        data.update({
            "GPS": {
                "N": gps.group(1),
                "E": gps.group(2),
            }
        })
    return data


def main():
    # init logger
    logging.getLogger().setLevel(logging.INFO)
    with open("properties.json", "w", encoding="utf-8") as f:
        for link in get_urls():
            f.write(json.dumps(get_property_info(link)) + "\n")


if __name__ == '__main__':
    main()
