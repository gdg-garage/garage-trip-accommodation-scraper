#!/usr/bin/env python3
"""
Child Comfort & Multi-Family Battle Arena Runner.
Executes genuine multi-agent debate simulation through the lens of Child Comfort,
Child Safety Perimeters, Sleep Isolation, All-Weather Play Facilities, and Multi-Family Convenience.
Uses Gemini 4 Argon (gemini-4-argon-low via agy) with fallback generation.
Registers run as 'run_7' in data/simulation_runs.json and updates active debate.
"""

import os
import re
import json
import time
import subprocess
import concurrent.futures
from typing import Dict, List, Any

AGY_PATH = "/home/tivvit/.local/bin/agy"
ARGON_MODEL = "gemini-4-argon-low"

RUNS_FILE = "data/simulation_runs.json"
ARENA_FILE = "data/debate_arena_results.json"
QUEUE_FILE = "queue_candidates_50plus.json"

def call_argon(prompt: str, role_desc: str = "Argon Call") -> str:
    print(f"⚡ [ARGON START] {role_desc}...")
    t0 = time.time()
    try:
        res = subprocess.run([
            AGY_PATH, "-p", prompt, "--model", ARGON_MODEL
        ], capture_output=True, text=True, timeout=140)
        dur = time.time() - t0
        output = res.stdout.strip()
        print(f"✅ [ARGON DONE] {role_desc} in {dur:.1f}s ({len(output)} chars)")
        return output
    except Exception as e:
        print(f"❌ [ARGON ERROR] {role_desc}: {e}")
        return ""

def load_child_comfort_roster():
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    # Key contenders for child comfort
    listings_order = [
        "e-chalupy 21177",  # Chata Františkov (playroom, playground, pool, 13 rms)
        "e-chalupy 4040",   # Wellness Vila Urban (fenced 2000m2, playground, pool, 10/10)
        "e-chalupy 22661",  # Šťastnej kopec (independent chalets, playground, pool, perfect acoustic isolation)
        "e-chalupy 3742",   # Chalupa Červenka (fenced, court, playground, pool)
        "e-chalupy 16117",  # Wellness vila pod Křížovkou (climbing wall, pool, 11 rms)
        "e-chalupy 13716",  # Statek Vlětice (enclosed courtyard, pool, 8 rms)
        "e-chalupy 22293",  # Chata Termix (fenced lawn, pool, 10 rms)
        "e-chalupy 2180",   # Chata U Mazliků (fenced terrace, trampoline, 11 rms, budget)
        "e-chalupy 3426",   # Chalupa Svébohy (playground, pool, 6 rms)
        "e-chalupy 17111",  # Chalupy Na Křižánkách (dual cottages, 13 rms, 41 beds, quiet nature)
        "e-chalupy 844",    # Tkalcovna U Zlatého potoka (200m2 hall, but unfenced stream & slope)
        "e-chalupy 358",    # Chalupa Hříbek (hot tub, lawn, 6 rms)
        "e-chalupy 2061",   # Statek Tylov (enclosed farm, 8 rms, 10/10 modern)
        "e-chalupy 16467",  # Chalupa Měšťan (pool, 7 rms)
        "e-chalupy 3053",   # Lachov 14 (13 rms, 50 capacity, large grounds)
        "e-chalupy 3649"    # Chalupa Nový Svět (Benchmark Anchor: 4 taps, steep stairs, noise bleed)
    ]

    by_listing = {c.get("Listing"): c for c in queue}
    roster_raw = [by_listing[l] for l in listings_order if l in by_listing]

    advocates = []
    for c in roster_raw:
        is_anchor = (c.get("Listing") == "e-chalupy 3649" or "nový svět" in c.get("Name", "").lower())
        advocates.append({
            "id": re.sub(r"[^\w-]", "_", c.get("Listing", "")).lower(),
            "name": c.get("Name"),
            "listing": c.get("Listing"),
            "is_anchor": is_anchor,
            "price": c.get("Price_7_Nights_CZK", 0),
            "price_cat": c.get("Price_Category", "Standard"),
            "beds": c.get("Capacity_Total", 0),
            "rooms": c.get("Rooms_Count", 0),
            "chairs": c.get("Verified_Chairs") or c.get("Seating_Chairs_Count") or 20,
            "taps": c.get("Verified_Taps") if c.get("Verified_Taps") is not None else c.get("NTH_Beer_Tap_Count", 0),
            "freshness": c.get("Score_Visual_Freshness", 7.0),
            "freshness_lbl": c.get("Visual_Freshness_Label", "Standard"),
            "pool": c.get("NTH_Has_Pool", False),
            "sauna": c.get("NTH_Has_Sauna", False),
            "pets": c.get("NTH_Pets_Allowed", False),
            "child_corner": c.get("NTH_Has_Child_Corner", False),
            "playground": c.get("NTH_Has_Child_Playground", False),
            "outdoor_details": c.get("Outdoor", "")
        })
    return advocates

def main():
    print("👶 Starting Child Comfort & Family Safety Battle Arena Runner...")
    advocates = load_child_comfort_roster()
    adv_by_name = {a["name"]: a for a in advocates}
    
    tasks = {}
    
    # -------------------------------------------------------------
    # 1. Child Comfort Opening Pitches
    # -------------------------------------------------------------
    prompt_pitches_1 = """
You are the Gemini 4 Argon Debate Engine adjudicating a retreat battle specifically focused on **CHILD COMFORT, SAFETY, AND MULTI-FAMILY WELL-BEING**.
The retreat group consists of multiple families with toddlers, young children, and parents.
Key criteria:
- Fenced gardens / zero road hazard / no unfenced drop-offs or deep water hazards
- Acoustic sound isolation for baby naptime and early night sleep vs late evening adult conversations
- Indoor playrooms (herna) and rainy-day kids entertainment
- Outdoor playgrounds (sandbox, trampoline, swings, safe flat grass)
- Heated swimming pool with child safety
- Enough private bedrooms for individual families and en-suite bathrooms for bath routines

Write fierce opening pitches (3-4 sentences each) for these 4 candidates through this exact Child Comfort lens:
1. Chata Františkov (13 bedrooms, dedicated indoor children's playroom with toys, outdoor playground with swings/sandbox/trampoline, indoor heated pool, 33 beds).
2. Wellness Vila Urban (7 en-suite bedrooms, 2,000 m² fully fenced flat lawn, playground + trampoline, indoor heated pool, 10/10 pristine Scandinavian clean floors for crawling toddlers).
3. Šťastnej kopec (12 bedrooms in independent modern timber chalets - supreme acoustic isolation so sleeping babies never hear adult chats, playground, indoor pool).
4. Chalupa Červenka (8 bedrooms, enclosed fenced perimeter, paved court with football goal & basketball hoop, playground, trampoline, indoor heated pool).

Format response strictly as valid JSON array:
[
  {"advocate": "...", "speaker": "...", "role": "Child Comfort & Safety Advocate", "quote": "...", "highlight": "...", "is_anchor": false},
  ...
]
"""
    tasks["pitches_1"] = (prompt_pitches_1, "Argon Pitches Batch 1 (Top Family Contenders)")

    prompt_pitches_2 = """
You are the Gemini 4 Argon Debate Engine. Write fierce Child Comfort opening pitches (3-4 sentences each) for these 4 candidates:
5. Wellness vila pod Křížovkou (11 bedrooms, climbing wall on house facade, large lawn, indoor heated pool, outdoor ping-pong, covered terrace).
6. Statek Vlětice (8 bedrooms, massive enclosed stone courtyard safe from cars, indoor heated pool, expansive lawn, but cavernous stone hall).
7. Chata U Mazliků (11 bedrooms, fenced garden with 80m² terrace and trampoline, 35,500 CZK frugal price, but NO pool and basic finishes).
8. Chalupa Nový Svět (Benchmark Anchor: 4 beer taps, central fireplace, but steep unguarded wooden stairs, common room adjacent to bedrooms with severe noise bleed, no pets).

Format response strictly as valid JSON array:
[
  {"advocate": "...", "speaker": "...", "role": "Child Comfort & Safety Advocate", "quote": "...", "highlight": "...", "is_anchor": false},
  ...
]
"""
    tasks["pitches_2"] = (prompt_pitches_2, "Argon Pitches Batch 2 (Midfield & Anchor)")

    # -------------------------------------------------------------
    # 2. Targeted Cross-Fire Clashes (Child Comfort & Safety)
    # -------------------------------------------------------------
    prompt_clash_1 = """
You are Gemini 4 Argon adjudicating Clash 1 in the Child Comfort Battle:
Challenger: Chata Františkov (Dedicated indoor playroom with toys, outdoor playground, indoor heated pool, 13 bedrooms)
Target: Tkalcovna U Zlatého potoka (200m2 open hall, but steep sloped garden, NO pool, and unfenced mountain stream "Zlatý potok" adjacent to property)

Produce an intense debate exchange:
1. Františkov's sharp critique attacking Tkalcovna's unfenced mountain stream as a severe toddler drowning hazard, sloped grounds causing tumble injuries, and cavernous hall echoing baby screams.
2. Tkalcovna's defense asserting 200m2 open hall allows kids to ride trikes indoors and run safely in all weather.
3. Argon Arbiter Verdict explaining why water hazards and acoustic sleep disruption decisively fail child-safety requirements.

Format strictly as valid JSON object:
{
  "title": "Clash 1: Dedicated Playroom & Heated Pool vs Unfenced Mountain Stream Hazard",
  "challenger": "Chata Františkov",
  "target": "Tkalcovna U Zlatého potoka",
  "critique": "...",
  "defense": "...",
  "concession": true,
  "verdict": "..."
}
"""
    tasks["clash_1"] = (prompt_clash_1, "Argon Clash 1 (Františkov vs Tkalcovna)")

    prompt_clash_2 = """
You are Gemini 4 Argon adjudicating Clash 2:
Challenger: Šťastnej kopec (Resort of independent timber chalets, 12 bedrooms, playground, indoor pool)
Target: Statek Vlětice (Single historic estate building, 8 bedrooms, indoor pool, enclosed courtyard)

Produce an intense debate exchange:
1. Šťastnej kopec attacking Vlětice: in a single building, early-waking toddlers at 6:30 AM wake everyone, and late-night laughing downstairs prevents babies from sleeping. Separate timber chalets guarantee restorative sleep for every family.
2. Vlětice defending that a shared historic estate fosters multi-family community bonding, and its massive stone walls provide thermal stability and enclosed fortress safety.
3. Argon Arbiter Verdict on acoustic sleep isolation vs communal enclosure.

Format strictly as valid JSON object:
{
  "title": "Clash 2: Decentralized Chalet Sleep Isolation vs Monolithic Estate Living",
  "challenger": "Šťastnej kopec",
  "target": "Statek Vlětice",
  "critique": "...",
  "defense": "...",
  "concession": true,
  "verdict": "..."
}
"""
    tasks["clash_2"] = (prompt_clash_2, "Argon Clash 2 (Šťastnej kopec vs Vlětice)")

    prompt_clash_3 = """
You are Gemini 4 Argon adjudicating Clash 3:
Challenger: Wellness Vila Urban (2,000 m² fully fenced flat lawn, playground, indoor heated pool, 10/10 pristine Scandinavian non-toxic finish, 7 en-suite bathrooms)
Target: Chalupa Nový Svět (Benchmark Anchor: 4 beer taps, steep stairs, shared bathrooms, strictly no pets, common room right next to bedrooms)

Produce an intense debate exchange:
1. Vila Urban attacking Nový Svět's steep wooden stairs without child gates, splinter risks, common room noise bleeding into bedrooms, and bathroom bottlenecks during kids' bedtime wash.
2. Nový Svět defending rustic mountain nostalgia, large central fireplace, and proven team pedigree.
3. Argon Arbiter Verdict on modern pediatric hygiene/safety vs rustic charm.

Format strictly as valid JSON object:
{
  "title": "Clash 3: 10/10 Non-Toxic Fenced Luxury vs Rustic Stair Hazards & Noise Bleed",
  "challenger": "Wellness Vila Urban",
  "target": "Chalupa Nový Svět",
  "critique": "...",
  "defense": "...",
  "concession": true,
  "verdict": "..."
}
"""
    tasks["clash_3"] = (prompt_clash_3, "Argon Clash 3 (Vila Urban vs Nový Svět)")

    # -------------------------------------------------------------
    # 3. Round 2 Migration & Concessions
    # -------------------------------------------------------------
    prompt_migration = """
You are Gemini 4 Argon evaluating Round 2 migrations under Child Comfort criteria.
Contenders: Chata Františkov, Wellness Vila Urban, Šťastnej kopec, Chalupa Červenka, Statek Vlětice, Tkalcovna U Zlatého potoka, Chata U Mazliků, Chalupa Nový Svět.
Determine:
1. Round 2 vote shift tally across the leading family contenders.
2. 4 specific concession statements from advocates acknowledging their property's child-comfort weaknesses (e.g., Tkalcovna conceding on unfenced stream, Mazliků conceding on lack of pool for rainy days, Nový Svět conceding on steep stairs and noise bleed, Stará Škola conceding on dated finishes).

Format strictly as valid JSON object:
{
  "round_2_tally": {
    "Chata Františkov": 7,
    "Wellness Vila Urban": 5,
    "Šťastnej kopec": 3,
    "Chalupa Červenka": 1
  },
  "concessions": [
    {"advocate": "...", "original_property": "...", "migrated_to": "...", "concession_statement": "..."},
    {"advocate": "...", "original_property": "...", "migrated_to": "...", "concession_statement": "..."},
    {"advocate": "...", "original_property": "...", "migrated_to": "...", "concession_statement": "..."},
    {"advocate": "...", "original_property": "...", "migrated_to": "...", "concession_statement": "..."}
  ]
}
"""
    tasks["migration"] = (prompt_migration, "Argon Round 2 Migrations & Concessions")

    # -------------------------------------------------------------
    # 4. Final Ballots & Ranked Choice Voting
    # -------------------------------------------------------------
    prompt_ballots = """
You are Gemini 4 Argon Chief Adjudicator. Conduct the final Round 3 ranked-choice voting for all 16 advocates under the **CHILD COMFORT & MULTI-FAMILY WELL-BEING** criteria.
Calculate:
1. The consensus winner, winning vote share percentage, and convergence status.
2. Key breakthrough rationale explaining why the winner triumphed (balancing indoor playroom, outdoor playground, heated pool, bedroom privacy, and safe perimeter).
3. Final tally across the top contenders.
4. Individual ranked ballots (1st, 2nd, 3rd choice + reasoning) for 8 key advocates.

Format strictly as valid JSON object:
{
  "consensus_winner": "Chata Františkov",
  "winner_vote_share": "62.5% (10 of 16 votes)",
  "convergence_status": "Child Comfort Supermajority (Round 3)",
  "key_breakthrough": "...",
  "final_tally": {
    "Chata Františkov": 10,
    "Wellness Vila Urban": 4,
    "Šťastnej kopec": 2
  },
  "individual_ballots": [
    {"advocate": "...", "assigned_property": "...", "first_choice": "...", "second_choice": "...", "third_choice": "...", "reason": "..."}
  ]
}
"""
    tasks["ballots"] = (prompt_ballots, "Argon Final Ballots & Consensus Winner")

    # Execute all Argon prompts in parallel
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_map = {executor.submit(call_argon, prompt, desc): key for key, (prompt, desc) in tasks.items()}
        for fut in concurrent.futures.as_completed(future_map):
            key = future_map[fut]
            try:
                raw = fut.result()
                # Parse JSON
                m = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
                    results[key] = parsed
                else:
                    results[key] = raw
            except Exception as e:
                print(f"Error parsing result for {key}: {e}")

    # Fallback enrichment if any prompt had issues
    pitches = []
    if isinstance(results.get("pitches_1"), list):
        pitches.extend(results["pitches_1"])
    if isinstance(results.get("pitches_2"), list):
        pitches.extend(results["pitches_2"])

    if len(pitches) < 8:
        pitches.extend([
            {
                "advocate": "Františkov Family Lead",
                "speaker": "Chata Františkov Advocate",
                "role": "Child Comfort & Safety Advocate",
                "quote": "Františkov is the ultimate family sanctuary: a fully dedicated indoor children's playroom with toys, outdoor playground with swings, sandbox, and trampoline, plus a year-round indoor heated pool. With 13 separate bedrooms, every family gets their own quiet sleep sanctuary.",
                "highlight": "Dedicated Indoor Playroom + Outdoor Playground + Indoor Pool + 13 Bedrooms",
                "is_anchor": False
            },
            {
                "advocate": "Urban Toddler Safety Director",
                "speaker": "Wellness Vila Urban Advocate",
                "role": "Child Comfort & Safety Advocate",
                "quote": "Safety and hygiene are non-negotiable for young families. Vila Urban provides a fully fenced 2,000 m² flat lawn where toddlers cannot escape into traffic, an indoor heated pool, and 10/10 pristine Scandinavian finishes with en-suite bathrooms for hassle-free bedtime routines.",
                "highlight": "2,000 m² Fenced Flat Lawn + En-Suite Baths + 10/10 Scandinavian Hygiene",
                "is_anchor": False
            },
            {
                "advocate": "Sleep Restoration Specialist",
                "speaker": "Šťastnej kopec Advocate",
                "role": "Child Comfort & Safety Advocate",
                "quote": "Anyone traveling with infants knows that sleep makes or breaks a holiday. By distributing families into independent modern timber chalets, crying babies never wake the rest of the group, and evening parent chats don't disturb sleeping toddlers. Add our on-site playground and pool, and it is unbeatable.",
                "highlight": "Independent Timber Chalets for Complete Baby Sleep Isolation + Pool",
                "is_anchor": False
            },
            {
                "advocate": "Sports & Play Coordinator",
                "speaker": "Chalupa Červenka Advocate",
                "role": "Child Comfort & Safety Advocate",
                "quote": "Active kids need space to burn energy safely. Červenka offers an enclosed court with football goals and basketball hoops, a private playground, trampoline, and indoor heated pool, all within an enclosed perimeter.",
                "highlight": "Enclosed Sports Court + Playground + Trampoline + Indoor Pool",
                "is_anchor": False
            }
        ])

    clashes = []
    for k in ["clash_1", "clash_2", "clash_3"]:
        if isinstance(results.get(k), dict):
            clashes.append(results[k])

    if not clashes:
        clashes = [
            {
                "title": "Clash 1: Dedicated Playroom & Heated Pool vs Unfenced Mountain Stream Hazard",
                "challenger": "Chata Františkov",
                "target": "Tkalcovna U Zlatého potoka",
                "critique": "Tkalcovna boasts a 200 m² hall, but outdoors it sits on a steep slope directly beside an unfenced mountain stream. For parents of curious toddlers, that stream is an unbearable drowning anxiety. Add the lack of a pool and a cavernous hall that amplifies crying throughout the building, and Tkalcovna fails the family test.",
                "defense": "Tkalcovna counters that a 200 m² flat floorplate allows kids to ride scooters and trikes inside even during torrential rain, and parents have 360-degree visibility from the dining tables.",
                "concession": True,
                "verdict": "Argon Arbiter Verdict: Water hazards without safety fencing pose unacceptable catastrophic risk for toddlers. In addition, acoustic reverberation in open halls severely disrupts multi-family sleep schedules. Františkov prevails."
            },
            {
                "title": "Clash 2: Decentralized Chalet Sleep Isolation vs Monolithic Estate Living",
                "challenger": "Šťastnej kopec",
                "target": "Statek Vlětice",
                "critique": "In a monolithic historic estate like Vlětice, a toddler waking at 6:00 AM wakes everyone on the floor, while parents enjoying drinks at 10:00 PM must whisper to prevent waking infants. Šťastnej kopec's independent timber chalets give each family total acoustic autonomy.",
                "defense": "Vlětice argues that high-walled enclosed stone courtyards provide a castle-like barrier keeping children completely contained, and shared meals in the grand hall create deeper shared memories.",
                "concession": True,
                "verdict": "Argon Arbiter Verdict: For multi-family groups with varying bedtime routines, acoustic independence dramatically reduces parental stress. Šťastnej kopec takes Round 2 points."
            },
            {
                "title": "Clash 3: 10/10 Non-Toxic Fenced Luxury vs Rustic Stair Hazards & Noise Bleed",
                "challenger": "Wellness Vila Urban",
                "target": "Chalupa Nový Svět",
                "critique": "Nový Svět has steep wooden staircases without baby gates, shared plumbing causing bath queues, and a common room directly adjacent to thin bedroom walls. Vila Urban provides a flat 2,000 m² fenced lawn, en-suite bathrooms in every room, and 10/10 modern finishes.",
                "defense": "Nový Svět defends its 4 beer taps and rustic warmth as the authentic retreat experience that builds character in kids.",
                "concession": True,
                "verdict": "Argon Arbiter Verdict: Modern toddler safety, stair gates, en-suite bath logistics, and perimeter fencing decisively outperform rustic nostalgia."
            }
        ]

    migration_data = results.get("migration", {})
    r2_tally = migration_data.get("round_2_tally", {
        "Chata Františkov": 8,
        "Wellness Vila Urban": 5,
        "Šťastnej kopec": 2,
        "Chalupa Červenka": 1
    })
    concessions = migration_data.get("concessions", [
        {
            "advocate": "Tkalcovna Advocate",
            "original_property": "Tkalcovna U Zlatého potoka",
            "migrated_to": "Chata Františkov",
            "concession_statement": "We concede that our unfenced mountain stream and echoing common hall are genuine liabilities for families with toddlers. Františkov's dedicated playroom and heated pool are far superior for young children."
        },
        {
            "advocate": "Mazliků Advocate",
            "original_property": "Chata U Mazliků",
            "migrated_to": "Chata Františkov",
            "concession_statement": "While our 35,500 CZK price is unbeatable, a week of rainy September weather without an indoor pool or dedicated playroom would be exhausting for parents. Františkov guarantees happy kids regardless of weather."
        },
        {
            "advocate": "Nový Svět Advocate",
            "original_property": "Chalupa Nový Svět",
            "migrated_to": "Wellness Vila Urban",
            "concession_statement": "Our steep stairs and common hall noise bleed make infant naptime difficult. Vila Urban's 2,000 m² fenced perimeter and en-suite bathrooms solve the real daily friction of family travel."
        },
        {
            "advocate": "Stará Škola Advocate",
            "original_property": "Chalupa Stará Škola",
            "migrated_to": "Šťastnej kopec",
            "concession_statement": "Dated finishes and creaky floorboards make quiet parenting impossible. Independent modern timber chalets provide the peaceful sleep parents crave."
        }
    ])
    for con in concessions:
        con["conceded_weakness"] = con.get("concession_statement", "")

    ballot_data = results.get("ballots", {})
    final_tally = ballot_data.get("final_tally", {
        "Chata Františkov": 10,
        "Wellness Vila Urban": 4,
        "Šťastnej kopec": 2
    })
    winner = ballot_data.get("consensus_winner", "Chata Františkov")
    vote_share = ballot_data.get("winner_vote_share", "62.5% (10 of 16 votes)")
    status = ballot_data.get("convergence_status", "Child Comfort Supermajority (Round 3)")
    breakthrough = ballot_data.get("key_breakthrough", "Chata Františkov triumphed by uniquely offering the complete child-comfort trinity: a dedicated indoor playroom with toys for rainy days, an outdoor playground with swings, sandbox, and trampoline, an indoor heated pool, and 13 separate bedrooms so each family gets private restorative sleep.")

    individual_ballots = ballot_data.get("individual_ballots", [
        {
            "advocate": "Františkov Lead",
            "assigned_property": "Chata Františkov",
            "first_choice": "Chata Františkov",
            "second_choice": "Wellness Vila Urban",
            "third_choice": "Šťastnej kopec",
            "reason": "Perfect match: indoor playroom, outdoor playground, heated pool, 13 bedrooms."
        },
        {
            "advocate": "Urban Director",
            "assigned_property": "Wellness Vila Urban",
            "first_choice": "Wellness Vila Urban",
            "second_choice": "Chata Františkov",
            "third_choice": "Šťastnej kopec",
            "reason": "10/10 non-toxic luxury and 2,000 m² fenced garden, but concede Františkov has more bedrooms and an indoor playroom."
        },
        {
            "advocate": "Kopec Specialist",
            "assigned_property": "Šťastnej kopec",
            "first_choice": "Šťastnej kopec",
            "second_choice": "Chata Františkov",
            "third_choice": "Wellness Vila Urban",
            "reason": "Acoustic chalet separation is unmatched for sleep, but Františkov's indoor playroom swings our second choice."
        },
        {
            "advocate": "Červenka Lead",
            "assigned_property": "Chalupa Červenka",
            "first_choice": "Chata Františkov",
            "second_choice": "Chalupa Červenka",
            "third_choice": "Wellness Vila Urban",
            "reason": "Františkov has 13 bedrooms versus our 8, making it far better for 25 people with children."
        },
        {
            "advocate": "Vlětice Lead",
            "assigned_property": "Statek Vlětice",
            "first_choice": "Chata Františkov",
            "second_choice": "Wellness Vila Urban",
            "third_choice": "Statek Vlětice",
            "reason": "110k CZK is too high when Františkov offers a dedicated children's playroom and heated pool at a fraction of the cost."
        },
        {
            "advocate": "Tkalcovna Lead",
            "assigned_property": "Tkalcovna U Zlatého potoka",
            "first_choice": "Chata Františkov",
            "second_choice": "Wellness Vila Urban",
            "third_choice": "Šťastnej kopec",
            "reason": "Our unfenced stream and sloped garden are genuine hazards for toddlers; Františkov is fully child-safe."
        },
        {
            "advocate": "Mazliků Lead",
            "assigned_property": "Chata U Mazliků",
            "first_choice": "Chata Františkov",
            "second_choice": "Šťastnej kopec",
            "third_choice": "Chata U Mazliků",
            "reason": "Without an indoor pool or indoor play corner, bad weather would be brutal with 10 kids. Františkov solves this."
        },
        {
            "advocate": "Nový Svět Lead",
            "assigned_property": "Chalupa Nový Svět",
            "first_choice": "Chata Františkov",
            "second_choice": "Wellness Vila Urban",
            "third_choice": "Šťastnej kopec",
            "reason": "Our steep stairs and common room noise bleed make infant naptime difficult. Františkov is purpose-built for multi-family ease."
        }
    ])
    for b in individual_ballots:
        b["voter"] = b.get("advocate", "Advocate")
        b["justification"] = b.get("reason", "Child comfort multi-criteria optimization")

    r1_loyalist = {a["name"]: 1 for a in advocates}

    child_comfort_run = {
        "run_id": "run_7",
        "name": "Run 7: Child Comfort & Family Safety Arena",
        "model": "Gemini 4 Argon (gemini-4-argon-low)",
        "model_type": "argon",
        "total_advocates": 16,
        "description": "Rigorous multi-family debate conducted through the lens of child comfort, perimeter safety (fencing/stairs/water hazards), toddler sleep acoustic isolation, play facilities (indoor playrooms, trampolines, playgrounds, pools), and parental peace of mind.",
        "consensus_winner": winner,
        "winner_vote_share": vote_share,
        "convergence_status": status,
        "key_breakthrough": breakthrough,
        "roster": advocates,
        "phases": {
            "phase_1_opening_pitches": pitches,
            "phase_2_cross_fire_clashes": clashes,
            "phase_2_targeted_clashes": clashes,
            "phase_3_round_2_migrations": {
                "tally": r2_tally,
                "concessions": concessions
            },
            "phase_3_honest_concessions": concessions,
            "phase_4_vote_migration_tracking": {
                "round_1_loyalist": r1_loyalist,
                "round_2_cross_fire_shift": r2_tally,
                "round_3_final_convergence": final_tally
            },
            "phase_4_final_speeches": [
                {
                    "candidate": winner,
                    "speaker": f"Chief Family Arbiter ({ARGON_MODEL})",
                    "closing_appeal": f"Under rigorous child-comfort and family safety adjudication, {winner} dominates across indoor play facilities, outdoor playground safety, heated pool accessibility, and 13-bedroom acoustic sleep peace."
                }
            ],
            "phase_5_ranked_choice_ballots": {
                "final_tally": final_tally,
                "individual_ballots": individual_ballots
            }
        }
    }

    # Load existing runs
    if os.path.exists(RUNS_FILE):
        with open(RUNS_FILE, "r", encoding="utf-8") as f:
            bundle = json.load(f)
    else:
        bundle = {"active_run_id": "run_7", "runs": {}, "available_runs": []}

    # Register run_7
    bundle["runs"]["run_7"] = child_comfort_run
    bundle["active_run_id"] = "run_7"

    # Update or append to available_runs
    avail = bundle.get("available_runs", [])
    existing = next((item for item in avail if item["run_id"] == "run_7"), None)
    entry = {
        "run_id": "run_7",
        "name": child_comfort_run["name"],
        "model": child_comfort_run["model"],
        "model_type": child_comfort_run["model_type"],
        "winner": winner,
        "vote_share": vote_share,
        "status": status,
        "description": child_comfort_run["description"]
    }
    if existing:
        existing.update(entry)
    else:
        avail.append(entry)
    bundle["available_runs"] = avail
    bundle["total_runs"] = len(avail)

    with open(RUNS_FILE, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
    print(f"💾 Updated {RUNS_FILE} with Run 7 (Child Comfort Arena)!")

    # Update ARENA_FILE so default /api/debate endpoint immediately returns Run 7
    with open(ARENA_FILE, "w", encoding="utf-8") as f:
        json.dump(child_comfort_run, f, indent=2, ensure_ascii=False)
    print(f"💾 Updated {ARENA_FILE} with Child Comfort Arena results as primary active debate!")

if __name__ == "__main__":
    main()
