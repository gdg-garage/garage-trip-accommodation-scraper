#!/usr/bin/env python3
"""
calculate_pragmatic_retreat_scores.py

Implements 'Scorer v2: Pragmatic Retreat 2026' based on user's methodical criteria:
1. Room Count & Privacy (8 min, 10-12 optimum, max 14; small rooms favored over giant bunk dorms)
2. Common Space, Tables, Nooks & Couches (seating, shisha/gaming nooks, deep couch comfort vs hard tavern benches)
3. Location & Nature (1 trail loop from doorstep; Orlické hory is neutral/acceptable, fresh region is bonus)
4. Catering & Food Delivery Feasibility (DEAL BREAKER)
5. Bathrooms (ideal 1:2 ratio to rooms)
6. Portable perks down-weighted (taps, projectors, TVs, toys, Lindr can be brought)
7. Price realism (<80k optimal, >100k heavily penalized)
8. Photo verification tagging: 'VERIFIED_WITH_PHOTOS' vs '⚠️ Preliminary - Photos Missing'
"""

import json
import csv
import os
import re
from typing import Dict, Any, Tuple

def parse_bathrooms_count(item: Dict[str, Any]) -> int:
    listing = str(item.get("Listing", ""))
    text = (item.get("Bedrooms_Bathrooms", "") + " " + item.get("Note", "") + " " + item.get("Common_Area_Desc", "")).lower()
    
    # Specific known property counts verified from listings & photos
    if "3649" in listing:
        return 7  # 7 bathrooms (1 per apartment) + 11 WCs
    if "5471" in listing:
        return 18 # Penzion Malovaný: en-suite in every room
    if "16467" in listing:
        return 7  # Chalupa Měšťan: 7 en-suite bathrooms
    if "10456" in listing:
        return 7  # Chalupa Pod Slunečnou: 7 en-suite bathrooms
    if "21177" in listing:
        return 13 # Chata Františkov: 13 en-suite bathrooms
    if "11079" in listing:
        return 8  # Veselá bouda: 8 bathrooms
    if "2940" in listing:
        return 7  # Statek U Pepíka: 7 bathrooms with WC
    if "2061" in listing:
        return 5  # Statek Tylov: 5 bathrooms, 6 WCs

    # Check apartment count with own bathroom (e.g. Nový Svět: 7 apartments, each with own bathroom)
    m_apt = re.search(r"(\d+)\s*(?:apartmánů|apartmány|apartmáneh|apartments).*?(?:vlastní|own)\s*(?:koupeln|sociál)", text)
    if m_apt:
        return int(m_apt.group(1))
        
    m = re.search(r"(\d+)\s*(?:koupelen|koupelny|koupelna|koupelnami|bathrooms|baths|sprch)", text)
    if m:
        return int(m.group(1))
    # Check if en-suite mentioned for each room
    if "každý pokoj má vlastní koupelnu" in text or "všech 8 pokojů vždy s vlastní koupelnou" in text or "na každém pokoji" in text or "vlastní sprchou" in text:
        return item.get("Rooms_Count", 0) or 8

    # Default fallback
    return 4

def parse_couches_info(item: Dict[str, Any]) -> Tuple[int, str]:
    """Returns couch score (0-8) and description."""
    listing = str(item.get("Listing", ""))
    desc = (item.get("Common_Area_Desc", "") + " " + item.get("Note", "")).lower()
    
    # Specific photo-verified property overrides
    if "3649" in listing:
        return 8, "TWO distinct deep couch zones (seats 10-12+ across main hall and lounge with 2 smart TVs)"
    if "2061" in listing: # Tylov: only bentwood chairs in 60m2 room; 2 armchairs in kids playroom
        return 1, "No deep couches in main 60 m² hall; only wooden dining chairs (2 armchairs in kids playroom)"
    if "16467" in listing: # Měšťan: no proper couches; daybeds & floor cushions in games hall
        return 2, "No proper living room couches; daybed wooden benches and floor cushions only"
    if "2940" in listing: # Statek U Pepíka: long banquet tables, secondary attic lounge
        return 4, "Attic lounge seating + banquet dining; no large central living room sofa"
    if "5471" in listing: # Malovaný: pension breakfast hall only
        return 1, "Pension dining hall with ~40 chairs; no living room lounge or couches"

    # Check dual couch zones
    if "two couch zones" in desc or "dvě zóny s gaučem" in desc or "dvě sedací soupravy" in desc:
        return 8, "TWO distinct couch zones (seats 8-12+ across main hall and lounge)"

    # Penalty if only wooden chairs/benches
    if "jen lavice" in desc or "pouze lavice" in desc or "no proper couches" in desc or ("lavice" in desc and not any(k in desc for k in ["gauč", "sofa", "pohovka", "sedací"])):
        return 0, "No deep couch; only wooden tavern chairs/benches"

    has_large_couch = any(k in desc for k in ["sedací souprava", "velká sedací", "rohový gauč", "rohová sedací", "u-sofa", "u-sedací", "leather sofa", "chesterfield", "velká pohovka", "pohovky", "sofa set", "corner sofa"])
    has_couch = any(k in desc for k in ["gauč", "sofa", "pohovka", "sedací", "daybed", "couch"])
    has_secondary_lounge = item.get("Has_Secondary_Room") or any(k in desc for k in ["druhá společenská", "druhý sál", "herna", "salon", "attic lounge", "patro s posezením", "vinárna", "sklípek", "veranda", "second dining", "game room"])

    if has_large_couch and has_secondary_lounge:
        return 8, "Primary large lounge sofa + secondary breakout lounge/nook"
    if has_large_couch:
        return 6, "Spacious primary living room sofa set (seats 6+)"
    if has_couch and has_secondary_lounge:
        return 6, "Compact sofa set + secondary lounge room"
    if has_couch:
        return 4, "Compact sofa corner (seats 3-4)"
    return 1, "Limited couch seating (mostly dining chairs)"

def evaluate_catering_feasibility(item: Dict[str, Any]) -> Tuple[int, str]:
    """Evaluates feasibility of lunch menu delivery and catering."""
    loc = (item.get("Location", "") + " " + item.get("Name", "")).lower()
    
    # 1. Major town proximity / verified delivery
    if any(k in loc for k in ["králíky", "prostřední lipka", "benešov", "mrač", "tišnov", "rašov", "šumperk", "bohdíkov", "sedlčany", "červená voda"]):
        return 15, "Verified town delivery nearby (DámeJídlo/Foodora or established local restaurant lunch deliveries)"
    
    # 2. Active mountain tourist hub with hotel / pension restaurants
    if any(k in loc for k in ["teplice nad metují", "broumov", "benecko", "herlíkovice", "strážné", "vrchlabí", "deštné", "rychnov", "jeseník", "lipová"]):
        return 12, "Active mountain center; menu delivery available from nearby hotel/pension restaurants"
        
    # 3. Rural village / local pub delivery
    if any(k in loc for k in ["lomnice", "tylov", "rýmařov", "bruntál", "horní stropnice", "nové hrady", "svébohy", "kounov", "bystré", "nedvězí"]):
        return 10, "Local village delivery; requires pre-ordering from local pub/inn within 5-10 km"
        
    # 4. Remote / isolated
    if any(k in loc for k in ["samot", "hřeben", "kvilda", "horní vltavice", "krušné"]):
        return 6, "Remote location; limited delivery coverage (mostly grocery self-haul)"
        
    return 10, "Standard delivery from nearest municipal hub (within 8-12 km)"

def evaluate_pragmatic_score(item: Dict[str, Any]) -> Dict[str, Any]:
    rooms = item.get("Rooms_Count", 0) or 0
    cap = item.get("Capacity_Total", 0) or 0
    p7 = float(item.get("Price_7_Nights_CZK") or 0)
    in_orlicke = item.get("In_Orlicke_Hory", False)
    fresh_score = float(item.get("Score_Visual_Freshness", 6.0) or 6.0)
    
    # -------------------------------------------------------------
    # 1. Rooms & Privacy (Max 25 pts)
    # -------------------------------------------------------------
    rooms_pts = 0.0
    rooms_note = ""
    if rooms < 8:
        rooms_pts = 4.0  # Failed minimum 8 rooms
        rooms_note = f"Only {rooms} rooms (fails 8 room minimum; cramped privacy for 25+)"
    elif rooms == 8:
        rooms_pts = 14.0
        rooms_note = "8 rooms (acceptable minimum for 25+; avg ~3.2 beds/room)"
    elif rooms == 9:
        rooms_pts = 17.0
        rooms_note = "9 rooms (solid bedroom count)"
    elif rooms in [10, 11, 12]:
        rooms_pts = 22.0
        rooms_note = f"{rooms} rooms (OPTIMAL SWEET SPOT: intimate 2-3 bed suites for families/couples)"
    elif rooms >= 13:
        rooms_pts = 25.0
        rooms_note = f"{rooms} rooms (BENCHMARK LUXURY: allows dedicating spare rooms for board games, shisha, escape rooms)"

    # Bed density modifier
    avg_beds = (cap / rooms) if rooms > 0 else 4.0
    if avg_beds <= 2.5:
        rooms_pts += 2.0
        rooms_note += "; low bed density (mostly doubles/triples)"
    elif avg_beds >= 4.0:
        rooms_pts -= 6.0
        rooms_note += f"; ⚠️ HIGH BED DENSITY ({avg_beds:.1f} beds/room in bunk dorms)"

    # -------------------------------------------------------------
    # 2. Common Space, Tables, Nooks & Couches (Max 25 pts)
    # -------------------------------------------------------------
    chairs = item.get("Seating_Chairs_Count", 0) or 0
    tables_pts = 0.0
    if chairs >= 24:
        tables_pts = 12.0
    elif chairs >= 18:
        tables_pts = 10.0
    elif chairs >= 14:
        tables_pts = 8.0  # Evča argument: 14-16 chairs workable with rotation
    else:
        tables_pts = 5.0

    couch_pts, couch_note = parse_couches_info(item)
    
    # Acoustic separation & nooks
    has_secondary = item.get("Has_Secondary_Room", False)
    nooks_pts = 5.0 if has_secondary else 2.0
    
    common_pts = round(tables_pts + couch_pts + nooks_pts, 1)
    common_note = f"Chairs: ~{chairs} ({tables_pts:.0f} pts) &middot; Couches: {couch_note} ({couch_pts:.0f} pts) &middot; {'Dual halls / nooks' if has_secondary else 'Single common hall'} ({nooks_pts:.0f} pts)"

    # -------------------------------------------------------------
    # 3. Catering & Food Delivery Feasibility (Max 15 pts) - DEAL BREAKER
    # -------------------------------------------------------------
    catering_pts, catering_note = evaluate_catering_feasibility(item)

    # -------------------------------------------------------------
    # 4. Bathrooms Ratio (Max 15 pts)
    # -------------------------------------------------------------
    baths = parse_bathrooms_count(item)
    ratio = (baths / rooms) if rooms > 0 else 0.3
    bath_pts = 0.0
    bath_note = ""
    if "5343" in str(item.get("Listing", "")):
        # Chalupa Jindřiška: communal gender-segregated shower stalls on ground floor
        bath_pts = 6.0
        bath_note = "Hostel layout: gender-segregated communal shower stalls on ground floor (shared)"
    elif ratio >= 0.8:
        bath_pts = 15.0
        bath_note = f"{baths} baths for {rooms} rooms (1:1 near-private en-suite; zero queues)"
    elif ratio >= 0.45:
        bath_pts = 12.0
        bath_note = f"{baths} baths for {rooms} rooms (1 bath per ~2 rooms; solid retreat standard)"
    elif ratio >= 0.3:
        bath_pts = 7.0
        bath_note = f"{baths} baths for {rooms} rooms (1 bath per 3 rooms; minor morning rush)"
    else:
        bath_pts = 3.0
        bath_note = f"{baths} baths for {rooms} rooms (⚠️ Severe bottleneck: 1 bath per 4+ rooms)"

    # -------------------------------------------------------------
    # 5. Location, Trails & Scenery (Max 10 pts)
    # -------------------------------------------------------------
    # User realized: we only go outside once for a 5-10km loop hike directly from house.
    # Orlické hory is acceptable/neutral (0 pts), fresh region gives +5 bonus.
    loc_pts = 5.0  # Base for hiking trails out the door
    loc_note = "Direct trail access for team loop hike"
    if not in_orlicke:
        loc_pts += 5.0
        loc_note += " + Fresh region novelty bonus (+5 pts)"
    else:
        loc_note += " &middot; Orlické hory (familiar, but great hiking trail access)"

    # -------------------------------------------------------------
    # 6. Aesthetic Freshness (Ota Approved) (Max 10 pts)
    # -------------------------------------------------------------
    # Novy Svet confirmed modern and clean by user ("everything modern for a very good price")
    if "3649" in str(item.get("Listing", "")):
        fresh_score = max(fresh_score, 8.5)

    # Penalize strange layouts or 1980s aged wood
    if fresh_score >= 8.5:
        fresh_pts = 10.0
        fresh_eval = "10/10 Modern, tasteful, fresh design (Ota approved)"
    elif fresh_score >= 7.0:
        fresh_pts = 7.0
        fresh_eval = "Solid clean standard"
    elif fresh_score >= 5.0:
        fresh_pts = 3.0
        fresh_eval = "Visibly aged / quirky layout (e.g. Mazlíků 5.5)"
    else:
        fresh_pts = 1.0
        fresh_eval = "Outdated 1980s rustic/hostel"

    # -------------------------------------------------------------
    # 7. Price Modifiers (-15 to +4 pts)
    # -------------------------------------------------------------
    price_mod = 0.0
    price_note = ""
    if p7 <= 0:
        price_mod = -2.0
        price_note = "Price on request / unconfirmed"
    elif p7 < 40000:
        price_mod = -6.0
        price_note = f"⚠️ Suspiciously low price (<40k: {int(p7):,} Kč) - risk of cramped hostel conditions (-6 pts)"
    elif p7 < 60000:
        price_mod = 4.0
        price_note = f"Frugal value (40k-60k CZK: {int(p7):,} Kč) (+4 pts)"
    elif p7 <= 80000:
        price_mod = 0.0
        price_note = f"Fair market value (60k-80k CZK: {int(p7):,} Kč)"
    elif p7 <= 100000:
        price_mod = -4.0
        price_note = f"High tier (80k-100k CZK: {int(p7):,} Kč) (-4 pts)"
    else:
        price_mod = -12.0
        price_note = f"💸 Exceeds 100k budget ceiling ({int(p7):,} Kč) (-12 pts)"

    # -------------------------------------------------------------
    # 8. Portable & Minor Perks (Max 5 pts)
    # -------------------------------------------------------------
    portable_pts = 0.0
    if item.get("NTH_Wellness_Features_Count", 0) > 0:
        portable_pts += 2.0  # Sauna
    if item.get("NTH_Has_Pool", False):
        portable_pts += 1.0  # Pool
    if item.get("NTH_Beer_Tap_Count", 0) > 0:
        portable_pts += 1.0  # Built-in tap (Lindr can be brought)
    portable_pts = min(portable_pts, 5.0)

    # -------------------------------------------------------------
    # Photo Verification Check
    # -------------------------------------------------------------
    folder = item.get("Photos_Folder", "")
    has_disk_photos = False
    photo_count = 0
    if folder and os.path.exists(folder):
        files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        photo_count = len(files)
        # Require at least 10 photos on disk for verified status
        if photo_count >= 10:
            has_disk_photos = True

    photo_status = "VERIFIED_WITH_PHOTOS" if has_disk_photos else "PRELIMINARY_PHOTOS_MISSING"
    photo_label = f"📸 Verified with Photos ({photo_count} photos)" if has_disk_photos else f"⚠️ Preliminary - Photos Missing / Incomplete ({photo_count} photos)"

    # Team comments veto / rejection penalty
    team_tc = ((item.get("Team_Comment") or "") + " " + (item.get("Tivvit_Note") or "")).lower()
    review_penalty = 0.0
    if "just no" in team_tc or "nee" in team_tc or "neni kde sedet" in team_tc:
        review_penalty -= 15.0
    if "2180" in item.get("Listing", ""):
        review_penalty -= 6.0  # Mazlíků strange layout & aged
    elif "22293" in item.get("Listing", ""):
        review_penalty -= 6.0  # Termix host silence

    # -------------------------------------------------------------
    # Total Pragmatic Score (0 - 100 scale)
    # -------------------------------------------------------------
    total_pragmatic = rooms_pts + common_pts + catering_pts + bath_pts + loc_pts + fresh_pts + price_mod + portable_pts + review_penalty
    total_pragmatic = max(10.0, min(100.0, round(total_pragmatic, 1)))

    return {
        "Score_Pragmatic_2026": total_pragmatic,
        "Photo_Validation_Status": photo_status,
        "Photo_Validation_Label": photo_label,
        "Has_Disk_Photos": has_disk_photos,
        "Breakdown": {
            "rooms_privacy": round(rooms_pts, 1),
            "rooms_note": rooms_note,
            "common_space_couches": round(common_pts, 1),
            "common_note": common_note,
            "catering_delivery": round(catering_pts, 1),
            "catering_note": catering_note,
            "bathrooms_ratio": round(bath_pts, 1),
            "bath_note": bath_note,
            "location_trails": round(loc_pts, 1),
            "loc_note": loc_note,
            "aesthetic_freshness": round(fresh_pts, 1),
            "fresh_eval": fresh_eval,
            "price_modifier": round(price_mod, 1),
            "price_note": price_note,
            "portable_perks": round(portable_pts, 1),
            "review_penalty": round(review_penalty, 1)
        }
    }

def main():
    with open("data/candidates_must_nice_all.json", "r", encoding="utf-8") as f:
        candidates = json.load(f)

    print(f"Loaded {len(candidates)} candidates. Evaluating Scorer v2: Pragmatic Retreat 2026...")

    for c in candidates:
        eval_res = evaluate_pragmatic_score(c)
        c["Score_Pragmatic_2026"] = eval_res["Score_Pragmatic_2026"]
        c["Photo_Validation_Status"] = eval_res["Photo_Validation_Status"]
        c["Photo_Validation_Label"] = eval_res["Photo_Validation_Label"]
        c["Has_Disk_Photos"] = eval_res["Has_Disk_Photos"]
        c["Score_Pragmatic_Breakdown"] = eval_res["Breakdown"]

    # Sort all candidates by Score_Pragmatic_2026 descending
    candidates.sort(key=lambda x: x.get("Score_Pragmatic_2026", 0), reverse=True)

    for rank, c in enumerate(candidates, start=1):
        c["Rank_Pragmatic_2026"] = rank

    # Write back to candidates_must_nice_all.json
    with open("data/candidates_must_nice_all.json", "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    # Write back to queue_candidates_50plus.json
    with open("queue_candidates_50plus.json", "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    # Write to queue_candidates_50plus.csv
    if candidates:
        keys = list(candidates[0].keys())
        # Flatten breakdown for CSV
        with open("queue_candidates_50plus.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            headers = [
                "Rank_Pragmatic_2026", "Name", "Listing", "Score_Pragmatic_2026", "Total_Score_Legacy",
                "Photo_Status", "Rooms_Count", "Capacity_Total", "Price_7_Nights_CZK", "Location",
                "Rooms_Score", "Common_Score", "Catering_Score", "Baths_Score", "Location_Score",
                "Fresh_Score", "Price_Mod", "Direct_Url"
            ]
            writer.writerow(headers)
            for c in candidates:
                b = c.get("Score_Pragmatic_Breakdown", {})
                writer.writerow([
                    c.get("Rank_Pragmatic_2026"),
                    c.get("Name"),
                    c.get("Listing"),
                    c.get("Score_Pragmatic_2026"),
                    c.get("Total_Score"),
                    c.get("Photo_Validation_Label"),
                    c.get("Rooms_Count"),
                    c.get("Capacity_Total"),
                    c.get("Price_7_Nights_CZK"),
                    c.get("Location"),
                    b.get("rooms_privacy"),
                    b.get("common_space_couches"),
                    b.get("catering_delivery"),
                    b.get("bathrooms_ratio"),
                    b.get("location_trails"),
                    b.get("aesthetic_freshness"),
                    b.get("price_modifier"),
                    c.get("Url")
                ])

    print("✅ Completed evaluation! Top 15 Pragmatic Retreat Contenders:")
    for c in candidates[:15]:
        b = c["Score_Pragmatic_Breakdown"]
        print(f"#{c['Rank_Pragmatic_2026']} {c['Name']} ({c['Listing']}) - Score: {c['Score_Pragmatic_2026']} pts | {c['Photo_Validation_Label']}")
        print(f"   Rooms: {c.get('Rooms_Count')} | Beds: {c.get('Capacity_Total')} | Price: {c.get('Price_7_Nights_CZK')} Kč | Loc: {c.get('Location')}")
        print(f"   Breakdown: Rooms={b['rooms_privacy']}, Common/Couches={b['common_space_couches']}, Catering={b['catering_delivery']}, Baths={b['bathrooms_ratio']}, PriceMod={b['price_modifier']}")

if __name__ == "__main__":
    main()
