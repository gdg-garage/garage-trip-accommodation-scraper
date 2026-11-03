#!/usr/bin/env python3
"""
aggregate_model_evaluations.py
Aggregates all individual model evaluations from data/model_evaluations/*.json
into data/rankings_final_multimodal.json and updates queue_candidates_50plus.json,
queue_candidates_50plus.csv, and sheet_updated_with_extractors.xlsx.
"""

import json
import glob
import os
import csv
import openpyxl

def normalize_key(k):
    if not k:
        return ""
    s = str(k).strip().lower()
    for prefix in ['e-chalupy ', 'echalupy ', 'booking ', 'o']:
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    return s

def main():
    eval_files = glob.glob('data/model_evaluations/*.json')
    print(f"Found {len(eval_files)} model evaluation files in data/model_evaluations/")

    eval_by_id = {}
    eval_list = []

    for fpath in eval_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            pid = normalize_key(data.get('property_id') or os.path.basename(fpath).replace('.json', ''))
            data['property_id_norm'] = pid
            eval_by_id[pid] = data
            eval_list.append(data)
        except Exception as e:
            print(f"Error reading {fpath}: {e}")

    # Sort eval_list by final_score descending
    eval_list.sort(key=lambda x: x.get('final_score', 0), reverse=True)

    # Save data/rankings_final_multimodal.json
    with open('data/rankings_final_multimodal.json', 'w', encoding='utf-8') as f:
        json.dump(eval_list, f, indent=2, ensure_ascii=False)
    print("Saved data/rankings_final_multimodal.json")

    # Now load queue_candidates_50plus.json
    with open('queue_candidates_50plus.json', 'r', encoding='utf-8') as f:
        candidates = json.load(f)

    print(f"Loaded {len(candidates)} candidates from queue_candidates_50plus.json")

    matched_count = 0
    for cand in candidates:
        listing = normalize_key(cand.get('Listing', ''))
        # Try finding in eval_by_id
        ev = eval_by_id.get(listing)
        if not ev:
            # Try matching digits from URL
            url = cand.get('Url', '')
            import re
            m = re.search(r'e-chalupy\.cz/(\d+)', url)
            if m:
                ev = eval_by_id.get(m.group(1))

        if ev:
            matched_count += 1
            cand['Model_Evaluated'] = True
            cand['Model_Final_Score'] = ev.get('final_score', 0.0)
            cand['Model_Common_Room_Score'] = ev.get('common_room_score', 0.0)
            cand['Model_Tables_Score'] = ev.get('tables_score', 0.0)
            cand['Model_Sleeping_Score'] = ev.get('sleeping_score', 0.0)
            cand['Model_Wellness_Score'] = ev.get('wellness_score', 0.0)
            cand['Model_Facilities_Score'] = ev.get('facilities_score', 0.0)
            cand['Model_Image_Reasoning'] = ev.get('image_reasoning', '')
            cand['Model_Tables_Confirmed'] = ev.get('tables_confirmed_by_images', False)
            cand['Model_Pros'] = ev.get('pros', [])
            cand['Model_Cons'] = ev.get('cons', [])
            cand['Model_Verdict'] = ev.get('verdict', '')
            cand['Model_Used'] = ev.get('model_used', 'antigravity-gemini')

            # Calculate Updated Total_Score: Model_Final_Score + Score_User_Feedback_Total
            user_feedback = cand.get('Score_User_Feedback_Total', 0.0)
            cand['Total_Score'] = round(ev.get('final_score', 0.0) + user_feedback, 1)
        else:
            cand['Model_Evaluated'] = False
            cand['Model_Final_Score'] = None
            cand['Model_Common_Room_Score'] = None
            cand['Model_Tables_Score'] = None
            cand['Model_Sleeping_Score'] = None
            cand['Model_Wellness_Score'] = None
            cand['Model_Facilities_Score'] = None
            cand['Model_Image_Reasoning'] = ''
            cand['Model_Tables_Confirmed'] = False
            cand['Model_Pros'] = []
            cand['Model_Cons'] = []
            cand['Model_Verdict'] = ''
            cand['Model_Used'] = ''

    print(f"Matched {matched_count} candidates with model evaluations.")

    # Re-rank candidates:
    # Priority 1: All_Must_Haves_Met==True and Model_Evaluated==True sorted by Total_Score desc
    # Priority 2: All_Must_Haves_Met==True and Model_Evaluated==False sorted by Total_Score desc
    # Priority 3: All_Must_Haves_Met==False sorted by Total_Score desc
    def sort_key(c):
        mh_met = 1 if c.get('All_Must_Haves_Met') else 0
        ev = 1 if c.get('Model_Evaluated') else 0
        score = c.get('Total_Score') or 0.0
        return (mh_met, ev, score)

    candidates.sort(key=sort_key, reverse=True)

    for rank_idx, c in enumerate(candidates, start=1):
        c['Rank'] = rank_idx

    # Save queue_candidates_50plus.json
    with open('queue_candidates_50plus.json', 'w', encoding='utf-8') as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)
    print("Updated queue_candidates_50plus.json")

    # Save queue_candidates_50plus.csv
    flat_rows = []
    # Collect all field names preserving order
    all_fields = []
    for c in candidates:
        for k in c.keys():
            if k not in all_fields:
                all_fields.append(k)

    for c in candidates:
        r = {}
        for k in all_fields:
            val = c.get(k)
            if isinstance(val, list):
                r[k] = " | ".join(str(x) for x in val)
            elif isinstance(val, dict):
                r[k] = json.dumps(val, ensure_ascii=False)
            else:
                r[k] = val
        flat_rows.append(r)

    with open('queue_candidates_50plus.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_fields)
        writer.writeheader()
        writer.writerows(flat_rows)
    print("Updated queue_candidates_50plus.csv")

    # Save sheet_updated_with_extractors.xlsx using openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Scored_Accommodations"

    ws.append(all_fields)
    for r in flat_rows:
        ws.append([r.get(k) for k in all_fields])

    wb.save('sheet_updated_with_extractors.xlsx')
    print("Updated sheet_updated_with_extractors.xlsx")

    print("\nTop 15 Ranked Retreat Accommodations:")
    for c in candidates[:15]:
        print(f"#{c['Rank']} {c['Name']} (ID: {c.get('Listing')}) - Total: {c['Total_Score']} (Model: {c['Model_Final_Score']}, User: {c.get('Score_User_Feedback_Total', 0.0)}) - Met MH: {c.get('All_Must_Haves_Met')}")

if __name__ == '__main__':
    main()
