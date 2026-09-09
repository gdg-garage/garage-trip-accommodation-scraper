#!/usr/bin/env python3
"""
Download gallery images for the top ranked candidate accommodations.
Follows the rule:
- Download all photos for one property (with intra-image polite pacing).
- Wait for a longer time between properties (e.g. 8-12 seconds).
"""

import argparse
import json
import os
import random
import sys
import time
from typing import List, Dict, Any

from extract_property_images import extract_property_images, resolve_html_file
from download_property_images import download_property_images


def download_top_candidates(
    rankings_file: str,
    top_n: int = 42,
    html_dir: str = "html",
    output_dir: str = "images",
    image_delay: float = 0.8,
    image_jitter: float = 0.4,
    inter_property_wait_min: float = 8.0,
    inter_property_wait_max: float = 12.0,
    limit_per_property: int = None,
):
    if not os.path.exists(rankings_file):
        print(f"Error: rankings file '{rankings_file}' not found.")
        sys.exit(1)

    with open(rankings_file, "r", encoding="utf-8") as f:
        ranked_properties = json.load(f)

    candidates = ranked_properties[:top_n]
    total_candidates = len(candidates)

    print("=" * 72)
    print(f" 🚀 Starting Gallery Image Download for Top {total_candidates} Candidates")
    print(f" 📁 HTML Directory:           {html_dir}")
    print(f" 📁 Image Output:             {output_dir}/")
    print(f" ⏱️  Pacing per Image:         {image_delay:.1f}s ± {image_jitter:.1f}s")
    print(f" ⏳ Wait between Properties:  {inter_property_wait_min:.1f}s - {inter_property_wait_max:.1f}s")
    print("=" * 72)

    total_downloaded = 0
    total_cached = 0
    total_failed = 0
    total_bytes = 0
    start_all = time.time()

    for idx, prop in enumerate(candidates, 1):
        prop_id = prop.get("property_id")
        name = prop.get("name")
        score = prop.get("score_total")
        source_file = prop.get("source_file")

        print(f"\n[{idx}/{total_candidates}] 🏰 Processing Property: {name} (ID: {prop_id}, Score: {score})")

        # Resolve HTML file
        html_path = os.path.join(html_dir, source_file) if source_file else None
        if not html_path or not os.path.exists(html_path):
            html_path = resolve_html_file(f"o{prop_id}", html_dir=html_dir)

        if not html_path or not os.path.exists(html_path):
            print(f" ⚠️  HTML file not found for {name} ({prop_id}). Skipping.")
            continue

        with open(html_path, "r", encoding="utf-8", errors="ignore") as hf:
            html_content = hf.read()

        # Extract gallery images from HTML content
        prop_manifest = extract_property_images(html_content, source_filename=html_path)
        img_count = len(prop_manifest.get("images", []))
        print(f" 📸 Found {img_count} images in gallery.")

        if img_count == 0:
            print(" ⚠️  No images found. Skipping.")
            continue

        # Slug for folder
        slug = prop_manifest.get("slug") or f"o{prop_id}"
        prop_output_dir = os.path.join(output_dir, slug)

        # Download all photos for this property
        stats = download_property_images(
            property_data=prop_manifest,
            output_dir=prop_output_dir,
            limit=limit_per_property,
            delay=image_delay,
            jitter=image_jitter,
        )

        total_downloaded += stats["downloaded"]
        total_cached += stats["cached"]
        total_failed += stats["failed"]
        total_bytes += stats["total_bytes"]

        # If not the last property, wait longer between properties
        if idx < total_candidates:
            wait_time = random.uniform(inter_property_wait_min, inter_property_wait_max)
            print(f" 💤 Waiting {wait_time:.1f}s before moving to next property ({idx + 1}/{total_candidates})...")
            time.sleep(wait_time)

    total_time = time.time() - start_all
    print("\n" + "=" * 72)
    print(f" 🏁 Finished Image Download for {total_candidates} Candidates in {total_time/60:.1f} minutes")
    print(f"    • Total Images Newly Downloaded: {total_downloaded}")
    print(f"    • Total Images Cached:           {total_cached}")
    print(f"    • Total Failures:               {total_failed}")
    print(f"    • Total Data Size:               {total_bytes / (1024 * 1024):.2f} MB")
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Download gallery images for top scored properties.")
    parser.add_argument("--rankings", "-r", default="rankings_text_pass1.json", help="Path to rankings JSON")
    parser.add_argument("--top", "-n", type=int, default=42, help="Number of top properties to download")
    parser.add_argument("--html-dir", default="html", help="HTML directory")
    parser.add_argument("--output-dir", "-o", default="images", help="Output images directory")
    parser.add_argument("--delay", type=float, default=0.8, help="Pacing between photos")
    parser.add_argument("--jitter", type=float, default=0.4, help="Jitter between photos")
    parser.add_argument("--wait-min", type=float, default=8.0, help="Min seconds between properties")
    parser.add_argument("--wait-max", type=float, default=12.0, help="Max seconds between properties")
    parser.add_argument("--limit-per-prop", type=int, default=None, help="Optional limit per property")

    args = parser.parse_args()
    download_top_candidates(
        rankings_file=args.rankings,
        top_n=args.top,
        html_dir=args.html_dir,
        output_dir=args.output_dir,
        image_delay=args.delay,
        image_jitter=args.jitter,
        inter_property_wait_min=args.wait_min,
        inter_property_wait_max=args.wait_max,
        limit_per_property=args.limit_per_prop,
    )


if __name__ == "__main__":
    main()
