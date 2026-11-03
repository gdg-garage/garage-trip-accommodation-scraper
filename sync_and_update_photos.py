#!/usr/bin/env python3
"""
Sync photos across all candidate accommodation datasets:
- Maps local downloaded photos from images/ and booking_images/
- Cleans invalid relative folder paths for properties with remote gallery URLs
- Populates candidates that had 0 photos from sheet_latest.xlsx and images_manifest.json
- Canonicalizes listing URLs
- Updates data/candidates_must_nice_all.json, queue_candidates_50plus.json, and queue_candidates_50plus.csv
"""

import csv
import glob
import json
import os
import re
import openpyxl

def sync_all():
    # 1. Load sheet_latest.xlsx photo URLs and canonical links
    wb = openpyxl.load_workbook("sheet_latest.xlsx", data_only=False)
    sheet = wb.active

    sheet_photos = {}
    sheet_urls = {}
    for row in sheet.iter_rows(values_only=True):
        listing_cell = str(row[11] or "")
        m = re.search(r"\d+", listing_cell)
        if m:
            oid = m.group(0)
            # URL
            m_url = re.search(r'https://[^\",\s\)]+', listing_cell)
            if m_url:
                sheet_urls[oid] = m_url.group(0)

            # Photos
            p_list = []
            for cell in [row[32], row[33]]:
                if cell and "http" in str(cell):
                    m_p = re.search(r'https://[^\",\s\)]+', str(cell))
                    if m_p:
                        p_list.append(m_p.group(0))
            if p_list:
                sheet_photos[oid] = p_list

    print(f"Loaded {len(sheet_photos)} properties with photos from sheet_latest.xlsx")
    print(f"Loaded {len(sheet_urls)} properties with URLs from sheet_latest.xlsx")

    # 2. Load urls.txt for exact slugs
    exact_urls = {}
    if os.path.exists("urls.txt"):
        with open("urls.txt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                m = re.search(r"-o(\d+)$", line)
                if m:
                    exact_urls[m.group(1)] = line

    # 3. Load images_manifest.json
    manifest = {}
    if os.path.exists("images_manifest.json"):
        with open("images_manifest.json", encoding="utf-8") as f:
            manifest = json.load(f)
    print(f"Loaded {len(manifest)} manifest entries")

    # 4. Load candidates
    with open("data/candidates_must_nice_all.json", "r", encoding="utf-8") as f:
        candidates = json.load(f)

    print(f"Processing {len(candidates)} candidates...")

    local_count = 0
    remote_cleaned_count = 0
    populated_count = 0
    zero_photo_count = 0

    for c in candidates:
        name = c.get("Name", "")
        listing = c.get("Listing", "")
        m = re.search(r"\d+", listing)
        oid = m.group(0) if m else ""

        # Fix Url if shortened or missing
        current_url = c.get("Url", "")
        if not current_url or "/ubytovani/" in current_url:
            if oid in exact_urls:
                c["Url"] = exact_urls[oid]
            elif oid in sheet_urls:
                c["Url"] = sheet_urls[oid]

        # Check local folder on disk
        folder = c.get("Photos_Folder", "")
        has_disk_files = False
        valid_files = []

        if folder and os.path.isdir(folder):
            valid_files = sorted([f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])
            if len(valid_files) > 0:
                has_disk_files = True

        if not has_disk_files and oid:
            for pattern in [f"images/*{oid}*", f"images/*-o{oid}", f"*{oid}*", f"data/*{oid}*"]:
                for d in glob.glob(pattern):
                    if os.path.isdir(d):
                        files = sorted([f for f in os.listdir(d) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])
                        if len(files) > 0:
                            folder = d
                            valid_files = files
                            has_disk_files = True
                            break
                if has_disk_files:
                    break

        if has_disk_files:
            c["Has_Local_Photos"] = True
            c["Photos_Folder"] = folder
            c["Photos_List"] = valid_files
            c["Photos_Count"] = len(valid_files)
            c["Primary_Photo"] = valid_files[0]
            local_count += 1
        else:
            # Not local files on disk
            cur_photos = c.get("Photos_List") or []
            has_remote = any(p.startswith("http") for p in cur_photos)

            if len(cur_photos) > 0 and has_remote:
                # Clear invalid folder path so UI doesn't prepend broken /images/.../https://...
                c["Photos_Folder"] = ""
                c["Has_Local_Photos"] = True
                c["Photos_Count"] = len(cur_photos)
                c["Primary_Photo"] = cur_photos[0]
                remote_cleaned_count += 1
            else:
                # 0 photos currently: try populating from sheet or manifest
                new_photos = []
                if oid in sheet_photos:
                    new_photos = sheet_photos[oid]
                elif c.get("Url"):
                    # Check manifest by slug
                    slug = c["Url"].rstrip("/").split("/")[-1].replace(".php", "").replace(".html", "")
                    if slug in manifest and manifest[slug]:
                        new_photos = [it["url"] for it in manifest[slug] if it.get("url")]

                if new_photos:
                    c["Photos_Folder"] = ""
                    c["Photos_List"] = new_photos
                    c["Photos_Count"] = len(new_photos)
                    c["Primary_Photo"] = new_photos[0]
                    c["Has_Local_Photos"] = True
                    populated_count += 1
                else:
                    c["Has_Local_Photos"] = False
                    c["Photos_Folder"] = ""
                    c["Photos_List"] = []
                    c["Photos_Count"] = 0
                    c["Primary_Photo"] = ""
                    zero_photo_count += 1
                    print(f"⚠️ Still 0 photos for {name} ({listing})")

    print("\n--- SYNC RESULTS ---")
    print(f"Total candidates: {len(candidates)}")
    print(f"  • Local image galleries (on disk): {local_count}")
    print(f"  • Remote image galleries (cleaned folder): {remote_cleaned_count}")
    print(f"  • Newly populated galleries: {populated_count}")
    print(f"  • Remaining with 0 photos: {zero_photo_count}")

    # 5. Save updated data/candidates_must_nice_all.json
    with open("data/candidates_must_nice_all.json", "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)
    print("💾 Saved data/candidates_must_nice_all.json")

    # 6. Save updated queue_candidates_50plus.json
    with open("queue_candidates_50plus.json", "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)
    print("💾 Saved queue_candidates_50plus.json")

    # 7. Save updated queue_candidates_50plus.csv
    csv_out = "queue_candidates_50plus.csv"
    if candidates:
        all_keys = []
        seen = set()
        for q in candidates:
            for k in q.keys():
                if k not in seen and k not in ("Photos_List", "Pros_Vs_Novy_Svet", "Cons_Vs_Novy_Svet", "Consecutive_Ranges"):
                    seen.add(k)
                    all_keys.append(k)
        all_keys.extend(["Consecutive_Ranges", "Pros_Vs_Novy_Svet", "Cons_Vs_Novy_Svet"])
        with open(csv_out, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            writer.writeheader()
            for q in candidates:
                row_copy = {k: v for k, v in q.items() if k not in ("Photos_List", "Pros_Vs_Novy_Svet", "Cons_Vs_Novy_Svet", "Consecutive_Ranges")}
                row_copy["Consecutive_Ranges"] = ", ".join(q.get("Consecutive_Ranges", [])) if isinstance(q.get("Consecutive_Ranges"), list) else str(q.get("Consecutive_Ranges") or "")
                row_copy["Pros_Vs_Novy_Svet"] = " | ".join(q.get("Pros_Vs_Novy_Svet", [])) if isinstance(q.get("Pros_Vs_Novy_Svet"), list) else str(q.get("Pros_Vs_Novy_Svet") or "")
                row_copy["Cons_Vs_Novy_Svet"] = " | ".join(q.get("Cons_Vs_Novy_Svet", [])) if isinstance(q.get("Cons_Vs_Novy_Svet"), list) else str(q.get("Cons_Vs_Novy_Svet") or "")
                writer.writerow(row_copy)
        print(f"💾 Saved {csv_out}")

if __name__ == "__main__":
    sync_all()
