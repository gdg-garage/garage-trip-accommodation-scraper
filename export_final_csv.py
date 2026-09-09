#!/usr/bin/env python3
"""
Export final scored accommodations into a clean, comprehensive CSV ready for Google Sheets import.
Combines:
  1. Pass 2 Multimodal evaluation scores (common room, tables, sleeping, wellness, facilities)
  2. Tables confirmed by vision, image observations, pros, cons, and final verdict
  3. Pass 1 structured technical specs (capacities, exact beds, bedrooms, toilets, showers, sauna, beer tap, kitchen)
  4. Location (village, region, GPS, Google Maps link)
  5. Verified live e-chalupy URL
"""

import csv
import json
import os
import re
from bs4 import BeautifulSoup

def parse_location_from_html(html_path):
    if not os.path.isfile(html_path):
        return {"village": "", "region": "", "gps": "", "maps_url": ""}
    try:
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f.read(8000), "html.parser")
        
        lat_meta = soup.find("meta", property="place:location:latitude")
        lon_meta = soup.find("meta", property="place:location:longitude")
        lat = lat_meta.get("content").strip() if lat_meta else ""
        lon = lon_meta.get("content").strip() if lon_meta else ""
        gps = f"{lat}, {lon}" if lat and lon else ""
        maps_url = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else ""

        title = soup.find("title").text.strip() if soup.find("title") else ""
        village = ""
        region = ""
        
        # Pattern A: 'Ubytování <Village>, <Name> - <Region>, <ID>'
        mA = re.search(r"Ubytování\s+([^,]+),\s*(.*?)\s*-\s*([^,]+),\s*(\d+)", title)
        if mA:
            village = mA.group(1).strip()
            region = mA.group(3).strip()
        else:
            # Pattern B: '<Name> - pronájem chalupy <Village> - ubytování <Region>, <ID>'
            mB = re.search(r"^(.*?)\s*-\s*(?:chalupa k pronájmu|pronájem chalupy|ubytování)\s*([^,-]+)\s*-\s*ubytování\s*([^,]+),\s*(\d+)", title)
            if mB:
                village = mB.group(2).strip()
                region = mB.group(3).strip()
            else:
                # Pattern C: fallback split
                parts = title.split(" - ")
                if len(parts) >= 2:
                    region = re.sub(r",\s*\d+$", "", parts[-1]).strip()

        return {"village": village, "region": region, "gps": gps, "maps_url": maps_url}
    except Exception:
        return {"village": "", "region": "", "gps": "", "maps_url": ""}

def main():
    with open("rankings_final_multimodal.json", "r", encoding="utf-8") as f:
        multimodal = json.load(f)

    with open("properties_structured.json", "r", encoding="utf-8") as f:
        structured = json.load(f)

    # Sort candidates by final_score descending
    multimodal_sorted = sorted(multimodal, key=lambda x: x.get("final_score", 0), reverse=True)

    csv_rows = []
    for rank, item in enumerate(multimodal_sorted, 1):
        pid = str(item.get("property_id"))
        s_data = structured.get(pid, {})
        source_file = item.get("source_file") or s_data.get("source_file") or f"{pid}.html"
        html_path = os.path.join("html", source_file)

        loc = parse_location_from_html(html_path)

        # Pros and cons as clean bulleted strings
        pros_str = "\n".join(f"• {p}" for p in item.get("pros", []))
        cons_str = "\n".join(f"• {c}" for c in item.get("cons", []))

        row = {
            "Rank": rank,
            "Final Score": item.get("final_score"),
            "Pass 1 Text Score": item.get("pass1_score"),
            "Name": item.get("name"),
            "URL": item.get("url"),
            "Region": loc["region"],
            "Village / Town": loc["village"],
            "Google Maps Link": loc["maps_url"],
            "GPS": loc["gps"],
            "Tables Score (max 25)": item.get("tables_score"),
            "Common Room Score (max 25)": item.get("common_room_score"),
            "Sleeping Comfort Score (max 20)": item.get("sleeping_score"),
            "Wellness Score (max 15)": item.get("wellness_score"),
            "Facilities Score (max 15)": item.get("facilities_score"),
            "Tables Confirmed by Vision": "YES" if item.get("tables_confirmed_by_images") else "NO",
            "Verdict": item.get("verdict"),
            "Pros": pros_str,
            "Cons": cons_str,
            "Image Reasoning": item.get("image_reasoning"),
            "Capacity Total": s_data.get("capacity_total"),
            "Regular Beds": s_data.get("beds_regular"),
            "Extra Beds": s_data.get("beds_extra"),
            "Bedrooms Count": s_data.get("bedrooms_count"),
            "Bedroom Layout": s_data.get("bedroom_layout"),
            "Bunk Beds Count": s_data.get("bunk_beds_count"),
            "Toilets Count": s_data.get("toilets_count"),
            "Bathrooms Count": s_data.get("bathrooms_count"),
            "Showers Count": s_data.get("showers_count"),
            "Has Sauna": "YES" if s_data.get("has_sauna") else "NO",
            "Sauna Type": s_data.get("sauna_type") or "",
            "Has Hot Tub / Whirlpool": "YES" if s_data.get("has_hot_tub_or_whirlpool") else "NO",
            "Has Pool": "YES" if s_data.get("has_pool") else "NO",
            "Beer Tap Available": "YES" if s_data.get("beer_tap_available") else "NO",
            "Tables & Workspace Description": s_data.get("tables_and_workspace"),
            "Table Seating Capacity": s_data.get("tables_seating_capacity"),
            "Common Room Size m2": s_data.get("common_room_size_m2"),
            "Common Room Description": s_data.get("common_room_description"),
            "Fridges Count": s_data.get("fridges_count"),
            "Dishwashers Count": s_data.get("dishwashers_count"),
            "Kitchen Details": s_data.get("kitchen_details"),
            "Wi-Fi Available": "YES" if s_data.get("wifi_available") else "NO",
            "Parking Spaces": s_data.get("parking_spaces"),
            "Exclusive Private Rental": "YES" if s_data.get("exclusive_private_rental") else "NO",
            "Owner on Site Risk": "YES" if s_data.get("owner_lives_on_site") else "NO",
            "Price Weekend CZK": s_data.get("price_weekend_czk"),
            "Price Week CZK": s_data.get("price_week_czk"),
            "Price Notes": s_data.get("price_notes"),
            "Property ID": pid,
            "Source HTML File": source_file,
        }
        csv_rows.append(row)

    output_csv = "rankings_garage_trip_final.csv"
    if csv_rows:
        fieldnames = list(csv_rows[0].keys())
        with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"Exported {len(csv_rows)} rows to {output_csv}")

    # Copy to Google Drive as well
    gdrive_dest = "/Users/tivvit/Library/CloudStorage/GoogleDrive-tivvitmail@gmail.com/My Drive/Garage Trip 7.0 2026/rankings_garage_trip_final.csv"
    try:
        import shutil
        shutil.copyfile(output_csv, gdrive_dest)
        print(f"Copied CSV directly to Google Drive: {gdrive_dest}")
    except Exception as e:
        print(f"Could not copy to Google Drive: {e}")

if __name__ == "__main__":
    main()
