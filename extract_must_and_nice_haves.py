#!/usr/bin/env python3
"""
Comprehensive Extractor and Scorer for Must-Haves and Nice-To-Haves.
Evaluates all accommodations against the retreat group's exact criteria:

MUST-HAVES:
1. No veto (veto is a no go)
2. Free slot in September for a week-long vacation (>= 7 consecutive days free)
3. >= 24 spots (capacity >= 24, capped at 30 for scoring)
4. >= 7 rooms (or annex/glamping/separate room/separate house)
5. Seating for >= 16 people (or office/dancing room/yoga room/multipurpose hall)

NICE-TO-HAVES:
1. TV or projector count
2. Beer tap count
3. Wellness (sauna, hot tub, whirlpool, bath barrel)
4. Pool (heated, indoor, covered, outdoor)
5. Outdoor seating (pergola, covered terrace, garden tables)
6. Indoor sofa seating (couches, lounge sofas)
7. Higher count of toilets & high ratio (toilets count, toilets per room, people per toilet)
8. Catering / professional kitchen
9. Child's corner (indoor playroom)
10. Child's outdoor playground (sandbox, swings, slide, trampoline)

PRICE & VALUE:
- Evaluates value-for-money, price per person for 7 nights, and applies penalty if high price with missing amenities.
"""

import csv
import glob
import json
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup
import openpyxl

from extract_availability import extract_september_availability
from extract_beer_tap import extract_beer_tap_info
from build_candidate_queue import resolve_photos

RANKING_CSV = "data/sheets_export/ranking.csv"
STRUCTURED_JSON = "properties_structured.json"
QUEUE_JSON = "queue_candidates_50plus.json"
OUTPUT_ALL_JSON = "data/candidates_must_nice_all.json"
OUTPUT_QUEUE_JSON = "queue_candidates_50plus.json"
OUTPUT_QUEUE_CSV = "queue_candidates_50plus.csv"
OUTPUT_WORKBOOK = "sheet_updated_with_extractors.xlsx"


def clean_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def get_html_soup_and_text(listing: str) -> Tuple[Optional[BeautifulSoup], str, str]:
    """Retrieve BeautifulSoup, main text, and source HTML filepath."""
    m = re.search(r"(\d+)", listing)
    if m and not listing.startswith("Booking"):
        oid = m.group(1)
        matches = glob.glob(f"html/*o{oid}.html") or glob.glob(f"html/*{oid}*.html")
        if matches:
            try:
                with open(matches[0], "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                soup = BeautifulSoup(content, "html.parser")
                main_elem = soup.find(class_="chata") or soup.find(class_="p-detail") or soup.find("main") or soup.body
                main_text = main_elem.get_text(" ", strip=True) if main_elem else soup.get_text(" ", strip=True)
                return soup, main_text, matches[0]
            except Exception:
                pass
    elif listing.startswith("Booking"):
        slug = listing.replace("Booking", "").strip()
        matches = glob.glob(f"booking_html/{slug}.html") or glob.glob(f"booking_html/*{slug}*.html")
        if matches:
            try:
                with open(matches[0], "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                soup = BeautifulSoup(content, "html.parser")
                main_elem = soup.find("div", id="bodyconstraint") or soup.find("main") or soup.body
                main_text = main_elem.get_text(" ", strip=True) if main_elem else soup.get_text(" ", strip=True)
                return soup, main_text, matches[0]
            except Exception:
                pass
    return None, "", ""


def resolve_real_url(listing: str, oid: Optional[str], soup: Optional[BeautifulSoup], html_path: str = "") -> str:
    """Resolve the genuine, working URL for e-chalupy and Booking listings."""
    if listing.startswith("e-chalupy") or (oid and not listing.startswith("Booking")):
        if soup:
            og = soup.find("meta", property="og:url")
            if og and og.get("content"):
                u = og["content"].strip()
                if u.startswith("http://"):
                    u = "https://" + u[7:]
                if u.endswith(".php"):
                    return u
        if oid:
            matches = glob.glob(f"html/*-o{oid}.html") or glob.glob(f"html/*_{oid}.html") or glob.glob(f"html/*{oid}*.html")
            if matches:
                try:
                    with open(matches[0], "r", encoding="utf-8", errors="ignore") as f:
                        for _ in range(60):
                            line = f.readline()
                            if not line: break
                            if 'property="og:url"' in line or "property='og:url'" in line:
                                m_url = re.search(r'content=[\"\']([^\"\']+)[\"\']', line)
                                if m_url:
                                    u = m_url.group(1).strip()
                                    if u.startswith("http://"): u = "https://" + u[7:]
                                    if u.endswith(".php"): return u
                except Exception:
                    pass
            return f"https://www.e-chalupy.cz/ubytovani/{oid}"
        return "https://www.e-chalupy.cz"
    elif listing.startswith("Booking"):
        slug = listing.replace("Booking", "").strip()
        if soup:
            can = soup.find("link", rel="canonical")
            if can and can.get("href"):
                return can["href"].strip()
            og = soup.find("meta", property="og:url")
            if og and og.get("content"):
                return og["content"].strip()
        return f"https://www.booking.com/hotel/cz/{slug}.html"
    return "https://www.e-chalupy.cz"


def extract_capacity(r: Dict[str, Any], sp: Dict[str, Any], html_text: str) -> Tuple[int, int, bool]:
    """Extract total capacity spots and effective score spots (capped at 30)."""
    cap_text = r.get("Capacity", "")
    m = re.search(r"(\d+)\s*(?:beds|lůž|osob|person|people|\+)", cap_text, re.I)
    if not m:
        m = re.search(r"(\d+)", cap_text)
    
    cap = int(m.group(1)) if m else 0
    if cap == 0 and sp.get("capacity_total"):
        try:
            cap = int(sp["capacity_total"])
        except Exception:
            pass

    if cap == 0 and html_text:
        m_html = re.search(r"Kapacita\s*[:\s]*(\d+)", html_text, re.I)
        if m_html:
            cap = int(m_html.group(1))

    effective_cap = min(30, cap)
    passes = (cap >= 24)
    return cap, effective_cap, passes


def extract_rooms_and_annex(r: Dict[str, Any], sp: Dict[str, Any], html_text: str) -> Tuple[int, bool, str, bool]:
    """
    Extract room count and check if accommodation has an annex/glamping/separate house.
    Requirement: >= 7 rooms OR separate annex/glamping/separate room/separate house.
    """
    rooms_text = r.get("Bedrooms & bathrooms", "")
    comb = f"{rooms_text} {r.get('Common area (what photos show)', '')} {r.get('Note', '')} {html_text[:2000]}"
    
    # 1. Annex / glamping / separate house detection
    has_annex = False
    annex_details = []

    if re.search(r"\bglamping\b", comb, re.I):
        has_annex = True
        annex_details.append("Glamping available")
    if re.search(r"(?:ve vedlejší budově|samostatný domek|výměnek|chatičk[ay]|chatk[ay]|druhý objekt|druhý dům|2 domy|2 budovy|apartmán v podkroví)", comb, re.I):
        has_annex = True
        annex_details.append("Separate cottage/annex building")
    if re.search(r"(?:apartmány v samostatné|vedlejší dům|samostatná chata)", comb, re.I):
        has_annex = True
        annex_details.append("Separate house on plot")

    # 2. Count rooms / bedrooms / apartments
    m_rms = re.search(r"(\d+)\s*(?:bed(?:room)?s|pokoj[ůe]?|ložnic[eí]?|rooms)", rooms_text, re.I)
    if not m_rms:
        # Sum apartments/suites or bedrooms in apartments
        m_apts = re.search(r"(\d+)\s*(?:apartm[aá]n[ůe]?|studios|units)", rooms_text, re.I)
        if m_apts:
            apts_cnt = int(m_apts.group(1))
            # Check if each apartment has multiple bedrooms
            m_mult = re.search(r"(\d+)\s*(?:apartm[aá]n[ůe]?).*?(\d+)\s*(?:ložnic|pokoj)", rooms_text, re.I)
            if m_mult:
                rms = int(m_mult.group(1)) * int(m_mult.group(2))
            else:
                rms = apts_cnt
        else:
            rms = 0
    else:
        rms = int(m_rms.group(1))

    if rms == 0 and sp.get("bedrooms_count"):
        try:
            rms = int(sp["bedrooms_count"])
        except Exception:
            pass

    # Look for compound "6 double rooms + 2 four-bed rooms"
    m_compound = re.findall(r"(\d+)\s*(?:dvoulůž|čtyřlůž|třílůž|pokoj)", rooms_text, re.I)
    if m_compound and len(m_compound) >= 2:
        compound_sum = sum(int(x) for x in m_compound[:4])
        if compound_sum > rms:
            rms = compound_sum

    if "18555" in str(r.get("Listing", "")) or "hostačov" in str(r.get("Name", "")).lower():
        return 6, False, "6 rooms (rooms #1 & #2 are dormitories; outdoor glamping tents not counted as 7th room)", False

    passes = (rms >= 7 or has_annex)
    annex_str = "; ".join(annex_details) if annex_details else ("None" if not has_annex else "Yes")
    return rms, has_annex, annex_str, passes


def extract_seating_and_secondary_rooms(r: Dict[str, Any], sp: Dict[str, Any], html_text: str) -> Tuple[int, bool, str, bool]:
    """
    Extract dining table seating chairs count and check for secondary activity rooms
    (office, dancing room, yoga room, second hall, sál, tělocvična).
    Requirement: >= 16 chairs OR secondary activity room.
    """
    ch_text = r.get("Chairs in common area (est.)", "")
    comm_text = r.get("Common area (what photos show)", "")
    comb = f"{ch_text} {comm_text} {r.get('Note', '')} {html_text[:2500]}"

    # 1. Chairs count
    m_ch = re.search(r"~?(\d+)\s*(?:chairs|židl|míst|seats)", ch_text, re.I)
    if not m_ch:
        m_ch = re.search(r"~?(\d+)", ch_text)
    chairs = int(m_ch.group(1)) if m_ch else 0
    
    if chairs == 0 and sp.get("tables_seating_capacity"):
        try:
            chairs = int(sp["tables_seating_capacity"])
        except Exception:
            pass

    # 2. Secondary room detection (office, dancing room, yoga room, multipurpose hall)
    has_sec = False
    sec_details = []

    if re.search(r"(?:jóga|yoga)", comb, re.I):
        has_sec = True
        sec_details.append("Yoga / exercise space")
    if re.search(r"(?:tančírna|taneční\s+sál)", comb, re.I):
        has_sec = True
        sec_details.append("Dancing hall")
    if re.search(r"(?:kancelář|coworking|zasedačk|meeting\s+room|jednací\s+místnost)", comb, re.I):
        has_sec = True
        sec_details.append("Office / meeting room")
    if re.search(r"(?:druhý\s+sál|samostatný\s+sál|společenský\s+sál|víceúčelový\s+sál|tělocvičn|konferenční|stodola\s+s\s+posezením|herna\s+s\s+posezením)", comb, re.I):
        has_sec = True
        sec_details.append("Multipurpose activity hall / barn")

    passes = (chairs >= 16 or has_sec)
    sec_str = "; ".join(sec_details) if sec_details else ("None" if not has_sec else "Yes")
    return chairs, has_sec, sec_str, passes


def extract_tv_and_projector(r: Dict[str, Any], sp: Dict[str, Any], html_text: str) -> Tuple[int, bool, str, float]:
    """Extract TV / Projector count and details."""
    comb = f"{r.get('Common area (what photos show)', '')} {r.get('Note', '')} {html_text}"
    
    has_proj = bool(re.search(r"(?:projektor|promítací\s+plátno|dataprojektor|projekční\s+stěna)", comb, re.I))
    
    # TV count detection
    tv_count = 0
    m_tvs = re.search(r"(\d+)\s*x?\s*(?:televiz|TV|plazm)", comb, re.I)
    if m_tvs:
        tv_count = int(m_tvs.group(1))
    elif re.search(r"(?:TV\s+na\s+každém\s+pokoji|televize\s+ve\s+všech\s+pokojích)", comb, re.I):
        tv_count = 8
    elif re.search(r"(?:dv[ěa]\s+televiz|2\s+TV|two\s+couch\s+zones\s+each\s+with\s+TV)", comb, re.I):
        tv_count = 2
    elif re.search(r"\b(?:TV|televize|smart\s*tv)\b", comb, re.I) or sp.get("projector_or_large_tv"):
        tv_count = 1

    total_screens = tv_count + (1 if has_proj else 0)
    details = []
    if tv_count > 0:
        details.append(f"{tv_count}x TV")
    if has_proj:
        details.append("Projector with screen")

    # Score: 0 -> 0, 1 -> 2.5, 2 -> 3.5, 3+ -> 5.0
    if total_screens == 0:
        score = 0.0
    elif total_screens == 1:
        score = 2.5
    elif total_screens == 2:
        score = 3.5
    elif total_screens == 3:
        score = 4.2
    else:
        score = 5.0

    return total_screens, has_proj, " + ".join(details) if details else "None", score


def extract_wellness(r: Dict[str, Any], sp: Dict[str, Any], html_text: str) -> Tuple[int, bool, bool, str, float]:
    """Extract wellness features (sauna, hot tub, whirlpool, bath barrel)."""
    sauna_desc = r.get("Sauna", "") or ""
    comb = f"{sauna_desc} {r.get('Note', '')} {html_text}"

    has_sauna = False
    sauna_type = "None"
    if sauna_desc and "no" not in sauna_desc.lower() and "ne" not in sauna_desc.lower():
        has_sauna = True
        sauna_type = sauna_desc
    elif sp.get("has_sauna") is True:
        has_sauna = True
        sauna_type = sp.get("sauna_type") or "Finnish sauna"
    elif re.search(r"\bsaun[ay]\b", comb, re.I):
        has_sauna = True
        sauna_type = "Sauna on site"

    has_hot_tub = False
    hot_tub_type = ""
    if re.search(r"(?:vířivk|whirlpool|jacuzzi|koupací\s+sud|hot\s*tub)", comb, re.I) or sp.get("has_hot_tub_or_whirlpool"):
        has_hot_tub = True
        hot_tub_type = "Hot tub / whirlpool / barrel"

    count = (1 if has_sauna else 0) + (1 if has_hot_tub else 0)
    details = []
    if has_sauna:
        details.append(f"Sauna ({sauna_type[:30]})")
    if has_hot_tub:
        details.append(hot_tub_type)

    if count == 0:
        score = 0.0
    elif count == 1:
        score = 3.0
    else:
        score = 5.0

    return count, has_sauna, has_hot_tub, ", ".join(details) if details else "None", score


def extract_pool(r: Dict[str, Any], sp: Dict[str, Any], html_text: str) -> Tuple[bool, str, float]:
    """Extract pool availability and type (indoor, heated, outdoor, none)."""
    pool_desc = (r.get("Pool") or "").strip()
    comb = f"{pool_desc} {html_text[:1500]}"
    
    has_pool = False
    pool_type = "None"
    score = 0.0

    if pool_desc and "no" not in pool_desc.lower() and "ne" not in pool_desc.lower() and "není" not in pool_desc.lower():
        has_pool = True
    elif sp.get("has_pool") is True:
        has_pool = True

    if has_pool:
        if re.search(r"(?:vnitřní|indoor|krytý\s+vyhřívaný)", comb, re.I):
            pool_type = "Indoor Heated Pool"
            score = 5.0
        elif re.search(r"(?:vyhřívaný|tepelným\s+čerpadlem|se\nbsp;zastřešením|teleskopick|saltwater|slaná\s+voda)", comb, re.I):
            pool_type = "Covered / Heated Saltwater Pool"
            score = 4.5
        elif re.search(r"(?:zastřešený)", comb, re.I):
            pool_type = "Covered Outdoor Pool"
            score = 4.0
        else:
            pool_type = "Outdoor Pool"
            score = 3.0

    return has_pool, pool_type, score


def extract_outdoor_seating(r: Dict[str, Any], html_text: str) -> Tuple[bool, str, float]:
    """Extract outdoor seating presence (pergola, covered terrace, garden dining)."""
    out_desc = r.get("Outdoor", "") or ""
    comb = f"{out_desc} {r.get('Common area (what photos show)', '')} {html_text[:2000]}"
    
    has_out = False
    details = []
    if re.search(r"(?:pergola|krytá\s+pergola)", comb, re.I):
        has_out = True
        details.append("Covered pergola")
    if re.search(r"(?:krytá\s+terasa|velká\s+terasa|terasa\s+s\s+posezením|terrace\s+table)", comb, re.I):
        has_out = True
        details.append("Terrace dining")
    if re.search(r"(?:zahradní\s+posezení|venkovní\s+posezení|picnic\s+tables|zahradní\s+nábytek)", comb, re.I):
        has_out = True
        details.append("Outdoor seating & tables")

    score = 3.0 if has_out else 0.0
    return has_out, "; ".join(details) if details else "None", score


def extract_indoor_sofa(r: Dict[str, Any], html_text: str) -> Tuple[bool, str, float]:
    """Extract indoor sofa seating presence (couch zones, living room sofas)."""
    comm_desc = r.get("Common area (what photos show)", "") or ""
    comb = f"{comm_desc} {r.get('Note', '')} {html_text[:2000]}"
    
    has_sofa = bool(re.search(r"(?:sedací\s+souprava|sedačk|gauč|pohovk|\bsofa\b|křesl|couch|couches|armchair|armchairs|futon)", comb, re.I))
    details = "Living room couch/sofa lounge zone" if has_sofa else "Dining tables with chairs only"
    score = 3.0 if has_sofa else 0.0
    return has_sofa, details, score


def extract_toilets(r: Dict[str, Any], sp: Dict[str, Any], rooms_cnt: int, cap: int) -> Tuple[int, float, float, float]:
    """Extract toilet count, toilets per room, people per toilet, and toilet ratio score."""
    rooms_text = r.get("Bedrooms & bathrooms", "")
    m = re.search(r"(\d+)\s*(?:x\s*)?(?:WC|toalet|záchod)", rooms_text, re.I)
    toilets = int(m.group(1)) if m else 0

    if toilets == 0 and sp.get("toilets_count"):
        try:
            toilets = int(sp["toilets_count"])
        except Exception:
            pass

    if toilets == 0:
        # Fallback based on bathroom mentions
        m_bath = re.search(r"(\d+)\s*(?:koupelen|bathrooms)", rooms_text, re.I)
        if m_bath:
            toilets = int(m_bath.group(1))
        else:
            toilets = max(2, rooms_cnt // 2)

    toilets_per_room = round(toilets / max(1, rooms_cnt), 2)
    people_per_toilet = round(cap / max(1, toilets), 1)

    # Score: 5 if >= 1.0 per room (or private baths in all rooms); 3.5 if 0.6-0.9; 2.0 if 0.4-0.5; 1.0 if <0.4
    if toilets_per_room >= 1.0 or "each apartment with own bathroom" in rooms_text or "every room has its own" in rooms_text:
        score = 5.0
    elif toilets_per_room >= 0.7:
        score = 4.0
    elif toilets_per_room >= 0.5:
        score = 3.0
    else:
        score = 1.5

    return toilets, toilets_per_room, people_per_toilet, score


def extract_catering(r: Dict[str, Any], html_text: str) -> Tuple[bool, str, float]:
    """Extract catering or professional kitchen availability."""
    kit_desc = r.get("Kitchen", "") or ""
    comb = f"{kit_desc} {r.get('Note', '')} {html_text[:2500]}"
    
    has_cat = bool(re.search(r"(?:catering|stravování|polopenze|snídaně|restaurace|nerezov|profi\s*kuchyň|gastro|catering\s*kitchen|buffet\s*counter)", comb, re.I))
    details = "Catering / Gastro catering kitchen" if has_cat else "Standard self-catering kitchen"
    score = 3.0 if has_cat else 0.0
    return has_cat, details, score


def extract_child_facilities(r: Dict[str, Any], html_text: str) -> Tuple[bool, str, float, bool, str, float]:
    """Extract child indoor corner and child outdoor playground."""
    comb = f"{r.get('Common area (what photos show)', '')} {r.get('Outdoor', '')} {r.get('Note', '')} {html_text[:2500]}"
    
    # 1. Indoor play corner
    has_corner = bool(re.search(r"(?:dětský\s+koutek|dětská\s+herna|hrací\s+kout|playroom\s+with\s+toys|dětský\s+pokoj\s+s\s+hračkami)", comb, re.I))
    corner_score = 2.0 if has_corner else 0.0
    corner_desc = "Indoor children's play corner" if has_corner else "None"

    # 2. Outdoor playground
    has_play = bool(re.search(r"(?:dětské\s+hřiště|pískoviště|trampolín|houpačk|skluzavk|prolézačk|playground)", comb, re.I))
    play_score = 2.0 if has_play else 0.0
    play_desc = "Outdoor playground with sandbox/trampoline" if has_play else "None"

    return has_corner, corner_desc, corner_score, has_play, play_desc, play_score


def extract_pets_allowed(r: Dict[str, Any], soup: Optional[BeautifulSoup], html_text: str) -> Tuple[bool, str, float]:
    """
    Extract whether pets / dogs are allowed at the accommodation.
    Returns (pets_allowed, pets_details, pets_score).
    Rewards properties that welcome pets with a +2.0 pts benefit.
    """
    note = str(r.get("Note", ""))
    team = str(r.get("Team_Comment", ""))
    tiv = str(r.get("Tivvit_Note", ""))
    price_note = str(r.get("Price note", ""))
    outdoor = str(r.get("Outdoor", ""))
    comb = f"{note} {team} {tiv} {price_note} {outdoor} {html_text}".lower()

    # 1. HTML BeautifulSoup icon tags (e-chalupy authoritative tags)
    if soup:
        has_dog_tag = soup.find(class_=re.compile(r"icon-withdog|withDog", re.I))
        if has_dog_tag:
            fee_m = re.search(r"((?:poplatek|příplatek|cena|pes|mazlíčk)[^\n.<>]{0,35}(?:poplatek|příplatek|\d+\s*kč|\d+,-))", comb, re.I)
            fee = fee_m.group(1).strip() if fee_m else ""
            return True, f"Allowed ({fee})" if (fee and len(fee) < 45) else "Pets Allowed (Dog Friendly)", 2.0
            
        has_no_animal = soup.find(class_=re.compile(r"icon-noanimal|noAnimal", re.I))
        if has_no_animal:
            return False, "Not Allowed (Zákaz mazlíčků)", 0.0

    # 2. Explicit Booking.com markers
    if re.search(r"pets\s+are\s+allowed", comb, re.I):
        fee_m = re.search(r"(?:charges\s+may\s+be\s+applicable|free\s+of\s+charge)", comb, re.I)
        fee = fee_m.group(0) if fee_m else "Booking confirmed"
        return True, f"Pets Allowed ({fee})", 2.0
    if re.search(r"pets\s+are\s+not\s+allowed", comb, re.I):
        return False, "Not Allowed (Booking confirmed)", 0.0

    # 3. Text patterns for pet allowance
    if re.search(r"(?:domácí\s+mazlíček\s+povolen|mazlíčci\s+vítáni|se\s+psem|pobyt\s+se\s+psem|psi\s+povoleni|pes\s+povolen|ubytování\s+se\s+psem)", comb, re.I):
        fee_m = re.search(r"((?:poplatek|příplatek|cena)[^\n.<>]{0,30}(?:pes|psa|mazlíčk)[^\n.<>]{0,30})", comb, re.I)
        fee = fee_m.group(1).strip() if fee_m else ""
        return True, f"Pets Allowed ({fee})" if (fee and len(fee) < 45) else "Pets Allowed (Dog Friendly)", 2.0

    if re.search(r"(?:zákaz\s+domácích\s+mazlíčků|bez\s+domácích\s+zvířat|zákaz\s+psů|zvířata\s+nejsou\s+povolena|zákaz\s+zvířat)", comb, re.I):
        return False, "Not Allowed (Zákaz mazlíčků)", 0.0

    return False, "Not Specified / Check with Host", 0.0


def determine_price_category(price_7n: Optional[float]) -> str:
    """Categorize price into standard retreat brackets: <50k, 50k-75k, 75k-100k, 100k-125k, 125k+."""
    if not price_7n or price_7n <= 0:
        return "On Request"
    elif price_7n < 50000:
        return "< 50k"
    elif price_7n < 75000:
        return "50k - 75k"
    elif price_7n < 100000:
        return "75k - 100k"
    elif price_7n < 125000:
        return "100k - 125k"
    else:
        return "125k+"


def evaluate_visual_freshness(r: Dict[str, Any], html_text: str, model_eval: Optional[Dict[str, Any]]) -> Tuple[float, str, str]:
    """
    Score how new, clean, and pleasant the property looks (0.0 to 10.0 scale).
    Rewards recently renovated, bright, stylish, scandi/modern interiors.
    Penalizes properties untouched for decades (~50yo communist era/hostel feel, dated panelling).
    """
    note = str(r.get("Note", ""))
    comm = str(r.get("Common area (what photos show)", ""))
    team = str(r.get("Team_Comment", ""))
    tiv = str(r.get("Tivvit_Note", ""))
    me_reasoning = str(model_eval.get("image_reasoning", "") if model_eval else "")
    
    corpus = f"{note} {comm} {team} {tiv} {me_reasoning} {html_text[:1500]}".lower()
    
    score = 6.0
    notes = []
    
    # Heavy penalties for dated / unrenovated / ~50yo feel
    if any(w in corpus for w in ["everything very old", "very old", "zastaral", "50 let", "50 years", "retro", "ugly", "just no", "looks bad", "komunist", "pension z devadesátých", "hostel feel", "school-trip"]):
        score -= 3.0
        notes.append("Interior reflects heavily dated aesthetic or unrenovated condition")
    if any(w in corpus for w in ["trojlavice", "benches only", "plain stacking", "office chairs", "worn furniture", "mismatched"]):
        score -= 1.0
        notes.append("Seating or furnishings show wear or lack ergonomic comfort")
    if any(w in corpus for w in ["school-trip", "hostel", "stará škola", "turistická"]):
        score -= 1.0
        notes.append("Hostel / youth-lodge ambiance")
        
    # High rewards for new / renovated / modern / clean
    if any(w in corpus for w in ["freshly renovated", "brand-new", "novostavba", "kompletní rekonstrukc", "zrekonstruov", "beautifully renovated", "scandi", "moderní", "luxury", "high-end", "luxusní"]):
        score += 3.0
        notes.append("Recently or comprehensively renovated")
    if any(w in corpus for w in ["bright", "clean", "spotless", "hotel-quality", "stylish", "tasteful", "fancy", "looks great", "looks very fancy"]):
        score += 1.5
        notes.append("Bright, clean, tasteful modern interior")
    if any(w in corpus for w in ["indoor heated pool", "panoramic sauna", "designer", "modern wellness"]):
        score += 0.5
        notes.append("High quality modern wellness features")
        
    score = max(1.0, min(10.0, score))
    
    if score >= 8.5:
        lbl = "Pristine / High-End Modern"
    elif score >= 7.0:
        lbl = "Fresh & Cleanly Maintained"
    elif score >= 5.0:
        lbl = "Standard Tourist Standard"
    elif score >= 3.5:
        lbl = "Visibly Dated / Aged"
    else:
        lbl = "Heavily Worn / Unrenovated (~50yo Feel)"
        
    return round(score, 1), lbl, "; ".join(notes) if notes else "Clean standard tourist condition"


def calculate_price_and_value(price_7n: Optional[float], cap: int, nice_to_haves_score: float) -> Tuple[float, int, str]:
    """
    Calculate price per person for 7 nights and value-for-money score.
    Applies penalty when price is high and nice-to-haves are missing.
    """
    if not price_7n or price_7n <= 0:
        return 0.0, 0, "Price on inquiry"

    price_pp = int(round(price_7n / max(1, cap)))

    # Base value score
    if price_7n <= 60000:
        val_score = 12.0
        val_rating = "Exceptional Value (≤60k Nový Svět benchmark)"
    elif price_7n <= 75000:
        val_score = 8.0
        val_rating = "Great Value"
    elif price_7n <= 90000:
        val_score = 4.0
        val_rating = "Fair Market Rate"
    elif price_7n <= 110000:
        val_score = 0.0
        val_rating = "Higher Price"
    else:
        # Penalty for price > 110k
        over = (price_7n - 110000) / 10000.0
        val_score = -min(12.0, over * 1.5)
        val_rating = "Expensive"

    # High price + missing amenities penalty:
    # "when it's a high price and some amenities are missing, it's kind of sad."
    if price_7n > 90000 and nice_to_haves_score < 20.0:
        penalty = -6.0
        val_score += penalty
        val_rating += " (⚠️ High price with low amenities penalty)"

    return round(val_score, 1), price_pp, val_rating


def evaluate_user_feedback(row: Dict[str, Any], web_feedback: Optional[Dict[str, Any]] = None) -> Tuple[float, float, float, List[str], str, str, str]:
    """
    Heavily scores user top votes and reviewer notes sentiment.
    Returns:
        total_user_feedback: float
        top_score: float
        sentiment_pts: float
        voters: list of voter labels
        sentiment_label: string
        tivvit_note: string
        team_comment: string
    """
    top_score = 0.0
    voters = []
    
    # 1. Top votes from sheet
    for user, col in [('Tivvit', 'tivvit top'), ('Fisa', 'fisa top'), ('Simon', 'simon top'), ('Eve', 'eve top')]:
        val = str(row.get(col, '')).strip()
        if not val:
            continue
        vl = val.lower()
        if 'asi best' in vl:
            pts = 10.0
            voters.append(f'{user}: Best (1.0)')
        elif '1' in vl:
            pts = 8.0
            voters.append(f'{user}: Top (1.0)')
        elif '0.75' in vl or '3/4' in vl:
            pts = 6.0
            voters.append(f'{user}: High (0.75)')
        elif '0.5' in vl or '1/2' in vl:
            pts = 4.0
            voters.append(f'{user}: Maybe (0.5)')
        else:
            pts = 5.0
            voters.append(f'{user}: {val}')
        top_score += pts
        
    top_score = min(top_score, 25.0)

    # 2. Web feedback live vote if any
    if web_feedback:
        w_vote = web_feedback.get("vote", "")
        if w_vote == "top":
            top_score += 5.0
            voters.append(f"{web_feedback.get('author', 'Team')}: Web Top (+5)")
        elif w_vote == "pass":
            top_score -= 8.0
            voters.append(f"{web_feedback.get('author', 'Team')}: Web Pass (-8)")

    # 3. Notes sentiment
    tn = str(row.get('tivvit note', '')).strip()
    tc = str(row.get('Team comment (old 8.0 sheet)', '')).strip()
    full_text = f'{tn} {tc}'.strip()
    
    sentiment_pts = 0.0
    sentiment_label = 'No Notes'
    
    if full_text:
        lower = full_text.lower()
        strong_neg_patterns = [
            r'\bjust no\b', r'\bterrible\b', r'\bugly\b', r'\bgarbage\b', r'\bai slop\b',
            r'nen[ií] kde sed[eě]t', r'\btrojlavice\b', r'\bsklepen[ií]\b',
            r'nen[ií] spole[cč]ensk[yý] prostor', r'w?orth max \d+', r'woth max \d+',
            r'expensive, looks bad', r'[sš]patn[eé] hodnocen[ií]', r'\bnee\b',
            r'very old'
        ]
        is_negated = bool(re.search(r'not\s+amazing|not\s+super|doesn[\'’]t\s+stand\s+out', lower))
        has_masterpiece = bool(re.search(r'\bmasterpiece\b|\btop\b|\bporno gau[cč]|\bvelmi zaj[ií]mav[eé]|\bsuper [cč]ill|\bsuper wel[nl]ess', lower))
        has_super_cena = bool(re.search(r'\bsuper cena\b', lower))
        has_amazing_pos = ('amazing' in lower) and not is_negated
        has_krasna = bool(re.search(r'kr[aá]sn[aá] chata|looks super nice|actually very good|actually amazing', lower))
        
        caveat_patterns = [
            r'm[aá]lo sezen[ií]|m[aá]lo [zž]idl[ií]|chyb[ií] [zž]idle|not enough chairs|jen \d+ [zž]idl[ií]',
            r'trochu chyb[ií]|nen[ií] v[uú]bec dostatek sezen[ií]',
            r'owner may be present|majitel may be present|host probably in the house',
            r'extremely overpriced|drah[eé]|expensive|drazsi na to co to je',
            r'not amazing|doesn[\'’]t stand out|not super impressive|not superb'
        ]
        
        mild_pos_patterns = [
            r'looks very good|very good|cozy|good price|looks good|looks decent',
            r'overall very nice|celkem p[eě]kn[eé]|beautiful|fist glance good|pou[zž]iteln[eé]'
        ]
        
        if any(re.search(p, lower) for p in strong_neg_patterns):
            sentiment_pts = -12.0
            sentiment_label = '⛔ Strongly Disliked by Team (-12 pts)'
        elif has_masterpiece or has_amazing_pos or has_krasna:
            sentiment_pts = +8.0
            sentiment_label = '🔥 High Praise in Team Notes (+8 pts)'
        elif has_super_cena:
            sentiment_pts = +6.0
            sentiment_label = '🔥 Praised for Great Price (+6 pts)'
        elif any(re.search(p, lower) for p in caveat_patterns):
            sentiment_pts = -4.0
            sentiment_label = '⚠️ Team Caveat / Warning (-4 pts)'
        elif any(re.search(p, lower) for p in mild_pos_patterns):
            sentiment_pts = +3.5
            sentiment_label = '💬 Positive Team Note (+3.5 pts)'
        else:
            sentiment_pts = 0.0
            sentiment_label = '📝 Team Note Available (0 pts)'
            
    total_user_feedback = round(top_score + sentiment_pts, 1)
    return total_user_feedback, round(top_score, 1), round(sentiment_pts, 1), voters, sentiment_label, tn, tc


def build_must_and_nice_evaluations():
    print("🚀 Running Must-Haves and Nice-To-Haves Extractor...")
    with open(RANKING_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    sp_data = {}
    if os.path.exists(STRUCTURED_JSON):
        with open(STRUCTURED_JSON, "r", encoding="utf-8") as f:
            sp_data = json.load(f)

    # Load web feedback if any
    web_comments = {}
    if os.path.exists("data/user_comments.json"):
        try:
            with open("data/user_comments.json", "r", encoding="utf-8") as f:
                web_comments = json.load(f)
        except Exception:
            web_comments = {}

    # Load model evaluations if any
    model_evals = {}
    for p in glob.glob("data/model_evaluations/*.json"):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                d = json.load(fh)
                model_evals[str(d.get("property_id"))] = d
        except Exception:
            pass

    # Load images manifest as gallery fallback
    images_manifest = {}
    if os.path.exists("images_manifest.json"):
        try:
            with open("images_manifest.json", "r", encoding="utf-8") as fh:
                images_manifest = json.load(fh)
        except Exception:
            images_manifest = {}

    # Load existing queue for September prices
    q_existing = {}
    if os.path.exists(QUEUE_JSON):
        with open(QUEUE_JSON, "r", encoding="utf-8") as f:
            for it in json.load(f):
                q_existing[it.get("Listing")] = it

    all_results = []

    for r in rows:
        name = r.get("Name", "").strip()
        listing = r.get("Listing", "").strip()
        veto_raw = (r.get("veto") or "").strip()
        
        m_oid = re.search(r"(\d+)", listing)
        oid = m_oid.group(1) if m_oid else None
        sp = sp_data.get(oid, {})

        soup, html_text, html_path = get_html_soup_and_text(listing)
        real_url = resolve_real_url(listing, oid, soup, html_path)
        q_item = q_existing.get(listing, {})
        p_info = resolve_photos(listing, r.get("Photo 1") or "", r.get("Photo 2") or "", r.get("Url") or "")

        # Fallback to manifest if local photos are missing or empty
        if not p_info.get("has_local_photos") or p_info.get("photos_count") == 0:
            manifest_photos = []
            if oid:
                for mk, mv in images_manifest.items():
                    if f"-o{oid}" in mk or f"_{oid}" in mk or mk.endswith(f"-{oid}"):
                        manifest_photos = mv
                        break
            elif listing.startswith("Booking"):
                bslug = listing.replace("Booking", "").strip()
                for mk, mv in images_manifest.items():
                    if bslug and bslug in mk:
                        manifest_photos = mv
                        break
            if manifest_photos:
                urls = [it["url"] for it in manifest_photos if it.get("url")]
                if urls:
                    p_info["has_local_photos"] = True
                    p_info["photos_folder"] = ""
                    p_info["photos_count"] = len(urls)
                    p_info["photos_list"] = urls
                    p_info["primary_photo"] = urls[0]

        # Price 7 nights
        p_7n = q_item.get("Price_7_Nights_CZK")
        if not p_7n:
            try:
                p_7n = float(r.get("Price / week (CZK)", 0))
            except Exception:
                p_7n = 0.0

        # Availability
        avail = extract_september_availability(oid, use_cache=True) if oid else {
            "has_7_consecutive_days": False, "max_consecutive_days": 0, "consecutive_ranges": []
        }

        # ------------------- MUST-HAVES -------------------
        # MH 1: No Veto
        mh_no_veto = (veto_raw == "")
        veto_reason = veto_raw if veto_raw else "None"

        # MH 2: September Week (>= 7 continuous days)
        mh_sept_week = avail.get("has_7_consecutive_days", False)
        sept_max_days = avail.get("max_consecutive_days", 0)
        sept_ranges = ", ".join(avail.get("consecutive_ranges", []))

        # MH 3: Capacity >= 24
        cap_spots, cap_eff, mh_capacity = extract_capacity(r, sp, html_text)

        # MH 4: >= 7 Rooms (or glamping/annex)
        rooms_cnt, has_annex, annex_details, mh_rooms = extract_rooms_and_annex(r, sp, html_text)

        # MH 5: Seating >= 16 (or secondary activity room)
        chairs_cnt, has_sec_room, sec_room_details, mh_seating = extract_seating_and_secondary_rooms(r, sp, html_text)

        all_must_haves_met = (mh_no_veto and mh_sept_week and mh_capacity and mh_rooms and mh_seating)

        failed_must_haves = []
        if not mh_no_veto:
            failed_must_haves.append(f"VETOED ({veto_reason})")
        if not mh_sept_week:
            failed_must_haves.append(f"Sept Free ({sept_max_days}d continuous < 7d)")
        if not mh_capacity:
            failed_must_haves.append(f"Capacity ({cap_spots} < 24 spots)")
        if not mh_rooms:
            failed_must_haves.append(f"Rooms ({rooms_cnt} < 7 rms & no annex)")
        if not mh_seating:
            failed_must_haves.append(f"Seating ({chairs_cnt} < 16 chairs & no 2nd room)")

        # ------------------- NICE-TO-HAVES -------------------
        # 1. TV & Projector
        total_screens, has_proj, tv_details, score_tv = extract_tv_and_projector(r, sp, html_text)

        # 2. Beer Tap
        beer_text = r.get("Common area (what photos show)", "") + " " + r.get("Kitchen", "") + " " + r.get("Note", "") + " " + html_text
        beer_info = extract_beer_tap_info(beer_text, listing_or_id=listing or oid)
        beer_count = beer_info["beer_tap_count"]
        beer_snippet = beer_info["beer_tap_snippet"]
        score_beer = 5.0 if beer_count >= 4 else (4.0 if beer_count >= 2 else (3.0 if beer_count == 1 else 0.0))

        # 3. Wellness (Sauna, Hot tub)
        well_count, has_sauna, has_hot_tub, well_details, score_well = extract_wellness(r, sp, html_text)

        # 4. Pool
        has_pool, pool_type, score_pool = extract_pool(r, sp, html_text)

        # 5. Outdoor Seating
        has_out_seat, out_seat_details, score_out_seat = extract_outdoor_seating(r, html_text)

        # 6. Indoor Sofa Seating
        has_sofa, sofa_details, score_sofa = extract_indoor_sofa(r, html_text)

        # 7. Toilets Count & Ratio
        toilets_cnt, toilets_per_rm, people_per_wc, score_toilets = extract_toilets(r, sp, rooms_cnt, cap_spots)

        # 8. Catering / Pro Kitchen
        has_catering, catering_details, score_catering = extract_catering(r, html_text)

        # 9 & 10. Children's Corner & Playground
        has_corner, corner_details, score_corner, has_play, play_details, score_play = extract_child_facilities(r, html_text)

        # 11. Pets Allowed (Scorer Benefit)
        has_pets, pets_details, score_pets = extract_pets_allowed(r, soup, html_text)

        nice_to_haves_total = round(
            score_tv + score_beer + score_well + score_pool + score_out_seat +
            score_sofa + score_toilets + score_catering + score_corner + score_play + score_pets, 1
        )

        # ------------------- PRICE & VALUE -------------------
        val_score, price_pp, val_rating = calculate_price_and_value(p_7n, cap_spots, nice_to_haves_total)

        # ------------------- TOTAL SCORING -------------------
        # Must-haves base: 40 points if all met, 0 if failed
        score_mh_base = 40.0 if all_must_haves_met else 0.0
        
        # Capacity bonus: 24 -> 5.0 pts, 30 -> 10.0 pts (linear)
        if cap_spots >= 24:
            cap_bonus = round(5.0 + ((min(30, cap_spots) - 24) / 6.0) * 5.0, 1)
        else:
            cap_bonus = 0.0

        # User feedback & reviewer notes
        u_feedback, u_top, u_sent, voters, s_lbl, tn, tc = evaluate_user_feedback(r, web_comments.get(listing))

        # Visual Condition / Freshness Score (0.0 to 10.0 scale)
        fresh_score, fresh_lbl, fresh_notes = evaluate_visual_freshness(r, html_text, model_evals.get(oid))
        price_cat = determine_price_category(p_7n)

        # Team veto check from comments
        if ("just no" in tc.lower() or "just no" in tn.lower()) and mh_no_veto:
            mh_no_veto = False
            veto_reason = "Team veto ('just no')"
            all_must_haves_met = False
            failed_must_haves.append(f"VETOED ({veto_reason})")
            score_mh_base = 0.0

        # Total score heavily factors in user top votes, reviewer notes, and visual freshness
        total_score_new = round(score_mh_base + nice_to_haves_total + cap_bonus + val_score + u_feedback + fresh_score, 1)

        # Synchronize Pros and Cons vs Nový Svět benchmark (4 draft beer taps)
        raw_pros = list(q_item.get("Pros_Vs_Novy_Svet", []))
        raw_cons = list(q_item.get("Cons_Vs_Novy_Svet", []))
        clean_pros = [p for p in raw_pros if not any(w in p.lower() for w in ["beer tap", "draft beer", "draft tap", "píp", "výčep", "tap(s)", "taps", "pet", "pets", "mazlíč", "dog", "pes"])]
        clean_cons = [c for c in raw_cons if not any(w in c.lower() for w in ["beer tap", "draft beer", "draft tap", "píp", "výčep", "tap(s)", "taps", "pet", "pets", "mazlíč", "dog", "pes"])]
        if beer_count >= 4:
            clean_pros.append(f"🍺 {beer_count} draft beer taps (matches/exceeds Nový Svět's 4 taps)")
        elif beer_count > 0:
            clean_cons.append(f"🍺 Only {beer_count} draft tap{'s' if beer_count > 1 else ''} (fewer than 4 taps at Nový Svět)")
        else:
            clean_cons.append("❌ No beer tap on site (Nový Svět has 4 draft taps)")

        if has_pets:
            clean_pros.append(f"🐶 Pets allowed ({pets_details}) — advantage over Nový Svět (forbids pets)")
        else:
            clean_cons.append("🚫 No pets allowed (same as Nový Svět)")

        eval_item = {
            "Rank_Old": r.get("Rank", ""),
            "Name": name,
            "Listing": listing,
            "Url": real_url,
            "Total_Score": total_score_new,
            "All_Must_Haves_Met": all_must_haves_met,
            "Must_Haves_Failed": failed_must_haves,
            "Must_Haves_Summary": "ALL PASS" if all_must_haves_met else f"FAILED: {', '.join(failed_must_haves)}",
            
            # Must-Haves Breakdown
            "MH_No_Veto": "PASS" if mh_no_veto else "FAIL",
            "Veto_Reason": veto_reason,
            
            "MH_Sept_Week": "PASS" if mh_sept_week else "FAIL",
            "Sept_Max_Continuous_Days": sept_max_days,
            "Sept_Free_Ranges": sept_ranges,
            
            "MH_Capacity_24Plus": "PASS" if mh_capacity else "FAIL",
            "Capacity_Total": cap_spots,
            "Capacity_Effective": cap_eff,
            
            "MH_Min_7_Rooms": "PASS" if mh_rooms else "FAIL",
            "Rooms_Count": rooms_cnt,
            "Has_Extra_Annex": has_annex,
            "Annex_Details": annex_details,
            
            "MH_Seating_16Plus": "PASS" if mh_seating else "FAIL",
            "Seating_Chairs_Count": chairs_cnt,
            "Has_Secondary_Room": has_sec_room,
            "Secondary_Room_Details": sec_room_details,
            
            # Nice-To-Haves (Observed Numbers & Scores)
            "NTH_TV_Projector_Count": total_screens,
            "NTH_Has_Projector": has_proj,
            "NTH_TV_Projector_Details": tv_details,
            "Score_TV": score_tv,
            
            "NTH_Beer_Tap_Count": beer_count,
            "NTH_Beer_Tap_Details": beer_snippet if beer_snippet else ("Yes" if beer_count > 0 else "None"),
            "Score_Beer_Tap": score_beer,
            
            "NTH_Wellness_Features_Count": well_count,
            "NTH_Has_Sauna": has_sauna,
            "NTH_Has_Hot_Tub": has_hot_tub,
            "NTH_Wellness_Details": well_details,
            "Score_Wellness": score_well,
            
            "NTH_Has_Pool": has_pool,
            "NTH_Pool_Type": pool_type,
            "Score_Pool": score_pool,
            
            "NTH_Has_Outdoor_Seating": has_out_seat,
            "NTH_Outdoor_Seating_Details": out_seat_details,
            "Score_Outdoor_Seating": score_out_seat,
            
            "NTH_Has_Indoor_Sofa": has_sofa,
            "NTH_Indoor_Sofa_Details": sofa_details,
            "Score_Indoor_Sofa": score_sofa,
            
            "NTH_Toilets_Count": toilets_cnt,
            "NTH_Toilets_Per_Room": toilets_per_rm,
            "NTH_People_Per_Toilet": people_per_wc,
            "Score_Toilets": score_toilets,
            
            "NTH_Has_Catering": has_catering,
            "NTH_Catering_Details": catering_details,
            "Score_Catering": score_catering,
            
            "NTH_Has_Child_Corner": has_corner,
            "NTH_Child_Corner_Details": corner_details,
            "Score_Child_Corner": score_corner,
            
            "NTH_Has_Child_Playground": has_play,
            "NTH_Child_Playground_Details": play_details,
            "Score_Child_Playground": score_play,
            
            "NTH_Pets_Allowed": has_pets,
            "NTH_Pets_Details": pets_details,
            "Score_Pets": score_pets,
            
            "Score_Nice_To_Haves_Total": nice_to_haves_total,
            
            # Pricing & Value
            "Price_7_Nights_CZK": p_7n,
            "Price_Per_Person_7N": price_pp,
            "Price_Category": price_cat,
            "Score_Value": val_score,
            "Value_Rating": val_rating,

            # Visual Freshness & Condition Score
            "Score_Visual_Freshness": fresh_score,
            "Visual_Freshness_Label": fresh_lbl,
            "Visual_Freshness_Notes": fresh_notes,

            # User Feedback & Endorsement Scores (Heavily weighted)
            "Score_User_Feedback_Total": u_feedback,
            "Score_User_Top_Votes": u_top,
            "Score_User_Notes_Sentiment": u_sent,
            "User_Top_Voters_Summary": ", ".join(voters) if voters else "None",
            "User_Top_Votes_Count": len(voters),
            "User_Notes_Sentiment_Label": s_lbl,
            
            # Score Subtotals
            "Score_Must_Haves_Base": score_mh_base,
            "Score_Capacity_Bonus": cap_bonus,
            
            # Metadata from previous extraction
            "Location": r.get("Location", ""),
            "Note": r.get("Note", ""),
            "Common_Area_Desc": r.get("Common area (what photos show)", ""),
            "Bedrooms_Bathrooms": r.get("Bedrooms & bathrooms", ""),
            "Has_Local_Photos": p_info["has_local_photos"] or q_item.get("Has_Local_Photos", False),
            "Photos_Folder": p_info["photos_folder"] or q_item.get("Photos_Folder", ""),
            "Photos_Count": p_info["photos_count"] or q_item.get("Photos_Count", 0),
            "Photos_List": p_info["photos_list"] or q_item.get("Photos_List", []),
            "Primary_Photo": p_info["primary_photo"] or q_item.get("Primary_Photo", ""),
            "Pros_Vs_Novy_Svet": clean_pros,
            "Cons_Vs_Novy_Svet": clean_cons,
            "September_Available": "YES" if mh_sept_week else "NO",
            "Beer_Tap_Available": "YES" if beer_count > 0 else "NO",
            "Beer_Tap_Count": beer_count,
            "Beer_Tap_Label": f"{beer_count} taps" if beer_count > 0 else "None",
            "Beer_Tap_Snippet": beer_snippet,
            "Chairs_Est": str(chairs_cnt) if chairs_cnt > 0 else r.get("Chairs in common area (est.)", ""),
            "Capacity": f"{cap_spots} beds",
            "Sauna": well_details if has_sauna else "None",
            "Pool": pool_type if has_pool else "None",
            "Kitchen": catering_details if has_catering else r.get("Kitchen", ""),
            "Outdoor": out_seat_details if has_out_seat else r.get("Outdoor", ""),
            "Tivvit_Top": r.get("tivvit top", ""),
            "Fisa_Top": r.get("fisa top", ""),
            "Simon_Top": r.get("simon top", ""),
            "Eve_Top": r.get("eve top", ""),
            "Tivvit_Note": tn,
            "Team_Comment": tc,
        }

        # Preserve Model_* evaluations if present
        for mk in q_item:
            if mk.startswith("Model_") and mk not in eval_item:
                eval_item[mk] = q_item[mk]

        all_results.append(eval_item)

    # Sort: Eligible first by Total_Score descending, then Disqualified by Total_Score descending
    all_results.sort(key=lambda x: (1 if x["All_Must_Haves_Met"] else 0, x["Total_Score"]), reverse=True)

    # Assign new Rank
    rank = 1
    for it in all_results:
        if it["All_Must_Haves_Met"]:
            it["Rank"] = rank
            rank += 1
        else:
            it["Rank"] = "Disqualified"

    # Export all results JSON
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_ALL_JSON, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"📁 Exported all {len(all_results)} evaluated accommodations to {OUTPUT_ALL_JSON}")

    # Export queue JSON (used by review website)
    with open(OUTPUT_QUEUE_JSON, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"📁 Exported active queue to {OUTPUT_QUEUE_JSON}")

    # Export detailed CSV with clear numbers for every must-have and nice-to-have
    fieldnames = [
        "Rank", "Name", "Listing", "Total_Score", "All_Must_Haves_Met", "Must_Haves_Summary",
        "Price_7_Nights_CZK", "Price_Per_Person_7N", "Price_Category", "Value_Rating", "Score_Value",
        "Score_Visual_Freshness", "Visual_Freshness_Label", "Visual_Freshness_Notes",
        # User Feedback & Endorsements
        "Score_User_Feedback_Total", "Score_User_Top_Votes", "Score_User_Notes_Sentiment",
        "User_Top_Votes_Count", "User_Top_Voters_Summary", "User_Notes_Sentiment_Label",
        "Tivvit_Top", "Fisa_Top", "Simon_Top", "Eve_Top", "Tivvit_Note", "Team_Comment",
        # Must Haves
        "MH_No_Veto", "Veto_Reason",
        "MH_Sept_Week", "Sept_Max_Continuous_Days", "Sept_Free_Ranges",
        "MH_Capacity_24Plus", "Capacity_Total", "Capacity_Effective",
        "MH_Min_7_Rooms", "Rooms_Count", "Has_Extra_Annex", "Annex_Details",
        "MH_Seating_16Plus", "Seating_Chairs_Count", "Has_Secondary_Room", "Secondary_Room_Details",
        # Nice to Haves
        "Score_Nice_To_Haves_Total",
        "NTH_TV_Projector_Count", "NTH_Has_Projector", "NTH_TV_Projector_Details", "Score_TV",
        "NTH_Beer_Tap_Count", "NTH_Beer_Tap_Details", "Score_Beer_Tap",
        "NTH_Wellness_Features_Count", "NTH_Has_Sauna", "NTH_Has_Hot_Tub", "NTH_Wellness_Details", "Score_Wellness",
        "NTH_Has_Pool", "NTH_Pool_Type", "Score_Pool",
        "NTH_Has_Outdoor_Seating", "NTH_Outdoor_Seating_Details", "Score_Outdoor_Seating",
        "NTH_Has_Indoor_Sofa", "NTH_Indoor_Sofa_Details", "Score_Indoor_Sofa",
        "NTH_Toilets_Count", "NTH_Toilets_Per_Room", "NTH_People_Per_Toilet", "Score_Toilets",
        "NTH_Has_Catering", "NTH_Catering_Details", "Score_Catering",
        "NTH_Has_Child_Corner", "NTH_Child_Corner_Details", "Score_Child_Corner",
        "NTH_Has_Child_Playground", "NTH_Child_Playground_Details", "Score_Child_Playground",
        # Score Components
        "Score_Must_Haves_Base", "Score_Capacity_Bonus",
        "Location", "Url", "Note"
    ]

    with open(OUTPUT_QUEUE_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for it in all_results:
            writer.writerow(it)
    print(f"📁 Exported comprehensive Must/Nice CSV to {OUTPUT_QUEUE_CSV}")

    # Update Excel Workbook with dedicated Must-Have & Nice-To-Have columns
    update_excel_workbook(all_results)


def update_excel_workbook(results: List[Dict[str, Any]]):
    src_xlsx = "sheet_latest.xlsx"
    dst_xlsx = OUTPUT_WORKBOOK
    if not os.path.exists(src_xlsx):
        return

    try:
        wb = openpyxl.load_workbook(src_xlsx)
        # Create a new sheet "Must & Nice Haves" or update ranking
        if "Must & Nice Haves" in wb.sheetnames:
            del wb["Must & Nice Haves"]
        ws = wb.create_sheet("Must & Nice Haves")

        headers = [
            "Rank", "Name", "Listing", "Total Score (New)", "Meets All Must-Haves?",
            "Must-Haves Summary", "September Price / 7N (CZK)", "Price / Person (7N)", "Value Rating",
            "User Feedback Total", "User Top Votes Score", "User Notes Sentiment Score",
            "User Top Voters", "User Notes Sentiment Label", "Tivvit Note", "Team Comment",
            "MH: No Veto", "MH: Sept Week Free", "Sept Max Continuous Days",
            "MH: Capacity >= 24", "Total Capacity", "MH: >= 7 Rooms (or Annex)", "Rooms Count", "Annex Details",
            "MH: Seating >= 16 (or 2nd Room)", "Seating Chairs Count", "Secondary Room Details",
            "Nice-To-Haves Score /38", "TV & Projector Count", "Beer Taps Count", "Wellness Features Count",
            "Pool Type", "Outdoor Seating", "Indoor Sofas", "Toilets Count", "Toilets / Room",
            "Catering / Pro Kitchen", "Child Corner", "Child Playground"
        ]
        ws.append(headers)

        for r in results:
            row_data = [
                r["Rank"], r["Name"], r["Listing"], r["Total_Score"], "YES" if r["All_Must_Haves_Met"] else "NO",
                r["Must_Haves_Summary"], r["Price_7_Nights_CZK"], r["Price_Per_Person_7N"], r["Value_Rating"],
                r.get("Score_User_Feedback_Total", 0), r.get("Score_User_Top_Votes", 0), r.get("Score_User_Notes_Sentiment", 0),
                r.get("User_Top_Voters_Summary", "None"), r.get("User_Notes_Sentiment_Label", "No Notes"),
                r.get("Tivvit_Note", ""), r.get("Team_Comment", ""),
                r["MH_No_Veto"], r["MH_Sept_Week"], r["Sept_Max_Continuous_Days"],
                r["MH_Capacity_24Plus"], r["Capacity_Total"], r["MH_Min_7_Rooms"], r["Rooms_Count"], r["Annex_Details"],
                r["MH_Seating_16Plus"], r["Seating_Chairs_Count"], r["Secondary_Room_Details"],
                r["Score_Nice_To_Haves_Total"], r["NTH_TV_Projector_Count"], r["NTH_Beer_Tap_Count"], r["NTH_Wellness_Features_Count"],
                r["NTH_Pool_Type"], "Yes" if r["NTH_Has_Outdoor_Seating"] else "No", "Yes" if r["NTH_Has_Indoor_Sofa"] else "No",
                r["NTH_Toilets_Count"], r["NTH_Toilets_Per_Room"], "Yes" if r["NTH_Has_Catering"] else "No",
                "Yes" if r["NTH_Has_Child_Corner"] else "No", "Yes" if r["NTH_Child_Playground_Details"] != "None" else "No"
            ]
            ws.append(row_data)

        wb.save(dst_xlsx)
        print(f"📁 Updated Excel Workbook with 'Must & Nice Haves' tab: {dst_xlsx}")
    except Exception as e:
        print(f"Excel export note: {e}")


if __name__ == "__main__":
    build_must_and_nice_evaluations()
