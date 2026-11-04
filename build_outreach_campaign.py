#!/usr/bin/env python3
"""
build_outreach_campaign.py

Generates structured outreach candidates and personalized inquiry messages
for the top viable retreat options following user feedback on Mazlíků and Termix.
"""

import json
import csv
import re
from typing import Dict, Any, List

def generate_custom_czech_inquiry(item: Dict[str, Any]) -> str:
    name = item.get("Name", "Chalupa")
    listing = item.get("Listing", "")
    lid = re.search(r"\d+", listing).group(0) if re.search(r"\d+", listing) else ""
    beds = item.get("Capacity", "25-30 lůžek")
    bedrooms = item.get("Bedrooms_Bathrooms", "")
    
    # Custom highlights per property
    highlights = []
    if "844" in listing:
        highlights.append("Všimli jsme si, že máte Starlink Wi-Fi, společenskou místnost 200 m² s krbem a bar s výčepem (2 kohouty), což je pro nás ideální.")
    elif "2061" in listing:
        highlights.append("Velmi se nám líbí moderní rekonstrukce, finská sauna, koupací sud i prostorná společenská místnost s posezením pro celou skupinu.")
    elif "3053" in listing:
        highlights.append("Velkou výhodou jsou pro nás 2 oddělené velké společenské sály v Lachově (jeden pro denní co-working, druhý pro večerní deskové hry) a 13 ložnic.")
    elif "16467" in listing:
        highlights.append("Oceňujeme herní křídlo (biliár, stolní fotbálek, ping-pong), venkovní bazén a velkou společenskou místnost.")
    elif "13716" in listing:
        highlights.append("Zaujala nás možnost využití 2 zrekonstruovaných stodol, wellness s bazénem a saunou a skvělá dostupnost z Prahy.")
    elif "3426" in listing:
        highlights.append("Moc se nám líbí přírodní koupací biotop, finská sauna a příjemná zahrada s posezením v Novohradských horách.")
    elif "358" in listing:
        highlights.append("Zaujal nás vnitřní krb, barové zázemí s pípou, finská sauna a poloha na Benecku.")
    elif "2940" in listing:
        highlights.append("Velmi se nám líbí klenutý cihlový vinný sklep s vlastním výčepním zařízením, kulečníková místnost a 10 ložnic.")
    elif "13786" in listing:
        highlights.append("Líbí se nám zastřešené venkovní posezení s kuchyní a výčepem a dobré rozdělení 8 ložnic.")
    elif "3649" in listing:
        highlights.append("Již z minulých pobytů máme výbornou zkušenost s vaším objektem (4 výčepní kohouty, 4 chladničky, 13–14 pokojů).")
    else:
        highlights.append("Objekt nás zaujal svou kapacitou, počtem ložnic a prostorným společenským zázemím.")

    highlight_text = " ".join(highlights)

    msg = f"""Dobrý den,

obracím se na Vás s poptávkou pronájmu celého objektu {name} pro naši skupinu na týdenní pobyt v září (ideálně sobota–sobota nebo neděle–neděle v termínu září 2026 / 2027 dle Vaší aktuální volné kapacity).

Jsme skupina přátel a kolegů ze softwarového oboru (cca 22 až 26 dospělých osob, bez malých dětí a bez domácích mazlíčků). Hledáme klidné a komfortní zázemí pro náš každoroční týmový retreat. {highlight_text}

Během pobytu přes den potřebujeme možnost klidné práce na noteboocích a večer rádi hrajeme společenské deskové hry (např. Městečko Palermo). 

Rádi bychom se proto informovali o následujících detailech:
1. Máte volný týdenní termín v průběhu září pro celou naši skupinu (~22–26 osob)?
2. Jaká by byla celková kalkulace ceny za týdenní pronájem celého objektu (včetně spotřeby energií, rekreačních poplatků a závěrečného úklidu)?
3. Jaká je rychlost a stabilita Wi-Fi připojení v objektu pro současnou práci cca 20 notebooků?
4. Jaké jsou možnosti chlazení potravin v kuchyni (počet chladniček / objem)?
5. U výčepního zařízení – jaké narážecí hlavy (bajonet / žehlička / kombi) jsou k dispozici, případně je možnost zapůjčení / zajištění sudů přímo přes Vás?
6. Jaké jsou storno podmínky a výše požadované zálohy?

Předem Vám velice děkuji za Vaši odpověď a cenovou nabídku.

S pozdravem a přáním hezkého dne,
Jan Vlček (za GDG / softwarový tým)
Telefon: +420 777 ...
E-mail: ...
"""
    return msg.strip()

def main():
    with open("queue_candidates_50plus.json", "r", encoding="utf-8") as f:
        candidates = json.load(f)

    # Exclude Mazlíků (flagged old/strange) and Termix (unresponsive) from active outreach
    # Focus on top viable candidates
    outreach_targets = []
    excluded_targets = []

    priority_map = {
        "e-chalupy 844": (1, "Top Pick #1 (Orlické hory, Pub/Pool/Starlink, 48k CZK)"),
        "e-chalupy 2061": (2, "Top Pick #2 (Nízký Jeseník, 10/10 design, sauna/sud, 55k CZK)"),
        "e-chalupy 3053": (3, "Top Pick #3 (Broumovsko, 13 rooms, 2 huge halls for games/work, 49k CZK)"),
        "e-chalupy 16467": (4, "Top Pick #4 (Jeseníky, dedicated game room wing, pool, 73.8k CZK)"),
        "e-chalupy 13716": (5, "Contender #5 (Central Bohemia, 2 event barns, pool, sauna - check price neg.)"),
        "e-chalupy 3426": (6, "Contender #6 (Novohradské hory, biotope pond, sauna, 70k CZK)"),
        "e-chalupy 358": (7, "Contender #7 (Krkonoše Benecko, tap, fireplace, sauna, 69.9k CZK)"),
        "e-chalupy 2940": (8, "Contender #8 (South Moravia Rašov, wine cellar w/ tap, billiards, 70k CZK)"),
        "e-chalupy 13786": (9, "Contender #9 (Posázaví/Benešov, outdoor kitchen w/ tap, 60k CZK)"),
        "e-chalupy 11079": (10, "Contender #10 (Krkonoše Herlíkovice, tap, 35 beds, 97k CZK)"),
        "e-chalupy 5343": (11, "Contender #11 (Jizerské hory Strážné, tap, heated pool, 70k CZK)"),
        "e-chalupy 3649": (12, "Benchmark Option (Chalupa Nový Svět, 13-14 rooms, 4 taps, 4 fridges)")
    }

    for c in candidates:
        lid = c.get("Listing", "")
        if lid in ["e-chalupy 2180", "e-chalupy 22293"]:
            c_copy = dict(c)
            if "2180" in lid:
                c_copy["Outreach_Status"] = "ON_HOLD_AGED"
                c_copy["Outreach_Note"] = "User feedback: Layout quite strange and interior feels old. Paused in favor of fresher options."
            else:
                c_copy["Outreach_Status"] = "UNRESPONSIVE"
                c_copy["Outreach_Note"] = "Outreach sent previously: host did not reply; questionable bunk bed capacity."
            excluded_targets.append(c_copy)
            continue

        if lid in priority_map:
            prio, label = priority_map[lid]
            c_copy = dict(c)
            c_copy["Outreach_Priority"] = prio
            c_copy["Outreach_Tier"] = "Priority 1 - Immediate Outreach" if prio <= 4 else ("Priority 2 - Secondary Contenders" if prio <= 8 else "Priority 3 - Benchmark & Reserves")
            c_copy["Outreach_Label"] = label
            c_copy["Direct_Inquiry_Url"] = f"{c.get('Url', '')}#kontakt"
            c_copy["Czech_Inquiry_Message"] = generate_custom_czech_inquiry(c)
            outreach_targets.append(c_copy)

    # Sort by priority
    outreach_targets.sort(key=lambda x: x.get("Outreach_Priority", 999))

    campaign_data = {
        "generated_at": "2026-11-04",
        "description": "Retreat Accommodation Outreach Campaign for Top Contenders",
        "active_outreach_candidates": outreach_targets,
        "paused_or_unresponsive_candidates": excluded_targets
    }

    # Save to data/outreach_campaign_top_candidates.json
    out_json = "data/outreach_campaign_top_candidates.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(campaign_data, f, ensure_ascii=False, indent=2)
    print(f"✅ Exported {len(outreach_targets)} active outreach targets to {out_json}")

    # Save to CSV
    out_csv = "data/outreach_campaign_top_candidates.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Priority", "Tier", "Name", "Listing", "Total_Score", "Price_Est",
            "Rooms_Beds", "Location", "Draft_Taps", "Direct_Url", "Inquiry_Url", "Outreach_Label"
        ])
        for t in outreach_targets:
            writer.writerow([
                t.get("Outreach_Priority"),
                t.get("Outreach_Tier"),
                t.get("Name"),
                t.get("Listing"),
                t.get("Total_Score"),
                t.get("Price_7n_Normalized") or t.get("Price"),
                f"{t.get('Capacity')} | {t.get('Bedrooms_Bathrooms')}",
                t.get("Location"),
                t.get("Beer_Tap_Label"),
                t.get("Url"),
                t.get("Direct_Inquiry_Url"),
                t.get("Outreach_Label")
            ])
    print(f"✅ Exported outreach CSV to {out_csv}")

if __name__ == "__main__":
    main()
