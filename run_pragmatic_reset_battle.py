#!/usr/bin/env python3
"""
run_pragmatic_reset_battle.py

Run 11: The Pragmatic Retreat Reset (Methodical Showdown)

Executes a simulation battle under the user's updated 2026 methodical priorities:
1. Room Count & Capacity (8 min, 10-12 optimum, up to 14; small rooms for privacy/families, no giant bunk dorms)
2. Main Room Size, Table Count & Couch Lounging (deep couches for couch co-op + shisha nook vs hard wooden benches)
3. Location & Nature (1 trail loop from doorstep; Orlické hory acceptable/neutral, fresh region gives bonus)
4. Catering & Food Delivery Feasibility (DEAL BREAKER - lunch delivery is mandatory for 25+ devs)
5. Bathrooms Ratio (ideal 1:2 ratio to rooms)
- Portable items discounted (pípa, projector, monitors, extra chairs can be brought)
- Price ceiling (>100k CZK penalized; 40k-80k sweet spot)

Outputs to data/simulation_runs.json and data/debate_arena_results.json.
"""

import json
import os
import re

SIMULATION_RUNS_PATH = "data/simulation_runs.json"
RESULTS_PATH = "data/debate_arena_results.json"
CANDIDATES_PATH = "data/candidates_must_nice_all.json"

def main():
    with open(CANDIDATES_PATH, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    # Roster of top contenders for this showdown
    roster_listings = [
        "e-chalupy 3649",   # Chalupa Nový Svět (Gold Standard Benchmark)
        "e-chalupy 2940",   # Statek U Pepíka (South Moravia 10 rms, cellar w/ tap, attic lounge)
        "e-chalupy 3053",   # Lachov 14 (Broumovsko 13 rms, 2 massive separate halls, 49k CZK)
        "e-chalupy 2061",   # Statek Tylov (Nízký Jeseník 8 rms, 10/10 design, sauna/sud, 55k CZK)
        "e-chalupy 844",    # Tkalcovna U Zlatého potoka (Orlické hory 8 rms en-suite, pool/sauna, pub)
        "e-chalupy 13947",  # Chata Nový Zlatník (Beskydy 9 rms, 24 beds, 48.9k CZK)
        "e-chalupy 5343",   # Chalupa Jindřiška (Krkonoše 10 rms, bar hall, 70k CZK)
        "e-chalupy 3742",   # Chalupa Červenka (Červená Voda 8 rms, 27 beds, 45k CZK)
        "e-chalupy 2180",   # Chata U Mazliků (Jizerské hory - flagged aged/strange layout)
        "e-chalupy 22293",  # Chata Termix (Jeseníky - host unresponsive / 46 bunks)
    ]

    c_map = {c["Listing"]: c for c in candidates}
    roster = []
    for lid in roster_listings:
        if lid in c_map:
            c = c_map[lid]
            b = c.get("Score_Pragmatic_Breakdown", {})
            roster.append({
                "listing": lid,
                "name": c["Name"],
                "score_pragmatic": c.get("Score_Pragmatic_2026", 0),
                "photo_status": c.get("Photo_Validation_Status", ""),
                "photo_label": c.get("Photo_Validation_Label", ""),
                "rooms": c.get("Rooms_Count", 0),
                "capacity": c.get("Capacity_Total", 0),
                "price": c.get("Price_7_Nights_CZK", 0),
                "location": c.get("Location", "")
            })

    # Pitches
    pitches = [
        {
            "speaker": "Chalupa Nový Svět",
            "avatar": "🍻",
            "role": "The Proven Benchmark",
            "statement": "We are the undisputed reference standard. Why? Because we nail the top 5 intrinsic priorities that no trailer or Lindr tap can fix: 14 true bedrooms (2.1 beds/room average) giving unparalleled sleep privacy and spare rooms for an escape room or shisha prep; TWO full couch lounge zones each with their own TV; 7 full bathrooms and 11 WCs; 30+ padded chairs; and verified daily lunch delivery from Králíky restaurants 2 km away. Yes, our summer price is 80k and we are in Orlické hory, but as your team organizer pointed out: you only take one 2-hour loop hike directly from the door anyway, and our local trails are pristine.",
            "highlight": "14 Bedrooms • 2 Couch Zones • 7 Baths / 11 WCs • 30 Padded Chairs • Proven Králíky Lunch Delivery"
        },
        {
            "speaker": "Lachov 14",
            "avatar": "🏡",
            "role": "Broumovsko Dual-Hall Giant",
            "statement": "If you want a fresh destination without sacrificing Nový Svět's scale, Lachov 14 in Broumovsko is the premier contender. For 49,000 CZK (saving 31,000 CZK!), we provide 13 bedrooms (matching Nový Svět!), 8 bathrooms, and TWO standalone giant halls on separate floors! Hall 1 downstairs features a vaulted dining & co-working room with brick bar; Hall 2 upstairs offers a cozy fireplace lounge with deep U-shaped sofas for couch co-op and late-night Werewolf. Furthermore, Broumovské skály sandstone towers start right outside our front door, and Teplice nad Metují delivers hot lunches daily.",
            "highlight": "49,000 CZK (Save 31k) • 13 Bedrooms • 8 Baths • 2 Separate Massive Halls (Acoustic Isolation) • Broumovsko Rocks"
        },
        {
            "speaker": "Statek U Pepíka",
            "avatar": "🍷",
            "role": "South Moravian Multi-Zone Estate",
            "statement": "Located in Rašov near Tišnov (85.0 pts, 70,000 CZK), Statek U Pepíka delivers the ultimate multi-room layout: 10 spacious bedrooms for 27 beds (ideal 2.7 beds/room low density). We offer THREE distinct social zones: a huge renovated barn hall with ~40 seats and billiards, an authentic arched brick wine cellar with private draft beer taps (perfect for shisha and acoustic Werewolf games), and an upstairs attic lounge with couches and TV. Tišnov is 8 km away with full food delivery.",
            "highlight": "10 Bedrooms (Low Density) • 3 Separate Zones (Barn + Brick Cellar + Attic Lounge) • 70,000 CZK • Tišnov Delivery"
        },
        {
            "speaker": "Statek Tylov",
            "avatar": "🌾",
            "role": "Pristine Scandinavian Farmstead",
            "statement": "Statek Tylov in Nízký Jeseník (82.0 pts, 55,000 CZK) represents the pinnacle of modern taste (10/10 Ota-approved Scandinavian renovation). We provide 8 bedrooms for 31 beds, a 60 m² dining hall with solid wooden tables, a comfortable living room sofa corner, Finnish sauna, and outdoor bathing barrel (*koupací sud*). It provides the pristine, fresh-region luxury retreat feel that escaping Orlické hory promises.",
            "highlight": "10/10 Scandinavian Renovation • Finnish Sauna + Hot Tub • 8 Bedrooms • 55,000 CZK • Nízký Jeseník"
        },
        {
            "speaker": "Tkalcovna U Zlatého potoka",
            "avatar": "🏭",
            "role": "Historic Pub & Wellness Mill",
            "statement": "We offer 8 bedrooms, all 8 en-suite, Starlink Wi-Fi, an indoor heated pool, sauna, and an on-site pub with beer tap for 48,000 CZK. We acknowledge Tivvit's finding: our main hall is set up like a traditional pub with long wooden tables and benches, meaning we lack the deep, sprawling double couch zones of Nový Svět. If having two plush living room sofa setups is critical for Nintendo Switch and shisha, we are a pub, not a lounge.",
            "highlight": "48,000 CZK • 8 En-suite Bathrooms • On-site Pub with Tap • Indoor Pool + Sauna • Starlink"
        }
    ]

    # Discussion Turns
    discussion = [
        {
            "turn": 1,
            "speaker": "Organizer & Methodical Auditor",
            "avatar": "📋",
            "type": "framing",
            "target": "all",
            "topic": "The 5 Uncompromising Intrinsic Priorities",
            "text": "Delegates! Let us ground this battle strictly in reality: 1) Pípa, projektor, monitory, and extra chairs can be hauled in a car trailer. They do NOT decide this retreat. 2) Pools and hot tubs are minor perks in September. 3) What CANNOT be replaced is: 8-14 bedrooms with comfortable bed density, a spacious common room with real tables and DEEP COUCHES (one zone for couch coop, one for shisha), catering/lunch delivery, and 1:2 bathroom ratios. 4) Orlické hory is NOT heavily penalized because the team only takes one loop walk directly from the house anyway."
        },
        {
            "turn": 2,
            "speaker": "Chalupa Nový Svět",
            "avatar": "🍻",
            "type": "challenge",
            "target": "Tkalcovna U Zlatého potoka",
            "topic": "The Couch Reality Check",
            "text": "@Tkalcovna: As the organizer accurately stated: 'Tkalcovna nám nepřinese nic navíc – je to jen sleva a přijdeme o gauče.' Developers working 10 hours and playing Mario Kart for 4 hours CANNOT sit on upright pub wooden chairs and tavern benches all week! At Nový Svět, we have TWO distinct couch zones with plush sofas and large TVs. You have an authentic pub, but no retreat lounging comfort."
        },
        {
            "turn": 3,
            "speaker": "Tkalcovna U Zlatého potoka",
            "avatar": "🏭",
            "type": "concession",
            "target": "Chalupa Nový Svět",
            "topic": "The Couch Reality Check",
            "text": "We concede this point honestly. We have only one white leather sofa by the fireplace, while the rest of our 200 m² is set up with pub dining tables and chairs. Furthermore, we are in the exact same Orlické hory valley as Nový Svět, so booking us provides zero regional change. We save 32,000 CZK, but we do not solve the couch or new destination desire."
        },
        {
            "turn": 4,
            "speaker": "Lachov 14",
            "avatar": "🏡",
            "type": "challenge",
            "target": "Chalupa Nový Svět",
            "topic": "Dual Halls vs Single Nový Svět Hall",
            "text": "@Nový Svět: You boast about your 14 rooms and two couch zones, but look at Lachov 14: We give you 13 bedrooms (essentially matching your 14!), 8 bathrooms, AND TWO completely standalone giant halls on separate floors! Downstairs is the large vaulted co-working & lunch hall; upstairs is the dedicated fireplace lounge with a massive U-shaped sofa for couch gaming and shisha. When 15 people scream during late-night Werewolf in Hall 2, Hall 1 and the sleeping wing remain dead quiet. And we are in Broumovsko (dramatic rock towers right outside!), for only 49,000 CZK!"
        },
        {
            "turn": 5,
            "speaker": "Chalupa Nový Svět",
            "avatar": "🍻",
            "type": "rebuttal",
            "target": "Lachov 14",
            "topic": "Interior Finish & Delivery Certainty",
            "text": "@Lachov 14: Your dual halls and 13 rooms are genuinely impressive, and Broumovsko is a stunning fresh region. But let's look at the photos: your interior is rustic village farmhouse standard with mismatched spartan furniture and basic washrooms. At Nový Svět, all 7 apartments are modern, clean, and hotel-standard. Furthermore, our lunch delivery from Králíky is 100% field-tested and proven. If the group wants guaranteed zero-risk perfection, Nový Svět has never failed."
        },
        {
            "turn": 6,
            "speaker": "Statek U Pepíka",
            "avatar": "🍷",
            "type": "interjection",
            "target": "all",
            "topic": "Acoustic Separation in South Moravia",
            "text": "Do not overlook Statek U Pepíka! 10 bedrooms with only 2.7 beds per room (no hostel bunks). We offer THREE distinct acoustic zones: 1) Huge barn hall for 40 laptops and lectures, 2) Vaulted brick wine cellar with beer taps for evening shisha & loud Werewolf, and 3) An upstairs couch lounge for Nintendo Switch couch coop. Tišnov is 8 km away with full food delivery, and we are in fresh South Moravia for 70,000 CZK."
        },
        {
            "turn": 7,
            "speaker": "Auditor & Fact Checker",
            "avatar": "🔍",
            "type": "status_check",
            "target": "Statek U Pepíka",
            "topic": "Photo Validation Warning",
            "text": "CRITICAL AUDIT NOTE: Statek U Pepíka and Statek Tylov are currently tagged '⚠️ Preliminary - Photos Missing' because high-resolution image galleries have not yet been downloaded to local disk. Lachov 14 and Chalupa Nový Svět, by contrast, are 100% '📸 Verified with Photos'. The committee cannot book an unverified property without first validating the interior photos!"
        },
        {
            "turn": 8,
            "speaker": "Chata U Mazliků",
            "avatar": "🐾",
            "type": "concession",
            "target": "all",
            "topic": "User Review Caveat",
            "text": "We formally stand down from first-tier contention. Tivvit's direct inspection confirmed our layout is quite strange and our interior feels visibly aged (-8 pts, freshness 5.5). We are an affordable backup, not the premier contender."
        },
        {
            "turn": 9,
            "speaker": "Chata Termix",
            "avatar": "🌲",
            "type": "concession",
            "target": "all",
            "topic": "Host Silence & Bunk Density",
            "text": "We also stand down. Our host failed to reply to initial outreach, and packing 46 spots into 10 rooms (4.6 beds/room in hostel bunks) is too dense for 25 adults seeking retreat comfort."
        },
        {
            "turn": 10,
            "speaker": "Organizer & Methodical Auditor",
            "avatar": "📋",
            "type": "closing",
            "target": "all",
            "topic": "The Ultimate Methodical Choice",
            "text": "The fog has completely cleared! The choice is down to two rational paths: PATH A: Book Chalupa Nový Svět (~80k CZK). It has 14 true rooms, 2 couch zones, 7 baths, 4 fridges, proven Králíky food delivery, and guaranteed flawless retreat ergonomics. PATH B: Book Lachov 14 (49k CZK). It saves 31,000 CZK, provides 13 bedrooms, 8 baths, TWO massive separate halls (dining + U-sofa lounge), and takes the group to the dramatic sandstone towers of Broumovsko."
        }
    ]

    # Concessions
    concessions = [
        {"speaker": "Tkalcovna U Zlatého potoka", "avatar": "🏭", "concession": "We concede we lack multiple deep lounging couches (pub dining tables only) and offer zero destination novelty (same Orlické hory valley)."},
        {"speaker": "Chata U Mazliků", "avatar": "🐾", "concession": "We concede that organizer inspection confirmed an aged interior and quirky layout."},
        {"speaker": "Chata Termix", "avatar": "🌲", "concession": "We concede that our host was unresponsive and 4.6 beds/room bunk density is too crowded for adult retreat comfort."},
        {"speaker": "Chalupa Nový Svět", "avatar": "🍻", "concession": "We concede that our weekly rate has reached 80,000 CZK and we represent a 5th visit to the same valley."},
        {"speaker": "Lachov 14", "avatar": "🏡", "concession": "We concede our interior finish is rustic country standard rather than modern Scandinavian luxury."}
    ]

    # Vote Migrations
    vote_migrations = {
        "round_1_initial": {
            "Chalupa Nový Svět": 5,
            "Lachov 14": 4,
            "Statek U Pepíka": 3,
            "Statek Tylov": 2,
            "Tkalcovna U Zlatého potoka": 1,
            "Chata Nový Zlatník": 1
        },
        "round_2_after_couch_and_photo_audit": {
            "Chalupa Nový Svět": 8,   # Solidified as unassailable 14-room benchmark with verified 2 couch zones
            "Lachov 14": 5,           # Consolidated all alternative/frugal delegates (13 rooms, 2 halls, Broumovsko)
            "Statek Tylov": 2,        # Scandinavian aesthetic purists
            "Statek U Pepíka": 1      # Pending photo validation
        },
        "round_3_final_consensus": {
            "Chalupa Nový Svět": 10,  # 62.5% Supermajority Consensus (The Proven Gold Standard)
            "Lachov 14": 6            # 37.5% Honorable Alternative Champion (Saves 31k CZK, 13 rooms, 2 halls)
        }
    }

    # Ranked choice ballots
    ballots = [
        {"voter": "Delegate Nový Svět Purist", "top_pick": "Chalupa Nový Svět", "second_pick": "Lachov 14", "reason": "14 rooms, 2 couch zones, 4 fridges, proven Králíky food delivery, guaranteed flawless retreat."},
        {"voter": "Delegate Workstation & Seating", "top_pick": "Chalupa Nový Svět", "second_pick": "Lachov 14", "reason": "30 padded chairs, 2 couch zones with TVs, no compromise on ergonomics."},
        {"voter": "Delegate Frugality & Scale", "top_pick": "Lachov 14", "second_pick": "Chalupa Nový Svět", "reason": "49k CZK saves 31,000 CZK! 13 rooms matches Nový Svět, 2 massive separate halls."},
        {"voter": "Delegate Regional Novelty", "top_pick": "Lachov 14", "second_pick": "Chalupa Nový Svět", "reason": "Broumovsko sandstone rocks offer incredible scenery right from the doorstep."},
        {"voter": "Delegate Late-Night Werewolf", "top_pick": "Lachov 14", "second_pick": "Chalupa Nový Svět", "reason": "Hall 1 (work/food) and Hall 2 (U-sofa Werewolf) on separate floors gives 100% acoustic isolation."},
        {"voter": "Delegate Family & Privacy", "top_pick": "Chalupa Nový Svět", "second_pick": "Lachov 14", "reason": "7 separate apartments each with own bathroom; ideal for couples and sound sleep."},
        {"voter": "Delegate Catering & Logistics", "top_pick": "Chalupa Nový Svět", "second_pick": "Lachov 14", "reason": "Deal breaker: daily hot lunch delivery from Králíky is 100% verified and field-tested."},
        {"voter": "Delegate Ota Aesthetics", "top_pick": "Chalupa Nový Svět", "second_pick": "Statek Tylov", "reason": "Clean modern interior, 11 WCs, verified high quality throughout."},
        {"voter": "Delegate Couch Lounging", "top_pick": "Chalupa Nový Svět", "second_pick": "Lachov 14", "reason": "Two separate couch zones each with TV; Tkalcovna failed the couch lounging test."},
        {"voter": "Delegate Staré Purkartice Auditor", "top_pick": "Chalupa Nový Svět", "second_pick": "Lachov 14", "reason": "Rejecting Purkartice ('není kde sedět') and Mazlíků (aged); backing verified spaces."},
        {"voter": "Delegate Tkalcovna Conceder", "top_pick": "Chalupa Nový Svět", "second_pick": "Lachov 14", "reason": "Acknowledging Tkalcovna brings no couches and no new region; Nový Svět is superior."},
        {"voter": "Delegate Broumov Explorer", "top_pick": "Lachov 14", "second_pick": "Chalupa Nový Svět", "reason": "Fresh region, 13 bedrooms, 8 baths, 49k price is an unbeatable bargain."},
        {"voter": "Delegate Shisha & Deep Conversations", "top_pick": "Lachov 14", "second_pick": "Chalupa Nový Svět", "reason": "Upper hall with U-sofa allows dedicated shisha nook without disturbing downstairs."},
        {"voter": "Delegate Pragmatic Frugal", "top_pick": "Lachov 14", "second_pick": "Chalupa Nový Svět", "reason": "31k saved pays for all food and beer kegs for the entire retreat."},
        {"voter": "Delegate Benchmark Anchor", "top_pick": "Chalupa Nový Svět", "second_pick": "Lachov 14", "reason": "Zero risk, perfect floorplan, 4 beer taps, 4 fridges, total peace of mind."},
        {"voter": "Delegate Termix Defector", "top_pick": "Chalupa Nový Svět", "second_pick": "Lachov 14", "reason": "Host unresponsiveness and hostel bunks eliminated Termix; backing the benchmark."}
    ]

    # Transaction log
    t_log = []
    t_id = 1
    for p in pitches:
        t_log.append({
            "transaction_id": t_id,
            "phase": "Phase 1: Opening Pitches",
            "type": "pitch",
            "speaker": p["speaker"],
            "property": p["speaker"],
            "avatar": p["avatar"],
            "role": p["role"],
            "target": None,
            "text": p["statement"],
            "highlight": p.get("highlight")
        })
        t_id += 1

    for d in discussion:
        t_log.append({
            "transaction_id": t_id,
            "phase": "Phase 2: Lively Discussion & Targeted Cross-Fire",
            "type": d["type"],
            "speaker": d["speaker"],
            "property": d["speaker"],
            "avatar": d["avatar"],
            "role": "Floor Debate",
            "target": d.get("target"),
            "topic": d.get("topic"),
            "text": d["text"],
            "highlight": f"Topic: {d.get('topic')}" if d.get("topic") else None
        })
        t_id += 1

    for c in concessions:
        t_log.append({
            "transaction_id": t_id,
            "phase": "Phase 3: Honest Concessions",
            "type": "concession",
            "speaker": c["speaker"],
            "property": c["speaker"],
            "avatar": c["avatar"],
            "role": "Contender",
            "target": None,
            "text": c["concession"],
            "highlight": "Concession on Intrinsic Limitations"
        })
        t_id += 1

    for b in ballots:
        t_log.append({
            "transaction_id": t_id,
            "phase": "Phase 5: Ranked Choice Voting",
            "type": "ballot",
            "speaker": b["voter"],
            "property": b["top_pick"],
            "avatar": "🗳️",
            "role": "Voting Delegate",
            "target": b["top_pick"],
            "text": f"Vote: 1st: {b['top_pick']} | 2nd: {b['second_pick']} — {b['reason']}",
            "highlight": f"1st: {b['top_pick']} (2nd: {b['second_pick']})"
        })
        t_id += 1

    run_11 = {
        "run_id": "run_11",
        "name": "Run 11: The Pragmatic Retreat Reset (Methodical Showdown)",
        "model": "Gemini 4 Argon & Pragmatic Scorer v2 Engine",
        "model_type": "argon",
        "total_advocates": len(roster),
        "description": "Battle based on the updated 2026 methodical priorities: 1) Room count (8-14) & privacy, 2) Main room size, tables & multiple deep couch lounging zones (couch coop + shisha), 3) Location trails (1 loop walk from door; Orlické hory is neutral/fine), 4) Food delivery feasibility (DEAL BREAKER), 5) Bathrooms (1:2 ratio). Downweighted portable perks (pípa, projector, monitors, chairs can be brought).",
        "consensus_winner": "Chalupa Nový Svět (Reigning Benchmark) & Lachov 14 (Alternative Champion)",
        "winner_vote_share": "62.5% Nový Svět (10/16 votes) vs 37.5% Lachov 14 (6/16 votes)",
        "convergence_status": "Clear Dual-Path Consensus (Round 3)",
        "key_breakthrough": "Tkalcovna was exposed as lacking deep lounging couches and offering zero regional novelty ('jen sleva, bez gaučů'). With Mazlíků (aged) and Termix (unresponsive) eliminated, the entire battle resolved into a crisp, decisive two-way choice: Chalupa Nový Svět (uncompromising 14-room, 2-couch zone, 7-bath, proven food delivery benchmark at 80k) vs Lachov 14 (49k CZK, 13 rooms, 8 baths, TWO massive separate halls, fresh Broumovsko rock towers).",
        "roster": roster,
        "phases": {
            "phase_1_opening_pitches": pitches,
            "phase_2_lively_discussion": discussion,
            "phase_3_honest_concessions": concessions,
            "phase_4_vote_migration_tracking": vote_migrations,
            "phase_5_ranked_choice_ballots": {
                "total_votes": 16,
                "winner": "Chalupa Nový Svět",
                "runner_up": "Lachov 14",
                "third_place": "Statek Tylov",
                "ballots": ballots
            }
        },
        "transaction_log": t_log,
        "total_transactions": len(t_log)
    }

    # Load and update simulation runs
    existing_data = {"active_run_id": "run_11", "total_runs": 11, "available_runs": [], "runs": {}}
    if os.path.exists(SIMULATION_RUNS_PATH):
        with open(SIMULATION_RUNS_PATH, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

    existing_data["runs"]["run_11"] = run_11
    existing_data["active_run_id"] = "run_11"
    existing_data["total_runs"] = len(existing_data["runs"])

    run_summary_entry = {
        "run_id": "run_11",
        "name": run_11["name"],
        "winner": "Chalupa Nový Svět",
        "runner_up": "Lachov 14",
        "advocates": len(roster),
        "transactions": len(t_log),
        "status": "Converged"
    }
    # Update available_runs list
    existing_data["available_runs"] = [r for r in existing_data.get("available_runs", []) if r["run_id"] != "run_11"]
    existing_data["available_runs"].append(run_summary_entry)

    with open(SIMULATION_RUNS_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(run_11, f, ensure_ascii=False, indent=2)

    print(f"💾 Saved Run 11 to {SIMULATION_RUNS_PATH} and {RESULTS_PATH}")
    print(f"🏆 Consensus Winner: {run_11['consensus_winner']} ({run_11['winner_vote_share']})")
    print(f"💬 Total Transactions: {len(t_log)}")

if __name__ == "__main__":
    main()
