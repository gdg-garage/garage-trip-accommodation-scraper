import argparse
import glob
import json
import os
import re
import urllib.parse
from bs4 import BeautifulSoup

DEFAULT_HTML_DIR = "html"
DEFAULT_OUTPUT = "images_manifest.json"
BASE_URL = "https://www.e-chalupy.cz"


def extract_images_from_html(html_text: str) -> list:
    soup = BeautifulSoup(html_text, "html.parser")
    images = []
    seen = set()

    # 1. Look for gallery links (/foto/...)
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if "/foto/" in href and any(href.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".webp", ".png"]):
            full_url = urllib.parse.urljoin(BASE_URL, href)
            title = a.get("title") or a.get("alt") or ""
            if full_url not in seen:
                seen.add(full_url)
                images.append({"url": full_url, "title": title})

    # 2. Look for <img> tags with /foto/
    for img in soup.find_all("img", src=True):
        src = img["src"].strip()
        if "/foto/" in src and any(src.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".webp", ".png"]):
            full_url = urllib.parse.urljoin(BASE_URL, src)
            title = img.get("alt") or img.get("title") or ""
            if full_url not in seen:
                seen.add(full_url)
                images.append({"url": full_url, "title": title})

    return images


def main():
    parser = argparse.ArgumentParser(description="Extract property image gallery URLs from local HTML files.")
    parser.add_argument("--html-dir", "-d", default=DEFAULT_HTML_DIR, help=f"HTML directory (default: {DEFAULT_HTML_DIR})")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT, help=f"Output manifest JSON (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    html_files = sorted(glob.glob(os.path.join(args.html_dir, "*.html")))
    print(f"Scanning {len(html_files)} HTML files in '{args.html_dir}/'...")

    manifest = {}
    total_images = 0

    for f in html_files:
        prop_slug = os.path.basename(f).replace(".html", "")
        with open(f, "r", encoding="utf-8", errors="ignore") as fh:
            imgs = extract_images_from_html(fh.read())
            manifest[prop_slug] = imgs
            total_images += len(imgs)

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    print(f"\n============================================================")
    print(f" 📸 Image Extraction Summary")
    print(f"============================================================")
    print(f"Properties scanned: {len(manifest)}")
    print(f"Total unique images: {total_images:,}")
    print(f"Average per cottage: {total_images/len(manifest):.1f}" if manifest else 0)
    print(f"Saved to:            {args.output}")
    print(f"============================================================")


if __name__ == "__main__":
    main()
