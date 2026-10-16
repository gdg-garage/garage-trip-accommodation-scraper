#!/usr/bin/env python3
"""
Filter Booking.com candidate accommodations from saved MHTML search results.
Extracts all property cards, computes bed capacity, filters for 20 <= capacity <= 40,
and outputs candidate URLs and structured metadata.
"""

import email
import json
import csv
import os
import re
from typing import Dict, Any, List, Tuple
from bs4 import BeautifulSoup


def parse_capacity(card_text: str, title: str) -> Tuple[int, int, int, List[str], str]:
    """
    Parses capacity from card text and title.
    Returns: (total_beds, cap_min, cap_max, breakdown_list, reason)
    """
    # 1. Explicit mention in title (e.g. 'až pro 30 lidí', 'až 25 lůžek')
    m_title = re.search(r'(?:až\s+pro|pro|až)\s*(\d+)\s*(?:lidí|osob|lůžek|hostů)', title, re.I)
    if m_title:
        val = int(m_title.group(1))
        if 5 <= val <= 100:
            return val, val, val, [f"Title explicit: {val}"], "title_explicit"

    # 2. Detailed bed breakdown: e.g. '21 beds (14 singles, 2 sofa beds, 5 large doubles)'
    bed_breakdowns = re.findall(r'(\d+)\s+beds?\s*\(([^)]+)\)', card_text, re.I)
    if bed_breakdowns:
        total_beds = 0
        c_min = 0
        c_max = 0
        breakdowns = []
        for num_beds, details in bed_breakdowns:
            total_beds += int(num_beds)
            breakdowns.append(f"{num_beds} beds ({details})")
            singles = sum(int(x) for x in re.findall(r'(\d+)\s+singles?', details, re.I))
            doubles = sum(int(x) for x in re.findall(r'(\d+)\s*(?:extra-large\s+doubles?|large\s+doubles?|doubles?)', details, re.I))
            bunks = sum(int(x) for x in re.findall(r'(\d+)\s+bunk\s+beds?', details, re.I))
            sofas = sum(int(x) for x in re.findall(r'(\d+)\s+sofa\s+beds?', details, re.I))
            futons = sum(int(x) for x in re.findall(r'(\d+)\s+futons?', details, re.I))
            c_min += singles + doubles * 2 + bunks * 2 + sofas * 1 + futons * 1
            c_max += singles + doubles * 2 + bunks * 2 + sofas * 2 + futons * 1
        return total_beds, c_min, c_max, breakdowns, "bed_breakdown"

    # 3. Multiple room types (e.g. '5x Quadruple Room', '1x Family Room')
    multi_rooms = re.findall(r'(\d+)\s*[×x]\s*([^\n|]+)', card_text, re.I)
    if multi_rooms:
        c_sum = 0
        breakdowns = []
        for count, r_name in multi_rooms:
            cnt = int(count)
            r_lower = r_name.lower()
            breakdowns.append(f"{cnt}x {r_name.strip()}")
            if 'quadruple' in r_lower or 'four' in r_lower:
                c_sum += cnt * 4
            elif 'triple' in r_lower or 'three' in r_lower:
                c_sum += cnt * 3
            elif 'double' in r_lower or 'twin' in r_lower:
                c_sum += cnt * 2
            elif 'single' in r_lower:
                c_sum += cnt * 1
            elif 'family' in r_lower:
                c_sum += cnt * 4
            elif 'apartment' in r_lower:
                c_sum += cnt * 4
        if c_sum > 0:
            return c_sum, c_sum, c_sum, breakdowns, "multi_rooms"

    # 4. Simple 'X beds'
    simple_beds = re.findall(r'(\d+)\s+beds?', card_text, re.I)
    if simple_beds:
        b_sum = sum(int(x) for x in simple_beds)
        return b_sum, b_sum, int(b_sum * 1.5), [f"{b_sum} simple beds"], "simple_beds"

    return 0, 0, 0, [], "none"


def main():
    mhtml_file = "booking_cz_25plus_filtered.mhtml"
    if not os.path.exists(mhtml_file):
        print(f"Error: {mhtml_file} not found!")
        return

    print(f"Reading {mhtml_file}...")
    with open(mhtml_file, 'rb') as f:
        msg = email.message_from_binary_file(f)

    html_part = None
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            html_part = part.get_payload(decode=True)
            break

    if not html_part:
        print("Error: No HTML part found in MHTML!")
        return

    soup = BeautifulSoup(html_part, 'html.parser')
    cards = soup.find_all('div', attrs={'data-testid': 'property-card'})
    print(f"Total raw property cards in DOM: {len(cards)}")

    all_properties = []
    seen_urls = set()

    for idx, card in enumerate(cards):
        title_el = card.find(attrs={'data-testid': 'title'})
        name = title_el.get_text(strip=True) if title_el else f"Property_{idx+1}"

        link_el = card.find('a', attrs={'data-testid': 'title-link'}) or card.find('a', href=True)
        raw_url = link_el['href'] if link_el and link_el.has_attr('href') else ''
        clean_url = raw_url.split('?')[0] if raw_url else ''

        if not clean_url or clean_url in seen_urls:
            continue
        seen_urls.add(clean_url)

        slug = clean_url.rstrip('/').split('/')[-1]
        if slug.endswith('.html'):
            slug = slug[:-5]
        if slug.endswith('.en-gb') or slug.endswith('.cs'):
            slug = slug.rsplit('.', 1)[0]

        loc_el = card.find(attrs={'data-testid': 'address'})
        location = loc_el.get_text(strip=True) if loc_el else ''

        score_el = card.find(attrs={'data-testid': 'review-score'})
        score_text = score_el.get_text(' ', strip=True) if score_el else ''
        score_m = re.search(r'(\d+[.,]\d+)', score_text)
        review_score = float(score_m.group(1).replace(',', '.')) if score_m else None

        card_text = card.get_text(' \n ', strip=True)

        is_entire = bool(re.search(r'entire\s+(?:holiday\s+home|villa|chalet|house|cottage|property|place)', card_text, re.I))

        # Bedrooms
        bedrooms = [int(x) for x in re.findall(r'(\d+)\s*(?:bedrooms|bedroom)', card_text, re.I)]
        total_bedrooms = sum(bedrooms) if bedrooms else None

        total_beds, cap_min, cap_max, breakdowns, reason = parse_capacity(card_text, name)

        # Estimated capacity
        if cap_max > 0:
            est_cap = cap_max
        elif total_beds > 0:
            est_cap = total_beds
        else:
            est_cap = 0

        prop = {
            'id': f"b_{idx+1:03d}",
            'slug': slug,
            'name': name,
            'url': clean_url,
            'location': location,
            'review_score': review_score,
            'is_entire_place': is_entire,
            'bedrooms_count': total_bedrooms,
            'total_beds': total_beds,
            'cap_min': cap_min,
            'cap_max': cap_max,
            'estimated_capacity': est_cap,
            'capacity_reason': reason,
            'breakdowns': breakdowns,
        }
        all_properties.append(prop)

    # Save all parsed properties
    with open('booking_all_properties.json', 'w', encoding='utf-8') as f:
        json.dump(all_properties, f, indent=2, ensure_ascii=False)

    # Filter: 20 <= capacity <= 40
    under_20 = [p for p in all_properties if p['estimated_capacity'] < 20]
    over_40 = [p for p in all_properties if p['estimated_capacity'] > 40]
    suitable = [p for p in all_properties if 20 <= p['estimated_capacity'] <= 40]

    print("\n--- Filtering Summary ---")
    print(f"Total Unique Properties: {len(all_properties)}")
    print(f"Filtered Out (< 20 capacity): {len(under_20)}")
    print(f"Filtered Out (> 40 capacity): {len(over_40)}")
    print(f"Retained Suitable (20 <= capacity <= 40): {len(suitable)}")

    # Save suitable
    with open('booking_candidates_20_40.json', 'w', encoding='utf-8') as f:
        json.dump(suitable, f, indent=2, ensure_ascii=False)

    with open('booking_urls_20_40.txt', 'w', encoding='utf-8') as f:
        for p in suitable:
            f.write(p['url'] + '\n')

    # Save CSV
    with open('booking_candidates_20_40.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Slug', 'Name', 'Location', 'Review Score', 'Capacity Min', 'Capacity Max', 'Estimated Capacity', 'Bedrooms', 'Total Beds', 'Entire Place', 'URL'])
        for p in suitable:
            writer.writerow([
                p['id'], p['slug'], p['name'], p['location'], p['review_score'] or '',
                p['cap_min'], p['cap_max'], p['estimated_capacity'],
                p['bedrooms_count'] or '', p['total_beds'],
                'YES' if p['is_entire_place'] else 'NO',
                p['url']
            ])

    print("\nGenerated files:")
    print("  - booking_all_properties.json (All parsed properties)")
    print("  - booking_candidates_20_40.json (Retained candidate properties)")
    print("  - booking_candidates_20_40.csv (Tabular summary)")
    print(f"  - booking_urls_20_40.txt ({len(suitable)} URLs for detail page download)")


if __name__ == '__main__':
    main()
