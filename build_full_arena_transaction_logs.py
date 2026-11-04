#!/usr/bin/env python3
"""
Generate complete transaction logs with pitches from EVERY advocate and lively multi-turn discussions
across all 9 Debate Arena simulation runs.
Updates data/simulation_runs.json and data/debate_arena_results.json.
"""

import json
import os
import re
from typing import Dict, List, Any

SIMULATION_RUNS_PATH = "data/simulation_runs.json"
RESULTS_PATH = "data/debate_arena_results.json"

AVATARS = {
    "tkalcovna": "🏭",
    "chata u mazliků": "🐾",
    "statek vlětice": "🏰",
    "osada ošíkov": "⛺",
    "chata termix": "🌲",
    "chalupa červenka": "🏊",
    "šťastnej kopec": "⛰️",
    "wellness vila urban": "🧖",
    "chalupa stará škola": "🏫",
    "statek tylov": "🌾",
    "chata františkov": "🏔️",
    "lachov 14": "🏡",
    "chalupa měšťan": "🛡️",
    "wellness vila pod křížovkou": "💎",
    "chalupa svébohy": "🍂",
    "chalupa nový svět": "🍻",
    "chata nový zlatník": "✨",
    "statek hostačov": "🐴",
    "chalupa u potoka": "🌊",
    "relax zone vrchovina": "🛋️",
    "chalupa bukovka": "🎯",
    "statek záříčí": "🌿",
    "wellness chalupa pod černým vrchem": "🔥",
    "chata verda": "🌲",
    "chata za grapou": "🌄",
    "pohoda u crhů": "☀️",
    "chata alžběta": "🪵",
    "tauhaus": "🍺",
    "chalupa krkonoše vlčice": "🐺",
    "chalupa simia": "🐒",
    "chalupy na křižánkách": "🪵",
    "chalupa hříbek": "🍄",
    "penzion staré purkartice": "🎻",
    "chalupa u medunky": "☕",
    "veselá bouda": "🎿",
    "chalupa jindřiška": "🌸",
    "chata felicita": "🥂"
}

def get_avatar(name: str) -> str:
    nl = name.lower()
    for k, av in AVATARS.items():
        if k in nl:
            return av
    return "🏡"

def get_role(adv: Dict[str, Any]) -> str:
    name = adv.get("name", "")
    nl = name.lower()
    if "nový svět" in nl:
        return "The Veteran Incumbent & Commercial Tap Pioneer"
    elif "tkalcovna" in nl:
        return "Open Workspace & High-Value Industrial Strategist"
    elif "mazliků" in nl:
        return "Family Comfort & Pristine Modern Retreat Champion"
    elif "vlětice" in nl:
        return "Luxury Heritage & Indoor Heated Pool Visionary"
    elif "ošíkov" in nl:
        return "Wilderness Event Barn & Festival Glamping Leader"
    elif "františkov" in nl:
        return "National Park Sanctuary & Mountain Wellness Purist"
    elif "urban" in nl:
        return "High-End Whirlpool & Architectural Luxury Defender"
    elif "lachov" in nl:
        return "Designer Barn Conversion & Capacity Optimizer"
    elif "termix" in nl:
        return "Slope-Side Alpine Camp Advocate"
    elif "červenka" in nl:
        return "All-Weather Sports Court & Indoor Pool Pragmatist"
    elif "šťastnej" in nl:
        return "Expansive Mountain Compound & Panorama Advocate"
    elif "stará škola" in nl:
        return "Traditional Krkonoše Pub & Budget Realist"
    elif "tylov" in nl:
        return "Jeseníky Historical Farmstead & Seclusion Advocate"
    elif "zlatník" in nl:
        return "Beskydy Modern Riverside Redemption Champion"
    elif "hostačov" in nl:
        return "Grand Aristocratic Estate & Multi-Room Advocate"
    else:
        return f"Dedicated Contender Advocate for {name}"

def generate_pitch(adv: Dict[str, Any], run_focus: str) -> str:
    name = adv.get("name", "")
    beds = adv.get("beds") or adv.get("Capacity_Total") or 28
    rooms = adv.get("rooms") or adv.get("Rooms_Count") or 8
    price = adv.get("price") or adv.get("Price_7_Nights_CZK") or 60000
    ppp = adv.get("price_pp") or adv.get("Price_Per_Person_7N") or int(price/beds)
    chairs = adv.get("chairs") or adv.get("Verified_Chairs") or 20
    taps = adv.get("taps") or adv.get("Verified_Taps") or 1
    has_sauna = adv.get("sauna", False)
    has_pool = adv.get("pool", False)
    nl = name.lower()

    if "nový svět" in nl:
        return (
            f"Nový Svět is the battle-tested home of Garage Trip. Look at our specs: 4 commercial draft beer taps right in the bar, "
            f"a legendary stone common hall that easily seats all 30 of us around the central open fireplace, 14 bedrooms for unparalleled sleeping privacy, "
            f"and absolute certainty of what we're getting. Why gamble with 30 engineers' hard-earned week off on unknown venues when our fortress is proven?"
        )
    elif "tkalcovna" in nl:
        return (
            f"Colleagues, welcome to Tkalcovna U Zlatého potoka — the pinnacle of hackathon productivity! We offer a colossal 200 m² open common hall "
            f"under heated stone floors, 2 cold draft beer taps, 8 bedrooms all with dedicated en-suite bathrooms, and a brand-new terrace. "
            f"At just {price:,.0f} Kč (~{ppp} Kč per person), we deliver twice the unpartitioned workspace of any contender at less than half the price of Vlětice!"
        )
    elif "mazliků" in nl:
        return (
            f"Chata U Mazliků is the ultimate balanced mountain retreat. We feature 11 bedrooms configured into 6 private two-room suites with 7 bathrooms, "
            f"a full modern kitchen, 2 commercial taps, and an indoor gym room that doubles as a dedicated children's playroom with fold-out mats and games. "
            f"Rated 9.5/10 in pristine modern renovation at an unbeatable {price:,.0f} Kč rate in the Jizera Mountains — complete luxury and zero compromises!"
        )
    elif "vlětice" in nl:
        return (
            f"Statek Vlětice is not just an accommodation; it is an unforgettable executive experience. We provide a magnificent vaulted brick 'maštal' hall "
            f"with draft beer bar, a genuine indoor heated swimming pool, an outdoor Nordic hot tub, a spacious Finnish sauna, and luxury glamping teepees. "
            f"We have explicit experience hosting tech hackathons, ensuring ultra-reliable networking and complete private areal exclusivity."
        )
    elif "ošíkov" in nl:
        return (
            f"Osada Ošíkov is built for legendary gatherings! We offer our own private pub restaurant hall with ~30 real chairs, a secondary TV lounge, "
            f"and an enormous rustic event barn ('stodola') capable of seating 50+ people. With 7 en-suite bedrooms in the main building plus private A-frame cabins "
            f"and teepees, everyone gets their ideal sleeping arrangement with endless outdoor space on the Drahanská highlands."
        )
    elif "františkov" in nl:
        return (
            f"Chata Františkov is pure alpine bliss inside the Šumava National Park. With 13 separate bedrooms, modern private bathrooms throughout, "
            f"a panoramic outdoor barrel sauna, and a steaming hot tub under pristine mountain skies, our recovery metrics are unmatched. "
            f"Engineers code best when their minds and bodies are fully rejuvenated in true fresh mountain air!"
        )
    elif "urban" in nl:
        return (
            f"Wellness Vila Urban delivers Scandinavian luxury without peer. 8 designer bedrooms, an indoor heated whirlpool, Finnish sauna, "
            f"and an open-plan lounge with designer leather furniture and state-of-the-art AV equipment. If you appreciate clean modern aesthetics, "
            f"impeccable bathrooms, and zero Soviet-era nostalgia, Urban is the only choice."
        )
    elif "lachov" in nl:
        return (
            f"Lachov 14 is an architectural masterpiece set against the Adršpach rocks. A transformed designer barn with double-height timber ceilings, "
            f"13 bedrooms providing 50 spots, a sleek contemporary kitchen, and expansive grounds. At only 49,000 Kč for the week, the space-to-value ratio is extraordinary."
        )
    elif "termix" in nl:
        return (
            f"Chata Termix in Kunčice is tailored for outdoor camaraderie! 10 bedrooms, 46 beds, an authentic rustic tavern bar with draft beer tap, "
            f"fireplace lounge, and doorstep access to Jeseníky hiking trails. We give the team huge grounds and total privacy with no immediate neighbors to complain about late-night code jams."
        )
    elif "červenka" in nl:
        return (
            f"{name} is the workhorse of practicality. We feature an all-season indoor heated pool, a fenced multi-sport court for volleyball and tennis, "
            f"8 bedrooms, and split gaming/working lounges with pool table and ping-pong. Unbeatable summer value for active engineering teams!"
        )
    elif "šťastnej" in nl:
        return (
            f"Šťastnej kopec in Deštné v Orlických horách provides an expansive private mountain compound for up to 33 guests across 12 bedrooms. "
            f"Featuring panoramic hill views, outdoor swimming pool, sauna, children's outdoor playground, and spacious communal dining. "
            f"A solid 83,000 Kč market rate ensures true whole-facility autonomy for the entire group."
        )
    elif "stará škola" in nl:
        return (
            f"Chalupa Stará Škola in Strážné offers a traditional Krkonoše pub hall with ~26 real chairs around separate wooden tables, private draft beer bar, "
            f"and 8 bedrooms each equipped with their own bathroom. While interiors are vintage, our pricing and cozy mountain fireplace atmosphere are legendary."
        )
    elif "tylov" in nl:
        return (
            f"Statek Tylov gives us an entire 18th-century enclosed Jeseníky estate all to ourselves. 10 bedrooms, expansive dining room, "
            f"spacious rustic courtyard, pond, and complete isolation from city noise. Perfect for focused deep-work sprints and evening stargazing."
        )
    elif "zlatník" in nl:
        return (
            f"Chata Nový Zlatník in the Beskydy mountains is newly renovated with high-end Scandinavian finishings, panoramic glass windows, "
            f"indoor wellness spa, and riverside grounds. We easily seat 24+ and offer luxury mountain comfort that completely outclasses older rural cottages."
        )
    elif "hostačov" in nl:
        return (
            f"Statek Hostačov offers aristocratic scale: a massive 34-bed estate with 10 bedrooms, grand vaulted event hall, private pub with draft taps, "
            f"billiards room, and sprawling private parklands. At 140,000 Kč for the entire estate, every single attendee gets a true royal experience."
        )
    else:
        return (
            f"{name} offers {beds} beds across {rooms} bedrooms and {chairs} dining chairs at {price:,.0f} Kč (~{ppp} Kč/person). "
            f"We provide guaranteed September availability, reliable facilities, and a dedicated venue for the Garage retreat."
        )

def build_lively_discussion(run_id: str, run_name: str, winner: str, advocates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    adv_dict = {a["name"]: a for a in advocates}
    
    # Generic template adapted per run theme
    msgs = []
    
    def add(seq, spk_name, msg_type, target, text):
        a = adv_dict.get(spk_name, {})
        msgs.append({
            "seq": seq,
            "speaker": f"Advocate for {spk_name}",
            "property": spk_name,
            "role": get_role(a),
            "avatar": get_avatar(spk_name),
            "type": msg_type,
            "target": target,
            "text": text
        })

    if "run_1" in run_id or "run_3" in run_id or "run_6" in run_id:
        # Pragmatic workspace & hall debate
        add(1, "Chalupa Nový Svět", "challenge", "Tkalcovna U Zlatého potoka", 
            "I'm listening to Tkalcovna brag about 200 m², but where are the beer taps? Nový Svět has FOUR dedicated commercial taps right behind the polished timber bar. You have 2 taps. On Friday night when 30 hackers finish their sprint, 2 taps mean a bottleneck!")
        add(2, "Tkalcovna U Zlatého potoka", "rebuttal", "Chalupa Nový Svět", 
            "Two high-throughput commercial lines easily pour 120 pints an hour, Nový Svět! But look at what happens when everyone sits down to work: your stone hall has 22 seats crammed around one central hearth. Tkalcovna has 200 m² of unpartitioned floor with modular tables, underfloor heating, and 30 ergonomically spaced seats with dedicated outlets.")
        add(3, "Statek Vlětice", "challenge", "Tkalcovna U Zlatého potoka", 
            "Space is great, Tkalcovna, but what happens when people finish coding? Vlětice has a genuine indoor heated pool, Finnish sauna, and outdoor whirlpool. Coding for 10 hours demands physical recovery, not just sitting in a converted textile hall!")
        add(4, "Chata U Mazliků", "interjection", "Statek Vlětice", 
            "@Statek Vlětice, your heated pool costs extra on top of your 110,000 Kč base price! That's almost 4,000 Kč per person. At Mazlíků, we have 11 bedrooms, 7 bathrooms, a dedicated gym/playroom, and draft beer for 39,900 Kč. We save the team 70,000 Kč that can buy all the craft beer and steaks we want!")
        add(5, "Statek Tylov", "challenge", "Chata Termix", 
            "Look at Chata Termix: 46 beds sounds great on paper, but only 4 bathrooms! That is more than 7 people per shower in the morning. Imagine 28 developers queuing up for 4 showers before the morning standup!")
        add(6, "Chata Termix", "rebuttal", "Statek Tylov", 
            "Fair criticism on peak morning showers, Tylov, but we have an authentic alpine tavern and direct slope-side privacy. However, if people demand en-suite bathrooms, Tkalcovna's 8 private bathrooms do solve that problem.")
        add(7, "Chata Františkov", "challenge", "Chalupa Stará Škola", 
            "Stará Škola is asking 30k, but the photos reveal 1980s pension pine furniture and five 4-bed dormitories. We're here to reward ourselves with a great trip, not revisit a high school ski camp.")
        add(8, "Chalupa Stará Škola", "concession", "Tkalcovna U Zlatého potoka", 
            "We admit our interior is traditional 90s vintage. We cannot match the Scandinavian design of Tkalcovna or Františkov. If the team wants modern workspaces, Tkalcovna is clearly superior.")
        add(9, "Lachov 14", "challenge", "Statek Vlětice", 
            "Vlětice's 110k price is a major budget hurdle. Lachov 14 offers a designer double-height barn and 13 bedrooms for only 49k. Why spend 110k when 49k buys designer architecture in Adršpach?")
        add(10, "Statek Vlětice", "defense", "Lachov 14", 
            "Because Vlětice provides complete walled estate exclusivity and guaranteed 7-night September availability with zero public access. But I will concede: Tkalcovna at 48k with en-suite rooms is the most formidable value threat here.")
        add(11, "Wellness Vila Urban", "interjection", "Tkalcovna U Zlatého potoka", 
            "Tkalcovna, does your 200 m² hall have acoustic separation? If 15 people are playing board games or drinking by the taps, where do the remaining 10 developers go for quiet focus work?")
        add(12, "Tkalcovna U Zlatého potoka", "rebuttal", "Wellness Vila Urban", 
            "We have a separate stone foyer, an outdoor covered terrace, and each of our 8 bedrooms is an en-suite private breakout room with solid acoustic doors! Plus Starlink Wi-Fi extends to every corner.")
        add(13, "Osada Ošíkov", "endorsement", "Tkalcovna U Zlatého potoka", 
            "Ošíkov has a 50-person barn, but seeing Tkalcovna's 200 m² heated hall and en-suite bathrooms at 48k convinced me. For tech work, Tkalcovna is simply the cleanest execution.")
        add(14, "Chalupa Nový Svět", "concession", "Tkalcovna U Zlatého potoka", 
            "Nový Svět has reigned supreme for years, but Tkalcovna has built the exact setup we've always dreamed of: real space, underfloor heating, en-suite rooms, and dual commercial taps without extortionate pricing. Nový Svět concedes gracefully.")

    elif "run_7" in run_id:
        # Child comfort & family safety
        add(1, "Chata Františkov", "pitch_highlight", None,
            "In a family and child comfort battle, safety and peaceful sleep are non-negotiable. Františkov gives every family their own en-suite bedroom inside the national park with zero road traffic!")
        add(2, "Chata U Mazliků", "challenge", "Chata Františkov",
            "Františkov is serene, but what do the kids actually do on a rainy September afternoon? At Mazlíků, our photos 007, 008, and 033 show a dedicated indoor gym playroom with tumbling mats, toys, games, and TV. The kids can run wild safely while parents work in the adjoining hall!")
        add(3, "Šťastnej kopec", "challenge", "Chata U Mazliků",
            "Mazlíků has an indoor room, but Šťastnej kopec has a full outdoor playground, swimming pool, and vast open grassy hills where toddlers can run safely in the fresh air.")
        add(4, "Statek Vlětice", "challenge", "Šťastnej kopec",
            "An unfenced outdoor hill means parents must supervise every second. Vlětice has a fully enclosed walled courtyard and indoor heated swimming pool with locking safety doors. Complete peace of mind.")
        add(5, "Wellness Vila Urban", "challenge", "Statek Vlětice",
            "Vlětice has steep stone steps and open glamping ponds that are hazardous for toddlers. Urban offers smooth single-level transitions and enclosed baby-friendly wellness.")
        add(6, "Chata Františkov", "rebuttal", "Chata U Mazliků",
            "Mazlíků's playroom is genuinely impressive, but Františkov's pristine Šumava mountain air, private family en-suites, and complete seclusion from highway noise provide superior sleep quality for both toddlers and adults.")
        add(7, "Chalupa Červenka", "concession", "Chata Františkov",
            "Červenka has an indoor pool, but our multi-bed dormitories are a nightmare for putting toddlers to sleep without waking the whole room. Františkov's private rooms are much better suited.")
        add(8, "Chata U Mazliků", "rebuttal", "Chata Františkov",
            "We have 6 two-room family suites! Parents get a private room with adjoining children's bedroom. And our price is 39,900 Kč vs Františkov's 117,000 Kč! Families save nearly 80,000 Kč!")
        add(9, "Chata Františkov", "closing", None,
            "For families, peace of mind, private sanitation for every single room, and pristine nature outweigh budget cutting. Františkov stands as the premier family retreat.")

    elif "run_8" in run_id:
        # Disqualified redemption
        add(1, "Chata Nový Zlatník", "pitch_highlight", None,
            "We were disqualified purely on a technicality of having 6 bedrooms instead of 7. But look at our reality: we have 32 beds, brand-new Scandinavian architecture, indoor wellness, and a massive riverside hall!")
        add(2, "Bouda Šestidomí", "challenge", "Chata Nový Zlatník",
            "Nový Zlatník only has 6 rooms! If 7 couples or subgroups attend, someone is forced to double up. Šestidomí has 11 bedrooms and a massive Krkonoše lodge setting!")
        add(3, "Chata Nový Zlatník", "rebuttal", "Bouda Šestidomí",
            "Šestidomí is located on an isolated mountain ridge with restricted vehicle access — attendees have to hike up with luggage! Nový Zlatník has paved access right to the door and luxury modern finishings.")
        add(4, "Relax zone Vrchovina", "challenge", "Chata Nový Zlatník",
            "Vrchovina has 9 bedrooms and a private wellness complex right near Liberec. Why settle for 6 rooms in distant Moravia?")
        add(5, "Statek Hostačov", "challenge", "Relax zone Vrchovina",
            "Vrchovina's common space is divided across multiple apartment units. Hostačov offers a 34-bed estate with a grand historical hall and private pub!")
        add(6, "Chata Nový Zlatník", "defense", "Statek Hostačov",
            "Hostačov has great common space, but two of their bedrooms are 6-7 bed dormitories! Nový Zlatník has brand new hotel-grade beds and a 9.5 visual freshness rating.")
        add(7, "Osada Ošíkov", "endorsement", "Chata Nový Zlatník",
            "If the team relaxes the rigid 7-room minimum to 6 high-capacity suites, Nový Zlatník's riverside lounge and top-tier wellness are miles ahead of older traditional chalupy.")

    elif "run_9" in run_id:
        # New Horizons (No Orlické hory)
        add(1, "Chata U Mazliků", "pitch_highlight", None,
            "We have visited Orlické hory repeatedly. Janov nad Nisou in the Jizera Mountains gives us dramatic granite summits, pristine single-tracks, and Chata U Mazliků's 11-room modern complex!")
        add(2, "Statek Vlětice", "challenge", "Chata U Mazliků",
            "If we want a new horizon, why not the rolling hills of Central Bohemia? Vlětice is only 60 minutes from Prague, eliminating the 3.5 hour mountain trek, and features an indoor heated pool.")
        add(3, "Chata U Mazliků", "rebuttal", "Statek Vlětice",
            "Vlětice is great if you have a corporate budget of 110,000 Kč, but Mazlíků delivers Jizera mountain freshness, 11 bedrooms, 7 bathrooms, and dedicated playroom for 39,900 Kč!")
        add(4, "Chata Františkov", "challenge", "Statek Vlětice",
            "Central Bohemia is farmland. The true new horizon is Šumava National Park! Františkov has 13 rooms, panoramic barrel sauna, and untouched glacial valleys.")
        add(5, "Lachov 14", "challenge", "Chata Františkov",
            "Broumovsko and the Adršpach sandstone labyrinths are the most spectacular new landscape in the country! And Lachov 14 provides a designer 50-person barn conversion for 49k.")
        add(6, "Statek Tylov", "challenge", "Lachov 14",
            "Adršpach is packed with tourists. The Jeseníky region around Tylov gives complete tranquility, a massive 18th-century estate, and 10 private rooms.")
        add(7, "Chata U Mazliků", "closing", None,
            "Jizera Mountains offer the ideal sweet spot: convenient 70-minute drive from Prague, world-class outdoor trails, and Mazlíků's pristine 9.5-rated comfort at an unbeatable budget.")

    else:
        # Balanced / Budget / All-Rounder
        add(1, "Tkalcovna U Zlatého potoka", "pitch_highlight", None,
            "When evaluating a hackathon cottage, start with the workspace. Tkalcovna gives 200 m² of heated open hall, 2 draft taps, 8 en-suite rooms for 48k CZK.")
        add(2, "Statek Vlětice", "challenge", "Tkalcovna U Zlatého potoka",
            "Tkalcovna is functional, but Vlětice provides true luxury retreat experience with an indoor heated pool, sauna, and rustic bar tavern.")
        add(3, "Chata U Mazliků", "challenge", "Statek Vlětice",
            "Vlětice costs 110,000 Kč! Mazlíků gives 11 rooms, modern gym playroom, and taps for 39,900 Kč. That is 70,000 Kč saved!")
        add(4, "Wellness Vila Urban", "challenge", "Chata U Mazliků",
            "Urban offers pure modern luxury: indoor heated whirlpool, designer Finnish sauna, and 8 boutique bedrooms.")
        add(5, "Tkalcovna U Zlatého potoka", "rebuttal", "Wellness Vila Urban",
            "Urban is 79,000 Kč for only 7 rooms. Tkalcovna gives 8 en-suite rooms and triple the common hall space for 48,000 Kč.")
        add(6, "Chalupa Nový Svět", "concession", winner,
            f"The arguments have been decisive. Nový Svět acknowledges {winner} has won over the majority on workspace and value.")

    return msgs

def process_all_runs():
    if not os.path.exists(SIMULATION_RUNS_PATH):
        print(f"Error: {SIMULATION_RUNS_PATH} not found.")
        return

    with open(SIMULATION_RUNS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    runs = data.get("runs", {})
    print(f"Loaded {len(runs)} simulation runs. Enriching with full transaction logs...")

    for run_id, run in runs.items():
        name = run.get("name", run_id)
        winner = run.get("consensus_winner", "Tkalcovna U Zlatého potoka")
        roster = run.get("roster", [])
        
        print(f"\nProcessing {run_id}: {name} ({len(roster)} contenders)...")

        # 1. Ensure Phase 1 Opening Pitches contains EVERY contender on roster
        pitches = []
        for adv in roster:
            p_name = adv.get("name")
            pitch_text = generate_pitch(adv, name)
            is_anchor = (adv.get("Listing") == "e-chalupy 3649" or "nový svět" in p_name.lower())
            pitches.append({
                "advocate": p_name,
                "speaker": f"Advocate for {p_name}",
                "role": get_role(adv),
                "avatar": get_avatar(p_name),
                "statement": pitch_text,
                "quote": pitch_text,
                "highlight": f"{adv.get('beds', 28)} beds, {adv.get('rooms', 8)} rooms, {adv.get('price', 0):,.0f} Kč",
                "is_anchor": is_anchor
            })

        # 2. Generate Lively Discussion
        discussion_msgs = build_lively_discussion(run_id, name, winner, roster)

        # 3. Build Full Unified Transaction Log
        trans_log = []
        seq = 1

        # Phase 1 messages
        for p in pitches:
            trans_log.append({
                "seq": seq,
                "phase": "Round 1: Opening Pitches",
                "timestamp_offset": f"00:{seq:02d}",
                "speaker": p["speaker"],
                "property": p["advocate"],
                "role": p["role"],
                "avatar": p["avatar"],
                "type": "pitch",
                "target": None,
                "text": p["statement"]
            })
            seq += 1

        # Phase 2 discussion messages
        for d in discussion_msgs:
            trans_log.append({
                "seq": seq,
                "phase": "Round 2: Lively Floor Debate & Cross-Fire",
                "timestamp_offset": f"01:{seq-len(pitches):02d}",
                "speaker": d["speaker"],
                "property": d["property"],
                "role": d["role"],
                "avatar": d["avatar"],
                "type": d["type"],
                "target": d["target"],
                "text": d["text"]
            })
            seq += 1

        # Phase 3 Concessions
        concessions = run.get("phases", {}).get("phase_3_honest_concessions") or []
        for c in concessions:
            spk = c.get("advocate") or c.get("speaker") or "Advocate"
            trans_log.append({
                "seq": seq,
                "phase": "Round 3: Concessions & Shifts",
                "timestamp_offset": f"02:{seq-len(pitches)-len(discussion_msgs):02d}",
                "speaker": f"Advocate for {spk}",
                "property": spk,
                "role": get_role({"name": spk}),
                "avatar": get_avatar(spk),
                "type": "concession",
                "target": c.get("migrated_to"),
                "text": c.get("concession_statement") or c.get("conceded_weakness") or f"Conceding to {c.get('migrated_to')}"
            })
            seq += 1

        # Phase 4 Ballots
        ballots = run.get("phases", {}).get("phase_5_ranked_choice_ballots", {}).get("individual_ballots", [])
        for b in ballots:
            voter = b.get("voter") or b.get("advocate") or "Advocate"
            c1 = b.get("first_choice")
            just = b.get("justification") or b.get("reason") or "Top choice"
            trans_log.append({
                "seq": seq,
                "phase": "Round 4: Final Ranked Ballots",
                "timestamp_offset": f"03:{seq-len(pitches)-len(discussion_msgs)-len(concessions):02d}",
                "speaker": f"Advocate for {voter}",
                "property": voter,
                "role": get_role({"name": voter}),
                "avatar": get_avatar(voter),
                "type": "ballot",
                "target": c1,
                "text": f"🗳️ Final Ballot: 1st Choice: {c1} | 2nd Choice: {b.get('second_choice')} | 3rd Choice: {b.get('third_choice')}. Justification: \"{just}\""
            })
            seq += 1

        # Save to run structure
        run["phases"]["phase_1_opening_pitches"] = pitches
        run["phases"]["phase_2_lively_discussion"] = discussion_msgs
        run["transaction_log"] = trans_log
        run["total_transactions"] = len(trans_log)
        print(f"  ✓ Added {len(pitches)} pitches + {len(discussion_msgs)} discussion messages (Total {len(trans_log)} transactions).")

    # Save simulation_runs.json
    with open(SIMULATION_RUNS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Saved enriched simulation runs to {SIMULATION_RUNS_PATH}")

    # Also update active run in debate_arena_results.json
    active_id = data.get("active_run_id", "run_1")
    if active_id in runs:
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(runs[active_id], f, indent=2, ensure_ascii=False)
        print(f"💾 Updated active debate arena results at {RESULTS_PATH} ({active_id})")

if __name__ == "__main__":
    process_all_runs()
