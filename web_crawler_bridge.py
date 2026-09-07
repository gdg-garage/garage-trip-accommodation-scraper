import argparse
import datetime
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

DEFAULT_INPUT = "urls_whole_object.txt"
DEFAULT_OUTPUT_DIR = "html"
DEFAULT_DAILY_LIMIT = 50
DEFAULT_LEDGER_FILE = ".daily_crawl_ledger.json"
PORT = 8765


def url_to_filename(url: str) -> str:
    p = urllib.parse.urlparse(url)
    path = p.path.strip("/")
    if path.endswith(".php"):
        path = path[:-4]
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", path)
    if not slug:
        slug = hashlib.md5(url.encode("utf-8")).hexdigest()
    return f"{slug}.html"


def load_urls(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]


class DailyQuotaTracker:
    def __init__(self, ledger_file=DEFAULT_LEDGER_FILE, daily_limit=DEFAULT_DAILY_LIMIT):
        self.ledger_file = ledger_file
        self.daily_limit = daily_limit
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.ledger_file):
            try:
                with open(self.ledger_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self):
        try:
            with open(self.ledger_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving quota ledger: {e}", file=sys.stderr)

    def get_today_str(self):
        return datetime.date.today().isoformat()

    def get_today_count(self):
        today = self.get_today_str()
        return self.data.get(today, 0)

    def can_download(self):
        return self.get_today_count() < self.daily_limit

    def record_download(self):
        today = self.get_today_str()
        self.data[today] = self.data.get(today, 0) + 1
        self._save()
        return self.data[today]


class CrawlerState:
    def __init__(self, input_file, output_dir, daily_limit=DEFAULT_DAILY_LIMIT):
        self.input_file = input_file
        self.output_dir = output_dir
        self.urls = load_urls(input_file)
        self.quota = DailyQuotaTracker(daily_limit=daily_limit)
        os.makedirs(output_dir, exist_ok=True)
        self._seed_existing_downloads_if_empty()

    def _seed_existing_downloads_if_empty(self):
        # If ledger is empty, seed today's count based on file modification times
        if not self.quota.data:
            today = datetime.date.today()
            today_count = 0
            if os.path.exists(self.output_dir):
                for f in os.listdir(self.output_dir):
                    if f.endswith(".html"):
                        fp = os.path.join(self.output_dir, f)
                        if datetime.date.fromtimestamp(os.path.getmtime(fp)) == today:
                            today_count += 1
            if today_count > 0:
                self.quota.data[today.isoformat()] = today_count
                self.quota._save()

    def get_status(self):
        self.urls = load_urls(self.input_file)
        cached = []
        pending = []
        for u in self.urls:
            fn = url_to_filename(u)
            fp = os.path.join(self.output_dir, fn)
            is_valid_cache = False
            if os.path.exists(fp) and os.path.getsize(fp) > 15000:
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        snippet = f.read(1200)
                    if "Just a moment" not in snippet and "Security" not in snippet and "Provádění bezpečnostního" not in snippet:
                        is_valid_cache = True
                except Exception:
                    pass

            if is_valid_cache:
                cached.append(u)
            else:
                pending.append(u)

        # Randomly shuffle pending URLs so requests are non-sequential
        random.shuffle(pending)

        today_count = self.quota.get_today_count()
        can_download = self.quota.can_download()
        remaining_today = max(0, self.quota.daily_limit - today_count)

        return {
            "total": len(self.urls),
            "cached": len(cached),
            "pending": len(pending),
            "pending_urls": pending[:100] if can_download else [],
            "output_dir": self.output_dir,
            "today_date": self.quota.get_today_str(),
            "today_downloads": today_count,
            "daily_limit": self.quota.daily_limit,
            "remaining_today": remaining_today,
            "daily_limit_reached": not can_download,
        }

    def save_page(self, url, html):
        if not self.quota.can_download():
            today = self.quota.get_today_str()
            return None, f"Daily limit ({self.quota.daily_limit}/day) reached for {today}. Cannot save."

        fn = url_to_filename(url)
        fp = os.path.join(self.output_dir, fn)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(html)
        
        today_total = self.quota.record_download()
        return fn, len(html), today_total



state = None


class BridgeHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS so browser on e-chalupy.cz can talk to localhost
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(state.get_status()).encode("utf-8"))
            ret        # Serve Dashboard
        status = state.get_status()
        daily_badge_color = "#ef4444" if status['daily_limit_reached'] else "#38bdf8"
        html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <title>🏡 e-chalupy Native Browser Bridge</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 2rem; }}
        .container {{ max-width: 950px; margin: 0 auto; background: #1e293b; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }}
        h1 {{ margin-top: 0; color: #38bdf8; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-weight: bold; background: #334155; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 1.5rem 0; }}
        .stat-card {{ background: #0f172a; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #334155; }}
        .stat-num {{ font-size: 2rem; font-weight: bold; color: #38bdf8; }}
        .stat-label {{ color: #94a3b8; font-size: 0.85rem; margin-top: 4px; }}
        .bookmarklet-box {{ background: #0f172a; border: 1px solid #38bdf8; padding: 1.2rem; border-radius: 8px; margin: 1.5rem 0; }}
        .btn {{ display: inline-block; background: #38bdf8; color: #0f172a; font-weight: bold; padding: 10px 20px; border-radius: 8px; text-decoration: none; cursor: pointer; border: none; font-size: 1rem; }}
        pre {{ background: #020617; padding: 1rem; border-radius: 6px; overflow-x: auto; color: #a5f3fc; font-size: 0.85rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🏡 e-chalupy Native Browser Bridge</h1>
        <p>This bridge lets your normal, trusted Chrome browser download cottage HTML pages in the background without triggering CAPTCHAs.</p>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-num" id="stat-total">{status['total']}</div>
                <div class="stat-label">Total Properties</div>
            </div>
            <div class="stat-card">
                <div class="stat-num" id="stat-cached" style="color: #4ade80;">{status['cached']}</div>
                <div class="stat-label">All-Time Saved</div>
            </div>
            <div class="stat-card">
                <div class="stat-num" id="stat-today" style="color: {daily_badge_color};">{status['today_downloads']}/{status['daily_limit']}</div>
                <div class="stat-label">Today ({status['today_date']})</div>
            </div>
            <div class="stat-card">
                <div class="stat-num" id="stat-pending" style="color: #facc15;">{status['pending']}</div>
                <div class="stat-label">Remaining in Queue</div>
            </div>
        </div>

        <div class="bookmarklet-box">
            <h3>⚡ 1-Click Native Collector (Strict 50/Day Backend Limit)</h3>
            <p>1. Open <a href="https://www.e-chalupy.cz/" target="_blank" style="color: #38bdf8; font-weight: bold;">https://www.e-chalupy.cz</a> in another tab.</p>
            <p>2. Open Developer Tools (<code>Cmd + Option + I</code>), go to <strong>Console</strong>, paste the code below, and press <strong>Enter</strong>:</p>
            <pre>fetch('http://localhost:{PORT}/crawler.js').then(r=>r.text()).then(eval);</pre>
            <p>Your browser will fetch each cottage smoothly with natural delays (30s – 5.5 min) and stop automatically when today's 50/day limit is reached.</p>
        </div>
    </div>

    <script>
        setInterval(async () => {{
            try {{
                const r = await fetch('/api/status');
                const d = await r.json();
                document.getElementById('stat-total').innerText = d.total;
                document.getElementById('stat-cached').innerText = d.cached;
                document.getElementById('stat-today').innerText = d.today_downloads + '/' + d.daily_limit;
                document.getElementById('stat-pending').innerText = d.pending;
            }} catch(e) {{}}
        }}, 2000);
    </script>
</body>
</html>"""
        if self.path == "/crawler.js":
            # Return ultra-slow crawler script with strict 50-max daily limit
            crawler_js = f"""
(async function() {{
    console.log("%c🏡 e-chalupy Ultra-Slow Native Bridge (Strict 50/day backend limit)...", "color: #38bdf8; font-size: 16px; font-weight: bold;");
    const BRIDGE = "http://localhost:{PORT}";
    
    while (true) {{
        let status;
        try {{
            const sRes = await fetch(BRIDGE + "/api/status");
            status = await sRes.json();
        }} catch(e) {{
            console.error("Bridge server unreachable:", e);
            break;
        }}
        
        if (status.daily_limit_reached) {{
            console.log(`%c🛑 Daily limit (${{status.daily_limit}}/day) reached for ${{status.today_date}}. Today's total: ${{status.today_downloads}}/${{status.daily_limit}}. Crawler paused until tomorrow!`, "color: #f59e0b; font-size: 14px; font-weight: bold;");
            break;
        }}
        
        if (status.pending === 0 || status.pending_urls.length === 0) {{
            console.log("%c🎉 All properties downloaded!", "color: #4ade80; font-size: 16px; font-weight: bold;");
            break;
        }}
        
        const url = status.pending_urls[0];
        console.log(`%c[Today: ${{status.today_downloads + 1}}/${{status.daily_limit}}] Fetching: ${{url}}`, "color: #38bdf8; font-weight: bold;");
        
        try {{
            const res = await fetch(url, {{ credentials: "include" }});
            const html = await res.text();
            
            if (html.includes("Just a moment") || html.length < 15000) {{
                console.warn("⚠️ Challenge detected. Cooling down for 3 minutes...");
                await new Promise(r => setTimeout(r, 180000));
                continue;
            }}
            
            // Send back to localhost
            const saveRes = await fetch(BRIDGE + "/api/save", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ url: url, html: html }})
            }});
            
            const saveJson = await saveRes.json();
            if (saveJson.success) {{
                console.log(`%c  ✓ Saved (${{html.length.toLocaleString()}} bytes) [Today: ${{saveJson.today_total}}/${{saveJson.daily_limit}}]`, "color: #4ade80;");
            }} else {{
                console.warn("Backend save response:", saveJson.error);
                if (saveJson.error && saveJson.error.includes("Daily limit")) {{
                    break;
                }}
            }}
        }} catch(err) {{
            console.error("Error fetching " + url, err);
        }}
        
        // Ultra-slow polite sleep between 30 seconds and 5.5 minutes (30s to 330s)
        const sleepMs = 30000 + Math.random() * 300000;
        const sleepSec = (sleepMs / 1000).toFixed(0);
        const sleepMin = (sleepMs / 60000).toFixed(1);
        const nextTime = new Date(Date.now() + sleepMs).toLocaleTimeString();
        console.log(`  ⏳ Sleeping for ${{sleepSec}}s (${{sleepMin}} min). Next request at ~${{nextTime}}...\\n`);
        await new Promise(r => setTimeout(r, sleepMs));
    }}
}})();
"""
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            self.wfile.write(crawler_js.encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        if self.path == "/api/save":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            url = data.get("url")
            html_text = data.get("html", "")
            
            res = state.save_page(url, html_text)
            if not res or res[0] is None:
                err_msg = res[1] if res else "Failed to save page"
                print(f"⚠️ Rejecting save: {err_msg}", flush=True)
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": err_msg}).encode("utf-8"))
                return

            filename, size, today_total = res
            print(f"✓ Saved {filename} ({size:,} bytes) from {url} [Today's Total: {today_total}/{state.quota.daily_limit}]", flush=True)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "file": filename,
                "size": size,
                "today_total": today_total,
                "daily_limit": state.quota.daily_limit
            }).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    global state
    parser = argparse.ArgumentParser(description="Native Browser Bridge for e-chalupy.cz")
    parser.add_argument("--input", "-i", default=DEFAULT_INPUT, help=f"Input URL file (default: {DEFAULT_INPUT})")
    parser.add_argument("--output-dir", "-o", default=DEFAULT_OUTPUT_DIR, help=f"Output HTML directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--port", "-p", type=int, default=PORT, help=f"Server port (default: {PORT})")
    parser.add_argument("--daily-limit", "-l", type=int, default=DEFAULT_DAILY_LIMIT, help=f"Strict max downloads per day (default: {DEFAULT_DAILY_LIMIT})")
    args = parser.parse_args()

    state = CrawlerState(args.input, args.output_dir, daily_limit=args.daily_limit)
    server = HTTPServer(("127.0.0.1", args.port), BridgeHandler)
    
    print(f"============================================================")
    print(f" 🏡 Native Browser Bridge Server Running (Strict Daily Limit)")
    print(f"============================================================")
    print(f"Dashboard URL:      http://localhost:{args.port}")
    print(f"Source URLs:        {args.input} ({len(state.urls)} properties)")
    print(f"Output Directory:   {args.output_dir}/")
    print(f"Daily Limit:        {args.daily_limit} max per day (Today's count: {state.quota.get_today_count()}/{args.daily_limit})")
    print(f"============================================================\n", flush=True)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBridge server stopped.")


if __name__ == "__main__":
    main()
