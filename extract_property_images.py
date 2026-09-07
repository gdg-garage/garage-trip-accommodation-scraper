#!/usr/bin/env python3
"""
Extract full-resolution image URLs and captions for a single property from local HTML.
Strictly extracts ONLY the property's dedicated gallery (excluding similar properties,
recommendation cards, and site icons).
"""

import argparse
import glob
import json
import os
import re
import sys
import urllib.parse
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

BASE_URL = "https://www.e-chalupy.cz"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".webp", ".png")


def slugify(text: str) -> str:
    """Convert text to a clean filesystem-friendly slug (ASCII only)."""
    import unicodedata
    # Normalize unicode to decompose accents (e.g. 'ř' -> 'r' + accent)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text).strip("-").lower()
    return text


def resolve_html_file(identifier: str, html_dir: str = "html") -> str:
    """Find matching HTML file given a file path, slug, URL, or property ID."""
    if os.path.isfile(identifier):
        return identifier

    if identifier.startswith("http://") or identifier.startswith("https://"):
        parsed = urllib.parse.urlparse(identifier)
        identifier = parsed.path.strip("/").split("/")[-1].replace(".html", "").replace(".php", "")

    clean_id = identifier.replace(".html", "")
    candidate = os.path.join(html_dir, f"{clean_id}.html")
    if os.path.isfile(candidate):
        return candidate

    files = glob.glob(os.path.join(html_dir, "*.html"))
    for f in files:
        base = os.path.basename(f).replace(".html", "")
        if base == clean_id:
            return f
        if clean_id.startswith("o") and base.endswith(f"-{clean_id}"):
            return f
        if base.endswith(f"-o{clean_id}"):
            return f
        if clean_id in base:
            return f

    raise FileNotFoundError(f"Could not find local HTML file matching '{identifier}' in '{html_dir}/'")


def clean_caption(raw: str) -> str:
    """Clean and filter out meta badges like '51 fotek, 1 video'."""
    if not raw:
        return ""
    text = raw.strip()
    # Ignore photo count labels
    if re.search(r"^\d+\s*fotek", text, re.I):
        return ""
    if re.search(r"^\d+\s*videa?", text, re.I):
        return ""
    return text


def extract_property_images(html_text: str, source_filename: str = "") -> Dict[str, Any]:
    """
    Extract structured property metadata and ONLY the photos belonging to its gallery.
    Excludes similar properties and external cards.
    """
    soup = BeautifulSoup(html_text, "html.parser")

    # 1. Property Name & ID
    h1 = soup.find("h1")
    raw_title = h1.text.strip() if h1 else ""
    id_match = re.search(r"\((\d+)\)", raw_title) or re.search(r"-o(\d+)", source_filename)
    property_id = id_match.group(1) if id_match else ""
    name = re.sub(r"\s*\(\d+\)\s*$", "", raw_title).strip() or "Ubytování"

    # Canonical URL or slug
    canon = soup.find("link", rel="canonical")
    if canon and canon.get("href"):
        canonical_url = canon["href"]
        slug = canonical_url.strip("/").split("/")[-1]
    else:
        slug = os.path.basename(source_filename).replace(".html", "") if source_filename else "property"
        canonical_url = f"{BASE_URL}/{slug}"

    # 2. Locate the dedicated gallery container
    # Modern layout: id="popup-gallery", class="property-detail-popup", class="property-detail-gallery"
    # Legacy layout: id="nahledy"
    gallery_container = (
        soup.find(id="popup-gallery")
        or soup.find(class_="property-detail-gallery")
        or soup.find(class_="property-detail-popup")
        or soup.find(id="nahledy")
    )

    seen_urls = set()
    images: List[Dict[str, Any]] = []

    def add_image(url_path: str, caption: str = ""):
        if not url_path:
            return
        url_path = url_path.strip()

        lower = url_path.lower()
        if not any(lower.endswith(ext) or ext in lower for ext in IMAGE_EXTENSIONS):
            return
        if any(bad in lower for bad in ("icon", "logo", "reklama", "mapa", "rating", "banner", "avatar", "svg")):
            return

        if not url_path.startswith("http"):
            full_url = urllib.parse.urljoin(BASE_URL, url_path)
        else:
            full_url = url_path

        # Normalize to full resolution /foto/ if /nahledy/ was given
        if "/nahledy/" in full_url:
            full_url = full_url.replace("/nahledy/", "/foto/")

        if full_url in seen_urls:
            return
        seen_urls.add(full_url)

        orig_filename = full_url.strip("/").split("/")[-1].split("?")[0]
        ext = os.path.splitext(orig_filename)[1] or ".jpg"

        idx = len(images) + 1
        cap = clean_caption(caption)
        if cap:
            slug_cap = slugify(cap)[:45]
            file_label = f"{idx:03d}_{slug_cap}{ext}"
        else:
            # Fallback to readable name derived from original filename
            base_clean = re.sub(r"-[a-f0-9]{4}-[a-f0-9]{4}-\d+", "", orig_filename.replace(ext, ""))
            file_label = f"{idx:03d}_{slugify(base_clean)[:45]}{ext}"

        images.append({
            "index": idx,
            "url": full_url,
            "caption": cap,
            "filename": file_label,
            "original_filename": orig_filename,
        })

    # First attempt: parse strictly from the dedicated gallery container
    if gallery_container:
        # Check popup gallery items / links
        for a in gallery_container.find_all("a", href=True):
            href = a["href"]
            if "/foto/" in href or (gallery_container.get("id") == "nahledy" and any(href.lower().endswith(e) for e in IMAGE_EXTENSIONS)):
                img = a.find("img")
                cap = (img.get("alt") if img else None) or (img.get("title") if img else None) or a.get("title") or a.get("alt") or ""
                add_image(href, cap)

        for img in gallery_container.find_all("img", src=True):
            src = img["src"]
            if "/foto/" in src or "/nahledy/" in src:
                cap = img.get("alt") or img.get("title") or ""
                add_image(src, cap)

    # Fallback: if no dedicated gallery container found, search main property body
    # (strictly excluding similar-properties and footer)
    if not images:
        main_content = soup.find(class_=re.compile(r"property-detail|p-detail|chata", re.I)) or soup.body
        if main_content:
            # Remove similar properties section before searching
            for bad_sec in main_content.find_all(class_=re.compile(r"similiar|similar|doporuc|footer", re.I)):
                bad_sec.decompose()

            for a in main_content.find_all("a", href=True):
                href = a["href"]
                if "/foto/" in href:
                    img = a.find("img")
                    cap = (img.get("alt") if img else None) or a.get("title") or ""
                    add_image(href, cap)

    return {
        "property_id": property_id,
        "name": name,
        "slug": slug,
        "canonical_url": canonical_url,
        "source_file": source_filename,
        "total_images": len(images),
        "images": images,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract all gallery image URLs for a single property from local HTML.")
    parser.add_argument("property", help="HTML file path, property slug, or ID (e.g. 'html/benecko-chalupa-pronajmuti-hribek-o358.html' or 'o358')")
    parser.add_argument("--html-dir", "-d", default="html", help="Directory containing downloaded HTML files (default: 'html')")
    parser.add_argument("--output", "-o", type=str, default=None, help="Save extracted manifest to JSON file")
    parser.add_argument("--json", action="store_true", help="Output pure JSON to stdout")
    args = parser.parse_args()

    try:
        html_path = resolve_html_file(args.property, args.html_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        data = extract_property_images(f.read(), source_filename=html_path)

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    print("=" * 68)
    print(f" 🏡 Property:  {data['name']} (ID: {data['property_id']})")
    print(f" 🔗 URL:       {data['canonical_url']}")
    print(f" 📄 Source:    {data['source_file']}")
    print(f" 📸 Gallery:   {data['total_images']} photos (strictly property gallery)")
    print("=" * 68)

    if data["images"]:
        print("\nExtracted Gallery Photos (first 8):")
        for img in data["images"][:8]:
            cap_info = f" - \"{img['caption']}\"" if img['caption'] else ""
            print(f"  [{img['index']:02d}] {img['url']}{cap_info}")
            print(f"       -> Filename: {img['filename']}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved manifest to: {args.output}")


if __name__ == "__main__":
    main()
