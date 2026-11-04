#!/usr/bin/env python3
"""
Export complete catalog and URL lists of all accommodation properties missing local gallery images.
Generates:
1. data/missing_property_images_urls.json (rich structured JSON grouped by property)
2. data/missing_property_images_urls.csv (spreadsheet table for quick review)
3. data/missing_images_urls_all.txt (all 3,821 image URLs, one per line)
4. data/missing_images_urls_top_candidates.txt (top eligible candidates only)
5. data/urls_by_property/*.txt (per-property URL lists for targeted downloads)
"""

import csv
import json
import os
import re
from typing import Dict, List, Any

QUEUE_JSON = "queue_candidates_50plus.json"
MANIFEST_JSON = "images_manifest.json"
OUTPUT_DIR = "data"
PER_PROP_DIR = os.path.join(OUTPUT_DIR, "urls_by_property")


def slugify_czech(text: str) -> str:
    """Clean ASCII transliteration for Czech property names."""
    cz_map = {
        'á': 'a', 'č': 'c', 'ď': 'd', 'é': 'e', 'ě': 'e', 'í': 'i', 'ň': 'n',
        'ó': 'o', 'ř': 'r', 'š': 's', 'ť': 't', 'ú': 'u', 'ů': 'u', 'ý': 'y', 'ž': 'z',
        'Á': 'a', 'Č': 'c', 'Ď': 'd', 'É': 'e', 'Ě': 'e', 'Í': 'i', 'Ň': 'n',
        'Ó': 'o', 'Ř': 'r', 'Š': 's', 'Ť': 't', 'Ú': 'u', 'Ů': 'u', 'Ý': 'y', 'Ž': 'z'
    }
    res = []
    for ch in text:
        res.append(cz_map.get(ch, ch))
    s = "".join(res).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PER_PROP_DIR, exist_ok=True)

    with open(QUEUE_JSON, "r", encoding="utf-8") as f:
        queue = json.load(f)

    manifest = {}
    if os.path.exists(MANIFEST_JSON):
        with open(MANIFEST_JSON, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    # Check images/ directory for existing directories
    existing_image_dirs = {}
    if os.path.exists("images"):
        for d in os.listdir("images"):
            full_p = os.path.join("images", d)
            if os.path.isdir(full_p):
                m = re.search(r"o(\d+)", d) or re.search(r"-(\d+)$", d)
                if m:
                    existing_image_dirs[m.group(1)] = os.path.join("images", d)

    missing_candidates = []
    all_urls = []
    top_urls = []

    for item in queue:
        listing = item.get("Listing", "")
        name = item.get("Name", "")
        rank = item.get("Rank", "")
        is_eligible = bool(item.get("All_Must_Haves_Met", False))
        listing_url = item.get("Url", "")
        existing_folder = item.get("Photos_Folder", "")
        existing_list = item.get("Photos_List", [])

        m_oid = re.search(r"(\d+)", listing)
        oid = m_oid.group(1) if m_oid else None

        # Check real local downloaded files on disk
        real_files = []
        check_folder = existing_folder or (existing_image_dirs.get(oid) if oid else None)
        if check_folder and os.path.exists(check_folder):
            real_files = [f for f in os.listdir(check_folder) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]

        # If already has downloaded images, skip
        if len(real_files) > 0:
            continue

        # Collect all image URLs
        urls = []

        # 1. Check manifest
        if oid:
            for mk, mv in manifest.items():
                if f"-o{oid}" in mk or f"_{oid}" in mk or mk.endswith(f"-{oid}"):
                    for p in mv:
                        u = p.get("url") or p.get("full_url")
                        if u and u.startswith("http") and u not in urls:
                            urls.append(u)
                    break

        # 2. Check Photos_List in queue
        for p in existing_list:
            if isinstance(p, str) and p.startswith("http") and p not in urls:
                urls.append(p)

        # 3. Determine target directory
        if existing_image_dirs.get(oid):
            target_dir = existing_image_dirs[oid]
        elif existing_folder:
            target_dir = existing_folder
        elif oid:
            # Generate friendly slug
            safe_name = slugify_czech(name)
            target_dir = f"images/ubytovani-{safe_name}-o{oid}"
        else:
            target_dir = "images/unknown"

        # Images list with suggested filenames
        images_info = []
        for idx, u in enumerate(urls, 1):
            ext = ".jpg"
            if ".png" in u.lower():
                ext = ".png"
            elif ".webp" in u.lower():
                ext = ".webp"
            filename = f"{idx:03d}{ext}"
            images_info.append({
                "index": idx,
                "filename": filename,
                "url": u,
                "target_path": os.path.join(target_dir, filename)
            })

        candidate_data = {
            "rank": rank,
            "is_eligible": is_eligible,
            "listing": listing,
            "property_id": oid,
            "name": name,
            "listing_url": listing_url,
            "target_directory": target_dir,
            "photos_count": len(urls),
            "image_urls": urls,
            "images_detailed": images_info,
        }
        missing_candidates.append(candidate_data)

        # Append to aggregates
        for u in urls:
            all_urls.append(u)
            if is_eligible:
                top_urls.append(u)

        # Write per-property URL list
        safe_listing = re.sub(r"[^a-zA-Z0-9_-]+", "_", listing)
        prop_file = os.path.join(PER_PROP_DIR, f"{safe_listing}.txt")
        with open(prop_file, "w", encoding="utf-8") as pf:
            for u in urls:
                pf.write(u + "\n")

    # 1. Export JSON
    json_path = os.path.join(OUTPUT_DIR, "missing_property_images_urls.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_properties_missing": len(missing_candidates),
            "eligible_properties_missing": sum(1 for c in missing_candidates if c["is_eligible"]),
            "disqualified_properties_missing": sum(1 for c in missing_candidates if not c["is_eligible"]),
            "total_urls_count": len(all_urls),
            "eligible_urls_count": len(top_urls),
            "properties": missing_candidates
        }, f, indent=2, ensure_ascii=False)
    print(f"📁 Exported structured JSON: {json_path}")

    # 2. Export CSV
    csv_path = os.path.join(OUTPUT_DIR, "missing_property_images_urls.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Rank", "Status", "Listing", "Property_ID", "Name", "Photos_Count",
            "Target_Directory", "Listing_URL", "Sample_Photo_1", "Sample_Photo_2", "Sample_Photo_3"
        ])
        for c in missing_candidates:
            writer.writerow([
                c["rank"],
                "Eligible" if c["is_eligible"] else "Disqualified",
                c["listing"],
                c["property_id"],
                c["name"],
                c["photos_count"],
                c["target_directory"],
                c["listing_url"],
                c["image_urls"][0] if len(c["image_urls"]) > 0 else "",
                c["image_urls"][1] if len(c["image_urls"]) > 1 else "",
                c["image_urls"][2] if len(c["image_urls"]) > 2 else "",
            ])
    print(f"📁 Exported CSV table:      {csv_path}")

    # 3. Export flat text lists
    txt_all_path = os.path.join(OUTPUT_DIR, "missing_images_urls_all.txt")
    with open(txt_all_path, "w", encoding="utf-8") as f:
        for u in all_urls:
            f.write(u + "\n")
    print(f"📁 Exported all URLs list:   {txt_all_path} ({len(all_urls)} URLs)")

    txt_top_path = os.path.join(OUTPUT_DIR, "missing_images_urls_top_candidates.txt")
    with open(txt_top_path, "w", encoding="utf-8") as f:
        for u in top_urls:
            f.write(u + "\n")
    print(f"📁 Exported top cand. list:  {txt_top_path} ({len(top_urls)} URLs)")


if __name__ == "__main__":
    main()
