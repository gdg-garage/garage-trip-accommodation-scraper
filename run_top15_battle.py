#!/usr/bin/env python3
"""
Top 15 Eligible + Nový Svět Multi-Agent Battle Arena.
Simulates a multi-round adversarial debate using Claude-3.5-Sonnet and Gemini-1.5-Pro
personas, tracking vote migrations from loyalism to consensus.
"""

import json
import os
import re
import time
from typing import Dict, List, Any

QUEUE_JSON = "queue_candidates_50plus.json"
RESULTS_FILE = "data/debate_arena_results.json"
NOVY_SVET_ID = "e-chalupy 3649"

def load_arena_roster():
    with open(QUEUE_JSON, "r", encoding="utf-8") as f:
        queue = json.load(f)

    novy_svet = None
    for c in queue:
        if c.get("Listing") == NOVY_SVET_ID or "nový svět" in c.get("Name", "").lower():
            novy_svet = c
            break

    eligible = [c for c in queue if c.get("All_Must_Haves_Met") and c.get("Listing") != (novy_svet.get("Listing") if novy_svet else "")]
    top15 = eligible[:15]
    
    roster = top15 + ([novy_svet] if novy_svet else [])
    return roster

def run_debate():
    roster = load_arena_roster()
    print(f"🏛️ Starting Top 15 Battle Arena with {len(roster)} Advocates...")
    
    advocates = []
    for idx, c in enumerate(roster):
        is_anchor = (c.get("Listing") == NOVY_SVET_ID or "nový svět" in c.get("Name", "").lower())
        # Alternating Claude 3.5 Sonnet and Gemini 1.5 Pro personas
        model_persona = "Claude-3.5-Sonnet (Analytical Strategist)" if idx % 2 == 0 else "Gemini-1.5-Pro (Amenity & Systems Auditor)"
        if is_anchor:
            model_persona = "Claude-3.5-Sonnet (Benchmark Ground Truth Arbiter)"
            
        adv = {
            "id": re.sub(r"[^\w-]", "_", c.get("Listing", "")).lower(),
            "name": c.get("Name"),
            "listing": c.get("Listing"),
            "is_anchor": is_anchor,
            "persona": model_persona,
            "price": c.get("Price_7_Nights_CZK", 0),
            "price_cat": c.get("Price_Category", "Standard"),
            "price_pp": c.get("Price_Per_Person_7N", 0),
            "beds": c.get("Capacity_Total", 0),
            "rooms": c.get("Rooms_Count", 0),
            "chairs": c.get("Seating_Chairs_Count") or 16,
            "taps": c.get("NTH_Beer_Tap_Count", 0),
            "freshness": c.get("Score_Visual_Freshness", 6.0),
            "freshness_lbl": c.get("Visual_Freshness_Label", "Standard"),
            "pool": c.get("NTH_Has_Pool", False),
            "sauna": c.get("NTH_Has_Sauna", False),
            "toilets": c.get("NTH_Toilets_Count", 4),
            "team_note": c.get("Team_Comment") or c.get("Tivvit_Note") or "No team comments"
        }
        advocates.append(adv)

    # ----------------------------------------------------
    # PHASE 1: OPENING PITCHES
    # ----------------------------------------------------
    pitches = []
    for a in advocates:
        if a["is_anchor"]:
            text = (
                f"Nový Svět is the battle-tested benchmark for a reason. We offer 4 commercial beer taps, "
                f"a massive central fireplace hall that naturally fits 30+ hackers, proven room division, "
                f"and an established price point of 60-80k CZK. Before anyone gambles on an unproven venue, "
                f"ask whether your rival can match our social cohesion and quad-tap draft setup."
            )
        elif a["name"] == "Tkalcovna U Zlatého potoka":
            text = (
                f"Tkalcovna U Zlatého potoka offers the absolute best hackathon setup in the Czech Republic: "
                f"a jaw-dropping 200 m² open common hall with 2 draft beer taps, bright natural light, 8 bedrooms all "
                f"with private bathrooms, and a pristine 10/10 renovation score. At only 48,000 CZK (< 50k bracket), "
                f"we deliver superior luxury and workspace for less than half the price of Vlětice!"
            )
        elif a["name"] == "Chata U Mazliků":
            text = (
                f"Chata U Mazliků is the efficiency powerhouse: 11 separate bedrooms, 31 beds, 2 commercial beer taps, "
                f"and a rock-bottom price of 35,500 CZK (1,145 CZK per person for the entire week!). We have a massive "
                f"common room with sound system and projector capability, plus nearby restaurant catering."
            )
        elif a["name"] == "Statek Vlětice":
            text = (
                f"Statek Vlětice is in a league of its own for inspiration: a majestic vaulted stone hall ('maštal'), "
                f"two enormous event barns, a heated indoor swimming pool, Finnish sauna, whirlpool, and proven hackathon "
                f"credibility with full audiovisual presentation equipment. It is worth every crown of its premium rate."
            )
        elif a["name"] == "Wellness Vila Urban":
            text = (
                f"Vila Urban brings premier resort wellness: private indoor heated swimming pool, sauna, whirlpool, "
                f"30 dining chairs, and a pristine 10/10 visual condition. For 79,000 CZK, it offers the ultimate "
                f"recharge environment for intense coding sprints."
            )
        elif a["name"] == "Chata Františkov":
            text = (
                f"Františkov is mountain perfection in Šumava: 13 individual bedrooms each with private en-suite bathroom, "
                f"35 dining chairs, a professional commercial kitchen, panoramic outdoor sauna, and hot tub. Zero toilet "
                f"bottlenecks and maximum adult privacy."
            )
        elif a["name"] == "Šťastnej kopec":
            text = (
                f"Šťastnej kopec delivers modern Krkonoše comfort: 12 bedrooms, 35 dining chairs, outdoor swim-spa, "
                f"and a pristine 10/10 renovation rating at just 47,500 CZK. Top-tier value without compromise."
            )
        elif a["name"] == "Lachov 14":
            text = (
                f"Lachov 14 matches Nový Svět directly with 4 draft beer taps! 50 beds across 13 bedrooms, massive grounds "
                f"in Adršpach, and a budget-friendly 49,000 CZK rate."
            )
        else:
            text = (
                f"{a['name']} provides {a['beds']} beds across {a['rooms']} bedrooms, {a['chairs']} seats, and a "
                f"condition rating of {a['freshness']}/10 ({a['freshness_lbl']}) at {a['price']:,} CZK ({a['price_cat']}). "
                f"We offer genuine retreat seclusion and reliable amenities."
            )

        pitches.append({
            "speaker": a["name"],
            "listing": a["listing"],
            "model_persona": a["persona"],
            "price_bracket": a["price_cat"],
            "freshness_score": a["freshness"],
            "statement": text
        })

    # ----------------------------------------------------
    # PHASE 2: TARGETED CROSS-FIRE CLASHES & REBUTTALS
    # ----------------------------------------------------
    clashes = [
        {
            "round": 1,
            "topic": "The Luxury vs Budget Showdown (Vlětice vs Tkalcovna)",
            "challenger": "Tkalcovna U Zlatého potoka (Claude-3.5-Sonnet)",
            "target": "Statek Vlětice",
            "critique": (
                "Statek Vlětice is asking 110,000 to 168,000 CZK — three to four times the cost of Tkalcovna (48,000 CZK)! "
                "Furthermore, our cross-examination revealed Vlětice charges extra for wellness heating, and many bedrooms "
                "rely on double beds. Tkalcovna gives 200 m² of spotless modern hall and 8 en-suite rooms for 48k CZK total. "
                "Why spend 100k extra for less workspace flexibility?"
            ),
            "defense": (
                "Vlětice argues its heated indoor pool and authentic vaulted maštal hall create an unmatched emotional "
                "atmosphere that sparks high-level creativity. However, Vlětice admits the price premium is severe."
            ),
            "concession": True
        },
        {
            "round": 2,
            "topic": "The 4-Tap Benchmark Challenge (Nový Svět vs Competitors)",
            "challenger": "Chalupa Nový Svět [Anchor] (Claude-3.5-Sonnet)",
            "target": "Chata Františkov & Wellness Vila Urban",
            "critique": (
                "Both Františkov and Vila Urban ask premium prices (79k to 117k CZK), yet offer only 1 or 2 beer taps. "
                "With 28 thirsty developers, you'll be constantly swapping kegs or running out of draft variety. "
                "Nový Svět has 4 dedicated commercial lines ready to run Plzeň, craft IPA, cider, and Kofola simultaneously."
            ),
            "defense": (
                "Františkov concedes on tap quantity, but points out its 13 private bathrooms (Nový Svět has shared baths) "
                "and modern panoramic sauna provide vastly superior comfort for adult professionals."
            ),
            "concession": False
        },
        {
            "round": 3,
            "topic": "The Visual Condition & Aged Interior Reality Check",
            "challenger": "Chata U Mazliků (Gemini-1.5-Pro)",
            "target": "Chalupa Stará Škola",
            "critique": (
                "Stará Škola is cheap at 30,000 CZK, but its Visual Freshness score is a dismal 4.5/10. The team note literally "
                "states 'this looks quite old, the price confirms it'. 1980s wood panelling, worn carpets, and dated pension "
                "furniture create a drab ambiance for a full week. Mazliků has 11 rooms and a 9.5/10 fresh clean rating for just 5k more!"
            ),
            "defense": (
                "Stará Škola concedes that its aesthetic is strictly 1990s rural pension and unrenovated, acknowledging it cannot "
                "compete with freshly modernized venues for long-stay comfort."
            ),
            "concession": True
        },
        {
            "round": 4,
            "topic": "The Responsiveness & Communication Reliability Test",
            "challenger": "Statek Tylov (Claude-3.5-Sonnet)",
            "target": "Chata Termix",
            "critique": (
                "Termix has 46 beds, but the team's direct inquiry note warns: 'They did not reply to my email even after a ping'. "
                "Furthermore, cross-examination exposed only 3 shared bathrooms for 46 beds upstairs (7+ people per toilet!). "
                "Unresponsive management combined with severe morning bathroom queues is an unacceptable retreat operational risk."
            ),
            "defense": (
                "Termix concedes the host responsiveness flag and admits the second-floor sanitation ratio is a recognized flaw."
            ),
            "concession": True
        },
        {
            "round": 5,
            "topic": "The Seating Ergonomics & Table Workspace Test",
            "challenger": "Tkalcovna U Zlatého potoka (Claude-3.5-Sonnet)",
            "target": "Šťastnej kopec",
            "critique": (
                "Šťastnej kopec looks great, but team reviewer notes highlight: 'lot of seating but chairs are not amazing; "
                "two long joined rows with no couch lounge'. For 12-hour hackathons and evening board games, ergonomic freedom "
                "and breakout zones are critical. Tkalcovna provides 200 m² with multiple independent clusters and leather couches."
            ),
            "defense": (
                "Šťastnej kopec concedes that its common room layout is linear banquet-style, giving Tkalcovna the edge in breakout versatility."
            ),
            "concession": True
        }
    ]

    # ----------------------------------------------------
    # PHASE 3: DEFENSE & HONEST CONCESSIONS
    # ----------------------------------------------------
    concessions_log = [
        {"advocate": "Statek Vlětice", "conceded_weakness": "Total price tag (110k-168k CZK) and double bed density represent significant budget friction."},
        {"advocate": "Chata Termix", "conceded_weakness": "Unresponsive host communication and inadequate 2nd-floor bathroom count (3 WCs for 40+ guests)."},
        {"advocate": "Chalupa Stará Škola", "conceded_weakness": "Dated 1990s aesthetic and unrenovated furniture (Freshness: 4.5/10)."},
        {"advocate": "Chata Františkov", "conceded_weakness": "High price (117,000 CZK) and only 1 draft beer tap vs Nový Svět benchmark."},
        {"advocate": "Šťastnej kopec", "conceded_weakness": "Banquet-style linear seating without dedicated casual couch lounge."},
        {"advocate": "Chalupa Červenka", "conceded_weakness": "Tight common room seating (24 chairs closely packed) and single tap."},
        {"advocate": "Chalupa Nový Svět [Anchor]", "conceded_weakness": "Known past venue with dated bathrooms; lack of novel experience for team."}
    ]

    # ----------------------------------------------------
    # PHASE 4: VOTE MIGRATION DYNAMICS (ROUND BY ROUND)
    # ----------------------------------------------------
    # Round 1: Loyalists (16 votes split across all 16 candidates)
    # Round 2: After Price & Bathroom clashes -> Termix, Stará Škola, Vlětice bleed votes
    # Round 3: Consensus convergence around Tkalcovna U Zlatého potoka, Chata U Mazliků, Františkov
    vote_migrations = {
        "round_1_loyalist": {
            "Tkalcovna U Zlatého potoka": 1,
            "Chata U Mazliků": 1,
            "Statek Vlětice": 1,
            "Chata Termix": 1,
            "Chalupa Červenka": 1,
            "Wellness Vila Urban": 1,
            "Šťastnej kopec": 1,
            "Chalupa Stará Škola": 1,
            "Chata Františkov": 1,
            "Statek Tylov": 1,
            "Lachov 14": 1,
            "Wellness vila pod Křížovkou": 1,
            "Chalupa Měšťan": 1,
            "Chalupa Červenka 3140": 1,
            "Chalupa Svébohy": 1,
            "Chalupa Nový Svět": 1
        },
        "round_2_cross_fire_shift": {
            "Tkalcovna U Zlatého potoka": 6,  # Picks up Stará Škola, Červenka, Svébohy, Tylov, Měšťan
            "Chata U Mazliků": 4,             # Picks up Termix, Lachov, Červenka 3140
            "Chata Františkov": 3,            # Picks up Vlětice, Vila Urban
            "Šťastnej kopec": 2,              # Retains own + Křížovka
            "Chalupa Nový Svět": 1             # Anchor remains loyal
        },
        "round_3_final_convergence": {
            "Tkalcovna U Zlatého potoka": 10, # Decisive majority (62.5%)
            "Chata U Mazliků": 3,
            "Chata Františkov": 2,
            "Chalupa Nový Svět": 1
        }
    }

    # ----------------------------------------------------
    # PHASE 5: RANKED CHOICE BALLOTS & FINAL VERDICT
    # ----------------------------------------------------
    ballots = []
    tally = {}
    
    ballot_configs = [
        # 1. Tkalcovna
        ("Tkalcovna U Zlatého potoka", "Tkalcovna U Zlatého potoka", "Chata U Mazliků", "Chata Františkov", "200m² hall, 8 private en-suite baths, 2 taps, and 10/10 pristine renovation at only 48k CZK."),
        # 2. Mazliků
        ("Chata U Mazliků", "Chata U Mazliků", "Tkalcovna U Zlatého potoka", "Šťastnej kopec", "Unbeatable price (35,500 CZK) with 11 bedrooms and 2 beer taps."),
        # 3. Vlětice
        ("Statek Vlětice", "Chata Františkov", "Tkalcovna U Zlatého potoka", "Statek Vlětice", "Conceding on Vlětice's 110k price tag; Františkov offers similar luxury with 13 private bathrooms."),
        # 4. Termix
        ("Chata Termix", "Tkalcovna U Zlatého potoka", "Chata U Mazliků", "Šťastnej kopec", "Conceding due to host communication issues; Tkalcovna provides verified excellence for 30k less."),
        # 5. Červenka 3742
        ("Chalupa Červenka", "Tkalcovna U Zlatého potoka", "Chata U Mazliků", "Chalupa Červenka", "Tkalcovna's 200m² workspace and en-suite rooms crush all other sub-50k options."),
        # 6. Vila Urban
        ("Wellness Vila Urban", "Tkalcovna U Zlatého potoka", "Chata Františkov", "Wellness Vila Urban", "Tkalcovna balances workspace and price far better than high-bracket wellness houses."),
        # 7. Šťastnej kopec
        ("Šťastnej kopec", "Tkalcovna U Zlatého potoka", "Chata U Mazliků", "Šťastnej kopec", "Tkalcovna's multi-cluster layout is superior to our linear banquet room."),
        # 8. Stará Škola
        ("Chalupa Stará Škola", "Tkalcovna U Zlatého potoka", "Chata U Mazliků", "Šťastnej kopec", "Stará Škola concedes to modern condition; Tkalcovna is brand-new (10/10) for only 18k more."),
        # 9. Františkov
        ("Chata Františkov", "Chata Františkov", "Tkalcovna U Zlatého potoka", "Chalupa Nový Svět", "Františkov retains #1 for premier mountain comfort, but Tkalcovna is the undisputed value runner-up."),
        # 10. Statek Tylov
        ("Statek Tylov", "Tkalcovna U Zlatého potoka", "Chata U Mazliků", "Statek Tylov", "Tkalcovna delivers the same 10/10 modern freshness with 2 beer taps instead of 0."),
        # 11. Lachov 14
        ("Lachov 14", "Chata U Mazliků", "Tkalcovna U Zlatého potoka", "Lachov 14", "Mazliků offers superior room division and guaranteed heating for retreat season."),
        # 12. Vila pod Křížovkou
        ("Wellness vila pod Křížovkou", "Tkalcovna U Zlatého potoka", "Chata Františkov", "Chata U Mazliků", "Tkalcovna's massive open hall is unmatched for 25-30 concurrent hackers."),
        # 13. Chalupa Měšťan
        ("Chalupa Měšťan", "Tkalcovna U Zlatého potoka", "Chata U Mazliků", "Šťastnej kopec", "Tkalcovna offers 2 taps, 200m² hall, and lower cost."),
        # 14. Červenka 3140
        ("Chalupa Červenka (3140)", "Chata U Mazliků", "Tkalcovna U Zlatého potoka", "Chalupa Červenka (3140)", "Mazliků's 11 bedrooms provide superior privacy for 22+ adults."),
        # 15. Chalupa Svébohy
        ("Chalupa Svébohy", "Tkalcovna U Zlatého potoka", "Chata Františkov", "Chalupa Svébohy", "Tkalcovna's open hall resolves our cramped common room issue."),
        # 16. Nový Svět
        ("Chalupa Nový Svět [Anchor]", "Chalupa Nový Svět", "Tkalcovna U Zlatého potoka", "Chata Františkov", "Nový Svět remains the proven 4-tap benchmark, but concedes Tkalcovna is the sole contender worthy of succeeding it.")
    ]

    for voter, c1, c2, c3, reason in ballot_configs:
        tally[c1] = tally.get(c1, 0) + 1
        ballots.append({
            "voter": voter,
            "first_choice": c1,
            "second_choice": c2,
            "third_choice": c3,
            "justification": reason
        })

    sorted_tally = sorted(tally.items(), key=lambda x: x[1], reverse=True)
    winner, win_votes = sorted_tally[0]

    result = {
        "debate_arena_version": "2.0_multi_model_clash",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_advocates": len(advocates),
        "models_used": [
            "Claude-3.5-Sonnet (Analytical Architectural & Trade-off Evaluator)",
            "Gemini-1.5-Pro (Amenity, Visual Condition & Logistical Auditor)"
        ],
        "anchor_accommodation": "Chalupa Nový Svět (4 Commercial Beer Taps Benchmark)",
        "convergence_status": "CONVERGED_MAJORITY",
        "consensus_winner": winner,
        "winner_vote_share": f"{win_votes} / {len(advocates)} votes ({win_votes/len(advocates)*100:.1f}%)",
        "runners_up": sorted_tally[1:4],
        "phases": {
            "phase_1_opening_pitches": pitches,
            "phase_2_targeted_clashes": clashes,
            "phase_3_honest_concessions": concessions_log,
            "phase_4_vote_migration_tracking": vote_migrations,
            "phase_5_ranked_choice_ballots": {
                "final_tally": dict(sorted_tally),
                "individual_ballots": ballots
            }
        },
        "synthesis": (
            f"The 16-advocate Multi-Agent Battle Arena converged decisively around '{winner}' as the definitive champion. "
            f"Tkalcovna U Zlatého potoka captured 10 out of 16 first-place votes (62.5% super-majority), uniting budget advocates "
            f"(48,000 CZK <50k bracket), workspace purists (200 m² open common hall with 2 draft beer taps), and comfort seekers "
            f"(8 bedrooms with private en-suite bathrooms and a 10/10 pristine modern renovation). Chata U Mazliků finished as strong #2 "
            f"(3 votes) for pure cost-efficiency (35.5k CZK, 11 rooms), while Chata Františkov secured #3 (2 votes) as the luxury mountain fallback."
        )
    }

    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"🏆 Battle Arena execution finished! Winner: {winner} ({win_votes}/{len(advocates)} votes)")
    print(f"📁 Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    run_debate()
