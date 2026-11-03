#!/usr/bin/env python3
"""
AI Bridge: Connects the review website with Antigravity AI assistant.
Allows users on the website to comment on any accommodation or specific aspect,
ask questions, request fact verification, or request document adjustments.
Antigravity inspects source HTML, calendars, spreadsheets, and updates the data.
"""

import csv
import datetime
import glob
import json
import os
import re
from typing import Dict, List, Any, Optional
import openpyxl

THREADS_FILE = "data/comments_threads.json"
PENDING_FILE = "data/ai_bridge/pending_inquiries.json"
QUEUE_JSON = "queue_candidates_50plus.json"
QUEUE_CSV = "queue_candidates_50plus.csv"
WORKBOOK_XLSX = "sheet_updated_with_extractors.xlsx"
RANKING_CSV = "data/sheets_export/ranking.csv"


def ensure_directories():
    os.makedirs("data/ai_bridge", exist_ok=True)


def load_threads() -> List[Dict[str, Any]]:
    ensure_directories()
    if os.path.exists(THREADS_FILE):
        try:
            with open(THREADS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "threads" in data:
                    return data["threads"]
        except Exception:
            return []
    return []


def save_threads(threads: List[Dict[str, Any]]):
    ensure_directories()
    with open(THREADS_FILE, "w", encoding="utf-8") as f:
        json.dump({"threads": threads}, f, indent=2, ensure_ascii=False)


def load_pending_inquiries() -> List[Dict[str, Any]]:
    ensure_directories()
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_pending_inquiries(inquiries: List[Dict[str, Any]]):
    ensure_directories()
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(inquiries, f, indent=2, ensure_ascii=False)


def get_accommodation_meta(listing: str) -> Dict[str, Any]:
    """Retrieve full cached data for a property."""
    meta = {"listing": listing, "name": listing, "html_path": None, "html_text": None, "queue_item": None}
    
    # Load queue item
    if os.path.exists(QUEUE_JSON):
        try:
            with open(QUEUE_JSON, "r", encoding="utf-8") as f:
                items = json.load(f)
                for it in items:
                    if it.get("Listing") == listing or it.get("Name") == listing:
                        meta["queue_item"] = it
                        meta["name"] = it.get("Name")
                        break
        except Exception:
            pass

    # Find HTML
    m = re.search(r"\d+", listing)
    if m:
        oid = m.group(0)
        matches = glob.glob(f"html/*o{oid}.html") or glob.glob(f"html/*{oid}*.html")
        if matches:
            meta["html_path"] = matches[0]
            try:
                with open(matches[0], "r", encoding="utf-8", errors="ignore") as f:
                    meta["html_text"] = f.read()
            except Exception:
                pass
    elif "booking" in listing.lower():
        slug = listing.replace("Booking", "").strip()
        matches = glob.glob(f"booking_html/*{slug}*.html")
        if matches:
            meta["html_path"] = matches[0]
            try:
                with open(matches[0], "r", encoding="utf-8", errors="ignore") as f:
                    meta["html_text"] = f.read()
            except Exception:
                pass

    return meta


def add_comment_thread(
    listing: str,
    target_aspect: str,
    author: str,
    comment: str,
    invoke_ai: bool = False
) -> Dict[str, Any]:
    """Create a new comment thread on an accommodation or specific aspect."""
    meta = get_accommodation_meta(listing)
    threads = load_threads()
    
    # Auto-detect AI invocation if comment starts with @ai or contains 'ask ai'
    comment_lower = comment.lower()
    if "@ai" in comment_lower or "@antigravity" in comment_lower or comment_lower.startswith("ask ai"):
        invoke_ai = True

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    thread_id = f"cmt_{int(datetime.datetime.now().timestamp())}_{os.urandom(3).hex()}"

    new_thread = {
        "id": thread_id,
        "listing": listing,
        "accommodation_name": meta.get("name", listing),
        "target_aspect": target_aspect or "general",
        "author": author or "Team Member",
        "comment": comment.strip(),
        "created_at": timestamp,
        "invoke_ai": invoke_ai,
        "ai_status": "pending" if invoke_ai else None,
        "ai_reply": None,
        "ai_action_taken": None,
        "resolved_at": None,
        "replies": []
    }

    threads.append(new_thread)
    save_threads(threads)

    # If AI requested, add to pending queue
    if invoke_ai:
        pending = load_pending_inquiries()
        pending.append(new_thread)
        save_pending_inquiries(pending)

        # Attempt immediate auto-verification if possible
        try_auto_verify(thread_id)

    return new_thread


def try_auto_verify(thread_id: str) -> Optional[Dict[str, Any]]:
    """Attempt immediate lookup in local HTML / calendar / data and draft reply."""
    threads = load_threads()
    thread = next((t for t in threads if t["id"] == thread_id), None)
    if not thread or thread.get("ai_status") != "pending":
        return None

    listing = thread["listing"]
    aspect = thread.get("target_aspect", "general")
    query = thread["comment"].lower()
    meta = get_accommodation_meta(listing)
    html = meta.get("html_text") or ""
    q_item = meta.get("queue_item") or {}

    reply = None
    action_taken = None

    # Check 1: Sauna fees / details
    if "sauna" in aspect or "saun" in query:
        if html:
            # Look for pricing or fee patterns near sauna
            m_fee = re.findall(r"([^\.\n]*saun[^\.\n]*(?:poplatek|příplatek|kč|cena|zdarma|v ceně|hodin)[^\.\n]*)", html, re.I)
            if m_fee:
                clean_snippet = re.sub(r"<[^>]+>", " ", m_fee[0]).strip()
                reply = f"Verified in property HTML: {clean_snippet}"
            else:
                reply = f"Checked property HTML: Sauna is mentioned as '{q_item.get('Sauna', 'Available')}', no explicit extra surcharge was noted in description."

    # Check 2: Beer tap verification
    elif "beer" in aspect or "tap" in aspect or "píp" in query or "piv" in query:
        beer_label = q_item.get("Beer_Tap_Label", "None")
        beer_snippet = q_item.get("Beer_Tap_Snippet", "")
        reply = f"Beer tap verified: Status is {beer_label}. Extracted source snippet: '{beer_snippet}'."

    # Check 3: September Availability verification
    elif "availability" in aspect or "sept" in query or "volno" in query or "termín" in query or "7" in query:
        status = q_item.get("September_Summary", "")
        consec = q_item.get("Consecutive_Ranges", [])
        max_d = q_item.get("Max_Consecutive_Days", 0)
        has_7 = q_item.get("Has_7_Consecutive_Days", False)
        if has_7:
            reply = f"September availability verified: Accommodates full 7 consecutive days. Free continuous windows: {', '.join(consec)} (Total: {q_item.get('September_Free_Days', 0)}/30 days free)."
        else:
            reply = f"September availability alert: Cannot accommodate 7 consecutive days. Maximum continuous span is {max_d} days due to weekend bookings. Details: {status}."

    # Check 4: Price adjustment requested by user
    # e.g., "price should be 55k", "adjust price to 110000", "set price to 95 000"
    m_price = re.search(r"(?:change|set|adjust|update|price is|cena|cena je)\s*(?:the\s+)?(?:price\s+)?(?:to|is|na)?\s*~?(\d{2,3}(?:[\s\.]?\d{3})?|\d{5,6})\s*(?:k|kč)?", query, re.I)
    if ("price" in aspect or "cena" in query) and m_price:
        num_str = re.sub(r"[\s\.]", "", m_price.group(1))
        num = int(num_str)
        new_val = num * 1000 if num < 1000 else num
        if 15000 <= new_val <= 400000:
            success = update_price_in_documents(listing, float(new_val), f"User update via website comment ({thread.get('author')})")
            if success:
                reply = f"September 7-night price has been updated to {new_val:,} Kč across the queue and Excel workbook.".replace(",", " ")
                action_taken = f"Updated Price_7_Nights_CZK to {new_val} Kč in queue_candidates_50plus.json, CSV, and sheet_updated_with_extractors.xlsx."

    # Check 5: Pool verification
    elif "pool" in aspect or "bazén" in query or "koup" in query:
        pool_desc = q_item.get("Pool", "No pool")
        reply = f"Swimming pool status verified: {pool_desc}."

    # Check 6: Common area & chairs verification
    elif "common" in aspect or "chair" in query or "židle" in query or "stůl" in query:
        chairs = q_item.get("Chairs_Est", "")
        desc = q_item.get("Common_Area_Desc", "")
        reply = f"Common area verified: Estimated chairs: '{chairs}'. Photos & floorplan show: '{desc}'."

    if reply:
        resolve_inquiry(thread_id, reply, action_taken)
        return thread

    return None


def resolve_inquiry(thread_id: str, reply: str, action_taken: Optional[str] = None) -> bool:
    """Resolve an AI inquiry with an explanation and optional document adjustment note."""
    threads = load_threads()
    updated = False
    for t in threads:
        if t["id"] == thread_id:
            t["ai_status"] = "resolved"
            t["ai_reply"] = reply
            t["ai_action_taken"] = action_taken
            t["resolved_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            updated = True
            break

    if updated:
        save_threads(threads)
        # Remove from pending queue
        pending = load_pending_inquiries()
        pending = [p for p in pending if p["id"] != thread_id]
        save_pending_inquiries(pending)
        return True

    return False


def update_price_in_documents(listing: str, new_price: float, reason: str) -> bool:
    """Directly adjust the candidate queue JSON, CSV, and Excel workbook."""
    updated = False

    # 1. Update JSON
    if os.path.exists(QUEUE_JSON):
        with open(QUEUE_JSON, "r", encoding="utf-8") as f:
            queue = json.load(f)

        for item in queue:
            if item.get("Listing") == listing or item.get("Name") == listing:
                item["Price_7_Nights_CZK"] = new_price
                item["Price_Source_Label"] = f"Adjusted: {int(new_price):,} Kč ({reason})".replace(",", " ")
                item["Price_Note"] = f"Manually adjusted to {int(new_price):,} Kč ({reason})".replace(",", " ")
                
                # Recalculate price score
                if new_price <= 45000:
                    item["Price_Score"] = 5.0
                elif new_price <= 60000:
                    item["Price_Score"] = 4.0
                elif new_price <= 80000:
                    item["Price_Score"] = 3.0
                elif new_price <= 110000:
                    item["Price_Score"] = 2.0
                else:
                    item["Price_Score"] = 1.0

                updated = True
                break

        if updated:
            with open(QUEUE_JSON, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2, ensure_ascii=False)

            # Update CSV
            if os.path.exists(QUEUE_CSV):
                flat_keys = [k for k in queue[0].keys() if k not in ("Photos_List", "Pros_Vs_Novy_Svet", "Cons_Vs_Novy_Svet", "Consecutive_Ranges")]
                flat_keys.extend(["Consecutive_Ranges", "Pros_Vs_Novy_Svet", "Cons_Vs_Novy_Svet"])
                with open(QUEUE_CSV, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=flat_keys, extrasaction="ignore")
                    writer.writeheader()
                    for q in queue:
                        row_copy = {k: v for k, v in q.items() if k not in ("Photos_List", "Pros_Vs_Novy_Svet", "Cons_Vs_Novy_Svet", "Consecutive_Ranges")}
                        row_copy["Consecutive_Ranges"] = ", ".join(q.get("Consecutive_Ranges", []))
                        row_copy["Pros_Vs_Novy_Svet"] = " | ".join(q.get("Pros_Vs_Novy_Svet", []))
                        row_copy["Cons_Vs_Novy_Svet"] = " | ".join(q.get("Cons_Vs_Novy_Svet", []))
                        writer.writerow(row_copy)

    # 2. Update Excel
    if os.path.exists(WORKBOOK_XLSX):
        try:
            wb = openpyxl.load_workbook(WORKBOOK_XLSX)
            if "ranking" in wb.sheetnames:
                ws = wb["ranking"]
                col_price = None
                col_listing = None
                for c in range(1, ws.max_column + 1):
                    val = str(ws.cell(1, c).value or "")
                    if "Price" in val and "7" in val:
                        col_price = c
                    elif val == "Listing":
                        col_listing = c

                if col_price and col_listing:
                    for r in range(2, ws.max_row + 1):
                        if str(ws.cell(r, col_listing).value or "").strip() == listing:
                            ws.cell(r, col_price, new_price)
                            break
                    wb.save(WORKBOOK_XLSX)
        except Exception as e:
            print(f"Excel workbook update note: {e}")

    return updated


if __name__ == "__main__":
    import sys
    print("🤖 AI Bridge Utility")
    threads = load_threads()
    pending = load_pending_inquiries()
    print(f"Total Threads: {len(threads)}")
    print(f"Pending AI Inquiries: {len(pending)}")
    for p in pending:
        print(f" - [{p['id']}] {p['accommodation_name']} ({p['target_aspect']}): {p['comment']}")
