#!/usr/bin/env python3
"""
Review Server for Garage Trip Accommodations.
A lightweight zero-dependency web server for reviewing candidates, photos,
pricing (7 nights), September availability, beer taps, collecting team feedback,
and providing a bidirectional AI Bridge where team members can comment on any
aspect or accommodation and invoke Antigravity AI to verify facts or adjust documents.
Usage:
    python3 serve.py [port]
"""

import csv
import json
import mimetypes
import os
import re
import sys
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

import ai_bridge

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
DATA_FILE = "queue_candidates_50plus.json"
COMMENTS_FILE = "data/user_comments.json"


def load_candidates():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_legacy_comments():
    if os.path.exists(COMMENTS_FILE):
        try:
            with open(COMMENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_legacy_comments(comments):
    os.makedirs(os.path.dirname(COMMENTS_FILE), exist_ok=True)
    with open(COMMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(comments, f, indent=2, ensure_ascii=False)


class ReviewHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Root: serve web/index.html
        if path in ("", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open("web/index.html", "rb") as f:
                self.wfile.write(f.read())
            return

        # API: get candidates with feedback and active thread counts
        if path == "/api/data":
            data = load_candidates()
            legacy = load_legacy_comments()
            threads = ai_bridge.load_threads()

            # Group threads by listing
            threads_by_listing = {}
            for t in threads:
                lst = t.get("listing")
                if lst not in threads_by_listing:
                    threads_by_listing[lst] = []
                threads_by_listing[lst].append(t)

            for item in data:
                listing = item.get("Listing")
                item["team_feedback"] = legacy.get(listing, {"comment": "", "vote": "", "updated_at": ""})
                item_threads = threads_by_listing.get(listing, [])
                item["threads"] = item_threads
                item["threads_count"] = len(item_threads)
                item["pending_ai_count"] = len([t for t in item_threads if t.get("ai_status") == "pending"])

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        # API: get comments threads
        if path == "/api/comments/threads":
            threads = ai_bridge.load_threads()
            listing_filter = query.get("listing", [None])[0]
            aspect_filter = query.get("target", [None])[0]

            if listing_filter:
                threads = [t for t in threads if t.get("listing") == listing_filter]
            if aspect_filter:
                threads = [t for t in threads if t.get("target_aspect") == aspect_filter]

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(threads, ensure_ascii=False).encode("utf-8"))
            return

        # API: get pending AI inquiries
        if path == "/api/ai/pending":
            pending = ai_bridge.load_pending_inquiries()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(pending, ensure_ascii=False).encode("utf-8"))
            return

        # API: export comments as CSV
        if path == "/api/export_comments":
            legacy = load_legacy_comments()
            threads = ai_bridge.load_threads()
            candidates = {c["Listing"]: c for c in load_candidates()}

            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=\"garage_trip_comments.csv\"")
            self.end_headers()

            lines = ["Type,Listing,Accommodation,Target_Aspect,Author,Vote_Or_Status,Comment,AI_Reply,Action_Taken,Created_At\n"]
            
            # Legacy votes & comments
            for listing, fb in legacy.items():
                name = candidates.get(listing, {}).get("Name", listing).replace('"', '""')
                vote = fb.get("vote", "")
                comment = fb.get("comment", "").replace('"', '""')
                updated_at = fb.get("updated_at", "")
                lines.append(f'"vote_summary","{listing}","{name}","general","{fb.get("author","Team")}","{vote}","{comment}","","","{updated_at}"\n')

            # Threaded aspect comments and AI replies
            for t in threads:
                listing = t.get("listing", "")
                name = t.get("accommodation_name", "").replace('"', '""')
                aspect = t.get("target_aspect", "general")
                author = t.get("author", "").replace('"', '""')
                status = t.get("ai_status") or "normal"
                comment = t.get("comment", "").replace('"', '""')
                reply = (t.get("ai_reply") or "").replace('"', '""')
                action = (t.get("ai_action_taken") or "").replace('"', '""')
                created = t.get("created_at", "")
                lines.append(f'"aspect_thread","{listing}","{name}","{aspect}","{author}","{status}","{comment}","{reply}","{action}","{created}"\n')

            self.wfile.write("".join(lines).encode("utf-8"))
            return

        # API: get debate arena results
        if path == "/api/debate" or path == "/api/simulation_runs":
            runs_file = "data/simulation_runs.json"
            debate_file = "data/debate_arena_results.json"
            
            selected_run_id = query.get("run", [None])[0]
            
            if os.path.exists(runs_file):
                try:
                    with open(runs_file, "r", encoding="utf-8") as f:
                        bundle = json.load(f)
                    
                    if path == "/api/simulation_runs":
                        data = bundle
                    elif selected_run_id and selected_run_id in bundle.get("runs", {}):
                        data = bundle["runs"][selected_run_id]
                        data["available_runs"] = bundle.get("available_runs", [])
                        data["active_run_id"] = selected_run_id
                    else:
                        active_id = bundle.get("active_run_id", "run_1")
                        data = bundle.get("runs", {}).get(active_id, {})
                        data["available_runs"] = bundle.get("available_runs", [])
                        data["active_run_id"] = active_id
                except Exception as e:
                    data = {"error": f"Failed to load simulation runs: {e}"}
            elif os.path.exists(debate_file):
                try:
                    with open(debate_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    data = {"error": f"Failed to load debate results: {e}"}
            else:
                data = {"status": "not_run_yet", "message": "Debate arena has not been run yet."}

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        # API: get cross-examination summary
        if path == "/api/cross-examinations":
            summary_file = "data/cross_examinations_summary.json"
            data = []
            if os.path.exists(summary_file):
                try:
                    with open(summary_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    data = []
            
            # Check individual listing query param
            listing_filter = query.get("listing", [None])[0]
            if listing_filter:
                slug = re.sub(r"[^\w-]", "_", listing_filter).lower()
                detail_file = f"data/cross_examinations/{slug}.json"
                if os.path.exists(detail_file):
                    with open(detail_file, "r", encoding="utf-8") as f:
                        detail = json.load(f)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(detail, ensure_ascii=False).encode("utf-8"))
                    return

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        # Serve local images from images/ or booking_images/
        clean_path = urllib.parse.unquote(path.lstrip("/"))
        if os.path.exists(clean_path) and os.path.isfile(clean_path):
            mime_type, _ = mimetypes.guess_type(clean_path)
            self.send_response(200)
            self.send_header("Content-Type", mime_type or "application/octet-stream")
            self.send_header("Content-Length", str(os.path.getsize(clean_path)))
            self.end_headers()
            with open(clean_path, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_error(404, "File Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            payload = json.loads(body) if body else {}
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": f"Invalid JSON: {e}"}).encode("utf-8"))
            return

        # 1. Threaded Aspect / Accommodation Comment & AI Bridge
        if path == "/api/comments/thread":
            listing = payload.get("listing")
            target_aspect = payload.get("target_aspect", "general")
            author = payload.get("author", "Team Member")
            comment = payload.get("comment", "").strip()
            invoke_ai = bool(payload.get("invoke_ai", False))

            if not listing or not comment:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Missing listing or comment"}).encode("utf-8"))
                return

            new_thread = ai_bridge.add_comment_thread(
                listing=listing,
                target_aspect=target_aspect,
                author=author,
                comment=comment,
                invoke_ai=invoke_ai
            )

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "thread": new_thread}, ensure_ascii=False).encode("utf-8"))
            return

        # 2. AI Bridge Resolve
        if path == "/api/ai/resolve":
            thread_id = payload.get("thread_id")
            reply = payload.get("reply", "").strip()
            action_taken = payload.get("action_taken")

            if not thread_id or not reply:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Missing thread_id or reply"}).encode("utf-8"))
                return

            ok = ai_bridge.resolve_inquiry(thread_id, reply, action_taken)
            self.send_response(200 if ok else 404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success" if ok else "not_found"}).encode("utf-8"))
            return

        # 3. AI Bridge Document Adjustment
        if path == "/api/ai/update_document":
            listing = payload.get("listing")
            price = payload.get("price")
            reason = payload.get("reason", "Adjusted via AI Bridge")

            if not listing or price is None:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Missing listing or price"}).encode("utf-8"))
                return

            ok = ai_bridge.update_price_in_documents(listing, float(price), reason)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success" if ok else "failed"}).encode("utf-8"))
            return

        # 4. Legacy vote & quick comment
        if path == "/api/comment":
            listing = payload.get("listing")
            comment = payload.get("comment", "").strip()
            vote = payload.get("vote", "").strip()
            author = payload.get("author", "Team Member").strip()

            if listing:
                legacy = load_legacy_comments()
                import datetime
                legacy[listing] = {
                    "author": author,
                    "vote": vote,
                    "comment": comment,
                    "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                save_legacy_comments(legacy)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "listing": listing}).encode("utf-8"))
                return

        self.send_error(404, "Unknown endpoint")


def run():
    os.makedirs("web", exist_ok=True)
    os.makedirs("data/ai_bridge", exist_ok=True)
    server_address = ("", PORT)
    httpd = ThreadingHTTPServer(server_address, ReviewHandler)
    print(f"🚀 Garage Trip Review Server + AI Bridge running at:")
    print(f"   👉 http://jarvis.lan:{PORT}")
    print(f"   👉 http://localhost:{PORT}")
    print(f"📂 Candidates: {DATA_FILE}")
    print(f"💬 Threads & Bridge Queue: {ai_bridge.THREADS_FILE}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
