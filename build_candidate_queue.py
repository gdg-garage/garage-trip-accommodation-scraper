#!/usr/bin/env python3
"""
Build Candidate Queue for Garage Trip Accommodations (September Off-Season Edition).
Filters accommodations:
- No veto
- Score >= 50
Enriches with:
- September Off-Season 7-Night Price (comparing directly to Novy Svet at 60k CZK)
- Strict 7 Consecutive Days in September Check (identifying whether a 7-night week fits)
- Beer tap & tap count extractor
- Local photo gallery paths and photo counts
- Comparison pills vs Chalupa Novy Svet (benchmarked to 60,000 CZK & 7-night availability)
Outputs queue_candidates_50plus.csv, queue_candidates_50plus.json,
and generates an updated Excel workbook sheet_updated_with_extractors.xlsx.
"""

import csv
import glob
import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple

import openpyxl
from bs4 import BeautifulSoup
from extract_beer_tap import extract_beer_tap_info
from extract_availability import extract_september_availability

# Anchor Novy Svet reference values (September Off-Season actual paid price)
ANCHOR = {
    "name": "Chalupa Nový Svět",
    "location": "Prostřední Lipka, Orlické hory",
    "price_7_nights_september": 60000.0,
    "score_total": 80.0,
    "score_common": 33.0,
    "score_bedrooms": 16.0,
    "score_wellness": 16.0,
    "has_pool": False,
    "has_sauna": True,
    "beer_taps": 4
}


def clean_float(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", ".").strip())
    except (ValueError, TypeError):
        return None


def calculate_price_score(price_week_czk: Optional[float]) -> float:
    if price_week_czk is None or price_week_czk <= 0:
        return 3.0
    if price_week_czk <= 60000.0:
        return 5.0
    elif price_week_czk <= 75000.0:
        return 4.0
    elif price_week_czk <= 90000.0:
        return 3.0
    elif price_week_czk <= 120000.0:
        return 2.0
    else:
        return 1.0


def extract_september_price(listing: str, note: str, current_price: Optional[float]) -> Tuple[Optional[float], str]:
    """
    Extracts the September / off-season price for 7 nights.
    Checks e-chalupy price tables in HTML, then reviewer notes, and falls back to standard 7-night rate.
    """
    # 1. Check raw HTML for e-chalupy
    oid_match = re.search(r"\d+", listing)
    if oid_match:
        oid = oid_match.group(0)
        h_files = glob.glob(f"html/*o{oid}.html")
        if h_files:
            try:
                soup = BeautifulSoup(open(h_files[0]), "html.parser")
                for group in soup.find_all(class_="price-group"):
                    title_el = group.find(class_="group-title")
                    title = title_el.text.strip().lower() if title_el else ""
                    if "mimo sez" in title:
                        for item in group.find_all(class_="price-item"):
                            b = item.find("b")
                            desc = item.find("i").text.strip().lower() if item.find("i") else ""
                            if b:
                                val = re.sub(r"[^\d]", "", b.text)
                                if val:
                                    num = int(val)
                                    # Whole house / week
                                    if "týden" in desc and num >= 15000:
                                        # Check if notes have specific promo (e.g. 7th night free)
                                        if "7th night free" in note or "7 nights with 1 free" in note:
                                            pass
                                        else:
                                            return float(num), f"{num:,} Kč/week off-season rate".replace(",", " ")
                                    # Whole house / night (min 3000/night)
                                    if "noc" in desc and "osob" not in desc and num >= 3000:
                                        if "7th night free" in note or "7 nights with 1 free" in note:
                                            total = num * 6
                                            return float(total), f"{total:,} Kč (off-season {num:,} Kč/night × 6, 7th free)".replace(",", " ")
                                        else:
                                            total = num * 7
                                            return float(total), f"{total:,} Kč (off-season {num:,} Kč/night × 7)".replace(",", " ")
            except Exception:
                pass

    # 2. Check note for explicit off-season rates
    m_off = re.search(r"(\d+(?:\.\d+)?)\s*k(?:\s*Kč)?\s*(?:off-season|mimo\s*sez[oó]n\w*)", note, re.I)
    if m_off:
        val = float(m_off.group(1)) * 1000.0
        return val, f"{int(val):,} Kč off-season rate".replace(",", " ")

    m_off2 = re.search(r"(?:off-season|mimo\s*sez[oó]n\w*)[^\d]*(\d+(?:\.\d+)?)\s*k", note, re.I)
    if m_off2:
        val = float(m_off2.group(1)) * 1000.0
        return val, f"{int(val):,} Kč off-season rate".replace(",", " ")

    m_off3 = re.search(r"(?:off-season)[^\n]*->\s*~?(\d+(?:\.\d+)?)\s*k", note, re.I)
    if m_off3:
        val = float(m_off3.group(1)) * 1000.0
        return val, f"{int(val):,} Kč off-season rate".replace(",", " ")

    # Fallback to existing 7-night calculated price
    if current_price and current_price > 0:
        return current_price, "All-year / flat 7-night rate"

    return None, "Price on inquiry"


def get_html_text_for_listing(listing: str, name: str) -> str:
    html_text = ""
    if listing.startswith("e-chalupy"):
        m = re.search(r"\d+", listing)
        if m:
            oid = m.group(0)
            matches = glob.glob(f"html/*o{oid}.html")
            if matches:
                with open(matches[0], "r", encoding="utf-8", errors="ignore") as f:
                    html_text = f.read()
    elif listing.startswith("Booking"):
        slug = listing.replace("Booking", "").strip()
        matches = glob.glob(f"booking_html/{slug}.html") or glob.glob(f"booking_html/*{slug}*.html")
        if matches:
            with open(matches[0], "r", encoding="utf-8", errors="ignore") as f:
                html_text = f.read()

    return html_text


def resolve_photos(listing: str, photo_1_label: str = "", photo_2_label: str = "", url: str = "") -> Dict[str, Any]:
    folder = None
    if "HYPERLINK" in listing:
        m = re.search(r',\s*"([^"]+)"\)', listing)
        if m:
            listing = m.group(1).strip()

    if listing.startswith("e-chalupy") or "e-chalupy" in url:
        m = re.search(r"\d+", listing) or re.search(r"e-chalupy\.cz/(\d+)", url)
        if m:
            oid = m.group(0)
            if os.path.exists("images"):
                for d in os.listdir("images"):
                    if f"o{oid}" in d or d.endswith(f"-{oid}") or d == oid:
                        folder = os.path.join("images", d)
                        break
    elif listing.startswith("Booking") or "booking.com" in url:
        slug = listing.replace("Booking", "").strip()
        if not slug and url:
            m = re.search(r"hotel/[a-z]{2}/([^/?#.]+)", url)
            if m:
                slug = m.group(1)
        if os.path.exists("booking_images"):
            # Exact match first
            if slug and os.path.exists(os.path.join("booking_images", slug)):
                folder = os.path.join("booking_images", slug)
            else:
                for d in os.listdir("booking_images"):
                    if slug and (slug in d or d in slug):
                        folder = os.path.join("booking_images", d)
                        break

    if not folder or not os.path.exists(folder):
        return {
            "has_local_photos": False,
            "photos_folder": "",
            "photos_count": 0,
            "photos_list": [],
            "photo_1_file": "",
            "photo_2_file": "",
            "primary_photo": ""
        }

    all_files = sorted([f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
    
    def find_photo_file(label: str) -> str:
        if not label:
            return ""
        m_num = re.search(r"(\d+)", label)
        if m_num:
            num_str = m_num.group(1).zfill(3)
            for f in all_files:
                if f.startswith(num_str) or f"_{num_str}" in f:
                    return f
        return ""

    p1 = find_photo_file(photo_1_label)
    p2 = find_photo_file(photo_2_label)
    primary = p1 or (all_files[0] if all_files else "")

    return {
        "has_local_photos": True,
        "photos_folder": folder,
        "photos_count": len(all_files),
        "photos_list": all_files,
        "photo_1_file": p1,
        "photo_2_file": p2,
        "primary_photo": primary
    }


def generate_comparison_vs_anchor(item: Dict[str, Any], raw_row: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Compares candidate accommodation with Chalupa Novy Svet (anchor)
    benchmarked against September off-season conditions:
    - Anchor price: 60,000 CZK (what was actually paid for Novy Svet in September)
    - Strict 7 consecutive days requirement
    """
    pros = []
    cons = []

    # 1. Price comparison (Anchor = 60,000 CZK in September)
    price = item.get("Price_7_Nights_CZK")
    anchor_price = ANCHOR["price_7_nights_september"]

    if price and isinstance(price, (int, float)) and price > 0:
        diff = price - anchor_price
        if diff <= -10000:
            savings = abs(int(diff))
            pros.append(f"💰 Much cheaper than Nový Svět: saves {savings:,} Kč ({int(price):,} vs 60 000 Kč)".replace(",", " "))
        elif diff < -2000:
            savings = abs(int(diff))
            pros.append(f"💰 Cheaper than Nový Svět: saves {savings:,} Kč ({int(price):,} vs 60 000 Kč)".replace(",", " "))
        elif diff >= 25000:
            extra = int(diff)
            cons.append(f"💸 Significantly more expensive: +{extra:,} Kč ({int(price):,} vs 60 000 Kč at Nový Svět)".replace(",", " "))
        elif diff > 2000:
            extra = int(diff)
            cons.append(f"💸 More expensive: +{extra:,} Kč ({int(price):,} vs 60 000 Kč at Nový Svět)".replace(",", " "))
        else:
            pros.append("⚖️ Same price as Nový Svět in September (60 000 Kč)")
    elif not price:
        cons.append("❓ Price on inquiry / not transparently listed")

    # 2. Strict 7 Consecutive Days in September Check
    has_7_days = item.get("Has_7_Consecutive_Days", False)
    max_days = item.get("Max_Consecutive_Days", 0)
    ranges = item.get("Consecutive_Ranges") or []
    sept_avail = item.get("September_Available")

    if has_7_days:
        range_str = ranges[0] if ranges else "dates available"
        pros.append(f"✅ Full 7-night week available in Sept ({range_str})")
    elif sept_avail == "CHECK_BOOKING":
        cons.append("🔍 Dates require Booking.com availability query")
    else:
        cons.append(f"❌ Cannot do 7 days in a row in Sept (max {max_days} consecutive days free; weekends booked!)")

    # 3. Swimming Pool comparison (Novy Svet had NO pool!)
    pool_desc = (raw_row.get("Pool") or "").lower()
    has_pool = ("yes" in pool_desc or "indoor" in pool_desc or "saltwater" in pool_desc or "covered" in pool_desc) and "no pool" not in pool_desc
    if has_pool:
        if "indoor" in pool_desc or "saltwater" in pool_desc or "covered" in pool_desc:
            pros.append("🏊 Indoor / covered pool (Nový Svět had no pool)")
        else:
            pros.append("🏊 Swimming pool on site (Nový Svět had no pool)")

    # 4. Beer tap comparison (Nový Svět benchmark: 4 taps)
    tap_count = item.get("Beer_Tap_Count") or 0
    has_tap = (item.get("Beer_Tap_Available") == "YES") or tap_count > 0
    if has_tap and tap_count >= 4:
        pros.append(f"🍺 {tap_count} draft beer taps (matches/exceeds Nový Svět's 4 taps)")
    elif has_tap and tap_count > 0:
        cons.append(f"🍺 Only {tap_count} draft tap{'s' if tap_count > 1 else ''} (fewer than 4 taps at Nový Svět)")
    elif not has_tap:
        cons.append("❌ No beer tap on site (Nový Svět has 4 draft taps)")

    # 5. Common Area comparison (Novy Svet scored 33/35)
    common_score = float(item.get("Common_Area_Score") or 0)
    chairs_est = item.get("Chairs_Est") or ""
    ch_label = chairs_est if chairs_est else "25+ chairs"
    if common_score >= 32:
        pros.append(f"🛋️ Exceptional common space ({ch_label})")
    elif common_score < 22:
        cons.append(f"🪑 Weaker common area ({common_score}/35 vs 33 at Nový Svět; benches/smaller room)")

    # 6. Bedrooms & Privacy (Novy Svet scored 16/20, 7 private apartments)
    beds_score = float(item.get("Bedrooms_Score") or 0)
    if beds_score >= 17:
        pros.append("🚪 Higher room privacy: mostly 2-person rooms with private baths")
    elif beds_score <= 12:
        cons.append("🛏️ Lower bedroom privacy (larger dorms, bunk beds or shared hall baths)")

    # 7. Sauna
    sauna_desc = (raw_row.get("Sauna") or "").lower()
    if "no" in sauna_desc and "yes" not in sauna_desc:
        cons.append("🧖 No sauna (Nový Svět had Finnish sauna)")

    return pros, cons


def build_candidate_queue():
    ranking_csv = "data/sheets_export/ranking.csv"
    if not os.path.exists(ranking_csv):
        print(f"Error: {ranking_csv} not found.")
        return

    with open(ranking_csv, "r", encoding="utf-8") as f:
        ranking_rows = list(csv.DictReader(f))

    queue = []
    print(f"Processing {len(ranking_rows)} items for September retreat (off-season pricing, 7-day requirement)...")

    for row in ranking_rows:
        veto = (row.get("veto") or "").strip()
        raw_score = clean_float(row.get("Total /90")) or 0.0
        listing = (row.get("Listing") or "").strip()
        name = (row.get("Name") or "").strip()

        # Rule 1: Must NOT have a veto
        if veto:
            continue

        # Rule 2: Score >= 50
        if raw_score < 50.0:
            continue

        # 1. September Off-Season Price Extraction
        raw_price = clean_float(row.get("Price / week (CZK)"))
        note_price = row.get("Price note") or ""
        p_september, price_source_label = extract_september_price(listing, note_price, raw_price)

        # Recalculate price score and total score based on September price
        old_price_score = clean_float(row.get("Price /5")) or 3.0
        new_price_score = calculate_price_score(p_september)
        delta_score = new_price_score - old_price_score
        adjusted_total_score = round(raw_score + delta_score, 1)

        # 2. Beer Tap Extraction
        text = get_html_text_for_listing(listing, name)
        extra_notes = " ".join([
            row.get("Kitchen") or "",
            row.get("Common area (what photos show)") or "",
            row.get("Note") or "",
            row.get("Text vs photos") or "",
        ])
        combined_text = text + " " + extra_notes
        beer_info = extract_beer_tap_info(combined_text, listing_or_id=listing)

        # 3. September Availability & 7-Day Window Extraction
        sept_info = {
            "september_available": "UNKNOWN",
            "september_status": "Unknown",
            "has_7_consecutive_days": False,
            "max_consecutive_days": 0,
            "consecutive_ranges": [],
            "free_days_count": 0,
            "summary": "Requires manual check"
        }
        if listing.startswith("e-chalupy"):
            m = re.search(r"\d+", listing)
            if m:
                oid = m.group(0)
                avail = extract_september_availability(oid, use_cache=True)
                sept_info = {
                    "september_available": "YES" if avail["has_7_consecutive_days"] else ("NO_7_DAYS" if avail["free_days_count"] > 0 else "NO"),
                    "september_status": avail["september_status"],
                    "has_7_consecutive_days": avail["has_7_consecutive_days"],
                    "max_consecutive_days": avail["max_consecutive_days"],
                    "consecutive_ranges": avail["consecutive_ranges"],
                    "free_days_count": avail["free_days_count"],
                    "summary": avail["summary"]
                }
        elif listing.startswith("Booking"):
            team_comment = row.get("Team comment (old 8.0 sheet)") or ""
            if "not free in Sept" in team_comment or "not free in sept" in team_comment.lower():
                sept_info = {
                    "september_available": "NO",
                    "september_status": "Occupied (per team comment)",
                    "has_7_consecutive_days": False,
                    "max_consecutive_days": 0,
                    "consecutive_ranges": [],
                    "free_days_count": 0,
                    "summary": "Occupied in September per review notes"
                }
            else:
                sept_info = {
                    "september_available": "CHECK_BOOKING",
                    "september_status": "Check Booking.com",
                    "has_7_consecutive_days": False,
                    "max_consecutive_days": 0,
                    "consecutive_ranges": [],
                    "free_days_count": 0,
                    "summary": "Requires date query on Booking.com"
                }

        # 4. Local Photos Resolution
        photo_info = resolve_photos(listing, row.get("Photo 1") or "", row.get("Photo 2") or "")

        ext_url = ""
        if listing.startswith("e-chalupy"):
            m_id = re.search(r"\d+", listing)
            if m_id:
                ext_url = f"https://www.e-chalupy.cz/{m_id.group(0)}"
        elif listing.startswith("Booking"):
            b_slug = listing.replace("Booking", "").strip()
            ext_url = f"https://www.booking.com/hotel/cz/{b_slug}.html"

        item = {
            "Rank": row.get("Rank", ""),
            "Name": name,
            "Listing": listing,
            "Url": ext_url,
            "Total_Score": adjusted_total_score,
            "Raw_Score_Original": raw_score,
            "Location": row.get("Location", ""),
            "Price_7_Nights_CZK": p_september if p_september is not None else "",
            "Price_Source_Label": price_source_label,
            "Price_Original_CZK": raw_price if raw_price is not None else "",
            "Price_Note": note_price,
            "Price_Score": new_price_score,
            "Capacity": row.get("Capacity", ""),
            "Bedrooms_Bathrooms": row.get("Bedrooms & bathrooms", ""),
            "Common_Area_Score": row.get("Common area /35", ""),
            "Bedrooms_Score": row.get("Bedrooms /20", ""),
            "Wellness_Score": row.get("Sauna, pool, outdoor /10", ""),
            "Kitchen_Score": row.get("Kitchen /10", ""),
            "Look_Score": row.get("Look & honesty /10", ""),
            "September_Available": sept_info["september_available"],
            "September_Status": sept_info["september_status"],
            "Has_7_Consecutive_Days": sept_info["has_7_consecutive_days"],
            "Max_Consecutive_Days": sept_info["max_consecutive_days"],
            "Consecutive_Ranges": sept_info["consecutive_ranges"],
            "September_Free_Days": sept_info["free_days_count"],
            "September_Summary": sept_info["summary"],
            "Beer_Tap_Available": "YES" if beer_info["has_beer_tap"] else "NO",
            "Beer_Tap_Count": beer_info["beer_tap_count"],
            "Beer_Tap_Label": beer_info["beer_tap_label"],
            "Beer_Tap_Snippet": beer_info["beer_tap_snippet"],
            "Note": row.get("Note", ""),
            "Common_Area_Desc": row.get("Common area (what photos show)", ""),
            "Chairs_Est": row.get("Chairs in common area (est.)", ""),
            "Sauna": row.get("Sauna") or "",
            "Pool": row.get("Pool") or "",
            "Outdoor": row.get("Outdoor") or "",
            "Kitchen": row.get("Kitchen") or "",
            "Photo_Quality": row.get("Photo quality") or "",
            "Text_Vs_Photos": row.get("Text vs photos") or "",
            "Tivvit_Note": row.get("tivvit note") or "",
            "Team_Comment": row.get("Team comment (old 8.0 sheet)") or "",
            "Tivvit_Top": row.get("tivvit top") or "",
            "Fisa_Top": row.get("fisa top") or "",
            "Simon_Top": row.get("simon top") or "",
            "Eve_Top": row.get("eve top") or "",
            "Old_Sheet_Rank": row.get("Old 8.0 sheet rank (score)") or "",
            "Meets_The_Bar": row.get("Meets the bar (≥60/90, common ≥20/35, ≤150k)") or "",
            "Added_To_Sheet": row.get("Added to sheet") or "",
            "Has_Local_Photos": photo_info["has_local_photos"],
            "Photos_Folder": photo_info["photos_folder"],
            "Photos_Count": photo_info["photos_count"],
            "Photos_List": photo_info["photos_list"],
            "Primary_Photo": photo_info["primary_photo"],
            "Photo_1_Label": row.get("Photo 1", ""),
            "Photo_1_File": photo_info["photo_1_file"],
            "Photo_2_Label": row.get("Photo 2", ""),
            "Photo_2_File": photo_info["photo_2_file"],
            "Source_Tab": "ranking"
        }

        # 5. Generate Pros and Cons vs Nový Svět (benchmarked to 60k and 7 consecutive days)
        pros, cons = generate_comparison_vs_anchor(item, row)
        item["Pros_Vs_Novy_Svet"] = pros
        item["Cons_Vs_Novy_Svet"] = cons

        queue.append(item)

    queue.sort(key=lambda x: -x["Total_Score"])

    print(f"\n✅ Extracted {len(queue)} candidate accommodations with September off-season pricing & 7-day checks.")

    # Export to CSV
    csv_out = "queue_candidates_50plus.csv"
    if queue:
        flat_keys = [k for k in queue[0].keys() if k not in ("Photos_List", "Pros_Vs_Novy_Svet", "Cons_Vs_Novy_Svet", "Consecutive_Ranges")]
        flat_keys.extend(["Consecutive_Ranges", "Pros_Vs_Novy_Svet", "Cons_Vs_Novy_Svet"])
        with open(csv_out, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=flat_keys)
            writer.writeheader()
            for q in queue:
                row_copy = {k: v for k, v in q.items() if k not in ("Photos_List", "Pros_Vs_Novy_Svet", "Cons_Vs_Novy_Svet", "Consecutive_Ranges")}
                row_copy["Consecutive_Ranges"] = ", ".join(q.get("Consecutive_Ranges", []))
                row_copy["Pros_Vs_Novy_Svet"] = " | ".join(q.get("Pros_Vs_Novy_Svet", []))
                row_copy["Cons_Vs_Novy_Svet"] = " | ".join(q.get("Cons_Vs_Novy_Svet", []))
                writer.writerow(row_copy)
        print(f"📁 Exported CSV to {csv_out}")

    # Export to JSON
    json_out = "queue_candidates_50plus.json"
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)
    print(f"📁 Exported JSON to {json_out}")

    # Update original Excel workbook
    src_xlsx = "sheet_latest.xlsx"
    dst_xlsx = "sheet_updated_with_extractors.xlsx"
    if os.path.exists(src_xlsx):
        wb = openpyxl.load_workbook(src_xlsx)
        ws_rank = wb["ranking"]

        queue_by_listing = {q["Listing"]: q for q in queue}

        col_price_week = None
        col_price_note = None
        col_price_score = None
        col_total_score = None
        col_listing = None

        for col in range(1, ws_rank.max_column + 1):
            val = ws_rank.cell(1, col).value
            if val in ("Price / week (CZK)", "Price / 7 nights (CZK)"):
                col_price_week = col
            elif val == "Price note":
                col_price_note = col
            elif val == "Price /5":
                col_price_score = col
            elif val == "Total /90":
                col_total_score = col
            elif val == "Listing":
                col_listing = col

        if col_price_week:
            ws_rank.cell(1, col_price_week, "September Price / 7 nights (CZK)")

        next_col = ws_rank.max_column + 1
        ws_rank.cell(1, next_col, "7 Consecutive Days in Sept?")
        ws_rank.cell(1, next_col + 1, "Sept Max Consecutive Free Days")
        ws_rank.cell(1, next_col + 2, "Sept Free Date Ranges")
        ws_rank.cell(1, next_col + 3, "Beer Tap Available")
        ws_rank.cell(1, next_col + 4, "Beer Tap Taps Count")
        ws_rank.cell(1, next_col + 5, "Better than Nový Svět (Pros)")
        ws_rank.cell(1, next_col + 6, "Worse than Nový Svět (Cons)")

        for r in range(2, ws_rank.max_row + 1):
            val_listing = str(ws_rank.cell(r, col_listing).value or "").strip() if col_listing else ""
            if val_listing in queue_by_listing:
                q_item = queue_by_listing[val_listing]
                if col_price_week and q_item["Price_7_Nights_CZK"] != "":
                    ws_rank.cell(r, col_price_week, q_item["Price_7_Nights_CZK"])
                if col_price_note and q_item["Price_Source_Label"] != "":
                    ws_rank.cell(r, col_price_note, q_item["Price_Source_Label"])
                if col_price_score:
                    ws_rank.cell(r, col_price_score, q_item["Price_Score"])
                if col_total_score:
                    ws_rank.cell(r, col_total_score, q_item["Total_Score"])

                ws_rank.cell(r, next_col, "YES" if q_item["Has_7_Consecutive_Days"] else "NO")
                ws_rank.cell(r, next_col + 1, q_item["Max_Consecutive_Days"])
                ws_rank.cell(r, next_col + 2, ", ".join(q_item["Consecutive_Ranges"]))
                ws_rank.cell(r, next_col + 3, q_item["Beer_Tap_Available"])
                ws_rank.cell(r, next_col + 4, q_item["Beer_Tap_Count"])
                ws_rank.cell(r, next_col + 5, "\n".join(f"+ {p}" for p in q_item.get("Pros_Vs_Novy_Svet", [])))
                ws_rank.cell(r, next_col + 6, "\n".join(f"- {c}" for c in q_item.get("Cons_Vs_Novy_Svet", [])))

        wb.save(dst_xlsx)
        print(f"📁 Generated updated workbook with September off-season pricing & 7-day checks: {dst_xlsx}")


if __name__ == "__main__":
    build_candidate_queue()
