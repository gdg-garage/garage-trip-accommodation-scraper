#!/usr/bin/env python3
"""
September Availability Extractor for e-chalupy and Booking.com accommodations.
Fetches official live calendar data from obsazenost.e-chalupy.cz and evaluates
availability for a continuous 7-day retreat in September.
"""

import os
import re
import urllib.request
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup

CACHE_DIR = "data/calendar_cache"


def fetch_calendar_html(prop_id: str, use_cache: bool = True, timeout: int = 10) -> Optional[str]:
    """Fetch calendar widget HTML for an e-chalupy property ID with disk caching."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{prop_id}.html")

    if use_cache and os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        with open(cache_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    url = f"https://obsazenost.e-chalupy.cz/kalendar.php?id={prop_id}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(content)
            return content
    except Exception:
        return None


def extract_september_availability(prop_id: str, target_year: str = "2027", use_cache: bool = True) -> Dict[str, Any]:
    """
    Evaluates September availability for an accommodation, specifically checking
    whether a full 7-day continuous block (a full week) is available.
    """
    html = fetch_calendar_html(prop_id, use_cache=use_cache)
    if not html:
        return {
            "september_available": False,
            "september_status": "Calendar unavailable",
            "has_7_consecutive_days": False,
            "max_consecutive_days": 0,
            "consecutive_ranges": [],
            "free_days_count": 0,
            "occupied_days_count": 0,
            "summary": "Could not fetch calendar"
        }

    soup = BeautifulSoup(html, "html.parser")
    sept_table = None

    for table in soup.find_all("table", class_="month"):
        m_name = table.find(class_="month-name")
        if m_name and "září" in m_name.text.lower():
            if target_year in m_name.text:
                sept_table = table
                break
            elif not sept_table:
                sept_table = table

    if not sept_table:
        return {
            "september_available": False,
            "september_status": "Not published",
            "has_7_consecutive_days": False,
            "max_consecutive_days": 0,
            "consecutive_ranges": [],
            "free_days_count": 0,
            "occupied_days_count": 0,
            "summary": f"September {target_year} calendar not published yet"
        }

    day_status = {}  # day_number -> True if free/half, False if full
    for td in sept_table.find_all("td"):
        cls = td.get("class", [])
        title = td.get("title", "")
        text = td.text.strip()
        if "day-shdw" in cls or not text.isdigit():
            continue
        day_num = int(text)
        if "day-free" in cls or "Volno" in title or "day-half" in cls:
            day_status[day_num] = True
        else:
            day_status[day_num] = False

    free_days_count = sum(1 for v in day_status.values() if v)
    occupied_days_count = len(day_status) - free_days_count

    # Find continuous blocks of free days
    ranges = []
    cur_start = None
    cur_len = 0
    max_len = 0

    for day in range(1, 31):
        if day_status.get(day, False):
            if cur_start is None:
                cur_start = day
            cur_len += 1
            max_len = max(max_len, cur_len)
        else:
            if cur_start is not None and cur_len >= 7:
                ranges.append((cur_start, day - 1, cur_len))
            cur_start = None
            cur_len = 0

    if cur_start is not None and cur_len >= 7:
        ranges.append((cur_start, 30, cur_len))

    has_7_days = max_len >= 7
    range_labels = [f"{start}.–{end}. 9. ({length} days)" for start, end, length in ranges]

    if has_7_days:
        status = "7+ Days Available"
        summary = f"Available for 7-night week ({', '.join(range_labels)})"
    elif free_days_count > 0:
        status = "No 7-Day Window"
        summary = f"Cannot fit 7 days in a row (max {max_len} consecutive days free, {free_days_count}/30 total)"
    else:
        status = "Occupied"
        summary = "Fully booked in September"

    return {
        "september_available": has_7_days,
        "september_status": status,
        "has_7_consecutive_days": has_7_days,
        "max_consecutive_days": max_len,
        "consecutive_ranges": range_labels,
        "free_days_count": free_days_count,
        "occupied_days_count": occupied_days_count,
        "summary": summary
    }


if __name__ == "__main__":
    import sys
    pid = sys.argv[1] if len(sys.argv) > 1 else "3649"
    res = extract_september_availability(pid)
    print("Result:", res)
