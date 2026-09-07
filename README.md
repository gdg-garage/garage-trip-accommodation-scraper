# 🏡 Garage Trip Accommodation Scraper & AI Ranker

A distributed, decoupled web scraping, offline DOM parsing, and LLM-powered ranking pipeline designed for discovering, filtering, and evaluating holiday cottages and chalets (*chaty a chalupy*) on [e-chalupy.cz](https://www.e-chalupy.cz).

Specially engineered for organizing **large group weekend retreats** (25–40 people), such as board game weekends, LAN gaming parties, and developer offsites.

---

## 💡 Concept & Motivation

### The Problem: Finding Cottages for 25–40 Friends
Planning a weekend getaway for 30 friends is notoriously tedious on traditional holiday rental websites:
- **Search filters are too crude**: Listing filters can tell you total bed count, but they don't tell you whether a cottage has a massive common room (*společenská místnost*) with enough tables and chairs for everyone to sit together, or if the beds are cramped into 10-person dormitories.
- **Hidden Gotchas**: Many large properties are actually guesthouses (*penzióny*) where the owner lives on-site, or multiple separate apartments in one building without a central gathering space.
- **Complex Pricing Models**: Pricing is listed in various formats (per week, per night, per person, seasonal vs. off-season), making manual price comparison difficult.
- **Subjective Suitability**: Deciding if a cottage is great for desktop PC gaming (power sockets, stable Wi-Fi) or tabletop board games requires reading between the lines of long Czech descriptions and guest reviews.

### The Solution: Hybrid Heuristic + LLM Pipeline
This project solves the challenge through a two-tier evaluation strategy:
1. **Rule-Based Heuristic Normalization**: Filters out hundreds of non-viable properties automatically by parsing capacities, bed-to-room ratios, distances to restaurants and forests, price caps, and required amenities (Wi-Fi, parking, grill).
2. **AI-Powered Evaluation with Gemma 2**: Sends candidate cottages (structured specs + plain text description + guest reviews + photos) to a local LLM via Ollama (`gemma2`) to evaluate layout comfort, table space, privacy (owner on-site detection), and group suitability, returning structured scores with **description first**.

---

## 🧩 Architectural Philosophy: Why 5 Decoupled Stages?

To enable **team collaboration** and **prevent server blocking**, the workflow is decoupled into 5 independent stages:

```
[ e-chalupy.cz search ] 
        |
        v  Step 1: scrape_links.py (make links)
   [ urls.txt ]
        |
        +-------------------------+-------------------------+
        | (Worker Shard 0)        | (Worker Shard 1)        | (Worker Shard 2)
        v                         v                         v
 download_html.py          download_html.py          download_html.py
   (--shard-id 0)            (--shard-id 1)            (--shard-id 2)
        |                         |                         |
        +-------------------------+-------------------------+
                                  |
                                  v
                            [ html/*.html ]
                                  |
                 +----------------+----------------+
                 |                                 |
                 v Step 4: parse_dom.py            v Step 3: download_images.py
           (Offline DOM)                     (Distributed Shards)
                 |                                 |
                 v                                 v
        [ properties.json ]                    [ imgs/*.jpg ]
        [ out.csv / out.json ]                     |
                 |                                 |
                 +----------------+----------------+
                                  |
                                  v  Step 5: rank.py (Ollama + gemma2)
                           [ ratings.json ]
                                  |
                                  v  Step 6: merge_ratings.py
                          [ out-rated.csv ]
```

### Why Decouple & Distribute?
1. **Polite & Anti-Blocking**: Instead of hammering `e-chalupy.cz` from a single IP, link discovery is isolated into a tiny lightweight query. The heavy HTML/image downloads can be partitioned among multiple team members across different networks using **worker sharding** (`--total-shards N --shard-id I`) with built-in delays, random jitter, and retry backoffs.
2. **Instant Offline Iteration**: Once HTML files are saved locally into `html/`, all DOM parsing, regex adjustments, heuristic tweaks, and price recalculations run **100% offline in milliseconds** without making a single network request to the live website.
3. **Resilience & Resumption**: Every downloading stage automatically checks if a file already exists on disk and skips it. If a network connection drops or a teammate is interrupted, restarting picks up right where it left off.
4. **Reproducible AI Experimentation**: Parsed structured data is saved to `out.json`, allowing team members to test different LLM models (`gemma2`, `llama3.1`, `llava`), prompt versions (`--prompt-version v4`), and multimodal visual prompts with `--dry-run` and incremental caching in `ratings.json`.

---

## 📌 5-Stage Pipeline Overview

1. **Link Extractor (`scrape_links.py`)**: Crawls search index pages across regions and outputs `urls.txt`.
2. **Distributed HTML Downloader (`download_html.py`)**: Downloads raw HTML pages into `html/` with polite rate-limiting, jitter, automatic retry backoff, and worker sharding.
3. **Image Downloader Tools**:
   - **Single Property Image Downloader (`download_property_images.py` & `extract_property_images.py`)**: Extracts full-resolution gallery photo URLs for a specific property and downloads them into `images/<slug>/` with graceful timeouts, exponential retries, polite delays, and image verification without triggering captchas.
   - **Distributed Bulk Image Downloader (`download_images.py`)**: Downloads property photos across all properties with worker sharding and rate-limiting.
4. **Offline DOM Parser & Heuristic Filter (`parse_dom.py`)**: Parses local HTML files offline, normalizes prices and distances, applies capacity/amenity filters, and produces `properties.json`, `out.csv`, and `out.json`.
5. **Gemma-Powered LLM Analyzer (`rank.py`)**: Evaluates candidate cottages with local Ollama LLMs (defaulting to newest **`gemma2`**), returning **description first**, suitability scores, owner presence detection, and constraint reasoning.


## 📦 Export Dataset & Methodology

### Current Candidate Dataset (1,199 Properties)
- **Export Date**: **`2026-08-29`**
- **Query Scope**: 25+ person accommodations (`persons=25`), exported in two comprehensive categories to ensure zero missed listings:
  1. **Cottages & Chalets (*Chaty a chalupy*)**: [`raw_regions/search_25_plus_cottages.mhtml`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/raw_regions/search_25_plus_cottages.mhtml) (**771 links**)
  2. **Other Types (*Apartmány, penziony, roubenky, etc.*)**: [`raw_regions/search_25_plus_others.mhtml`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/raw_regions/search_25_plus_others.mhtml) (**899 links**)
- **Overlap & Deduplication**: 471 properties appear in both categories; deduplicating gives **1,199 total unique accommodations**.
- **Extracted URLs**: [`urls.txt`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/urls.txt) (**1,199 lines**)

### How to Extract & Reproduce
```bash
python3 extract_links.py raw_regions/search_25_plus_cottages.mhtml raw_regions/search_25_plus_others.mhtml --output urls.txt
```
This extracts, normalizes, and deduplicates all unique accommodation URLs into [`urls.txt`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/urls.txt).



---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) running locally or on a LAN server
- Pull the newest Gemma model:
  ```bash
  ollama pull gemma2
  # Or for multimodal visual evaluation with images:
  ollama pull llava
  ```

### 2. Installation
```bash
git clone https://github.com/gdg-garage/garage-trip-accommodation-scraper.git
cd garage-trip-accommodation-scraper
pip install -r requirements.txt
```


---

## 👥 Distributed Team Collaboration Guide

When scraping hundreds of properties, multiple team members can share the download workload to minimize requests to `e-chalupy.cz` and prevent rate-limiting:

### 1. Extract Links (1 person runs this)
```bash
make links
# Generates urls.txt
```
Share `urls.txt` with your team.

### 2. Distribute HTML Downloads (e.g. across 3 teammates)
- **Teammate 1**:
  ```bash
  python3 download_html.py --total-shards 3 --shard-id 0
  ```
- **Teammate 2**:
  ```bash
  python3 download_html.py --total-shards 3 --shard-id 1
  ```
- **Teammate 3**:
  ```bash
  python3 download_html.py --total-shards 3 --shard-id 2
  ```

Teammates simply zip and share their `html/` folders (e.g. `tar -czvf html_shard0.tar.gz html/`), and merge all `.html` files into a single `html/` directory!

### 3. Distribute Image Downloads (optional)
Similarly, image downloads can be sharded:
```bash
python3 download_images.py --total-shards 3 --shard-id 0
```

### 4. Parse Offline & Filter (runs 100% locally)
Once HTML files are in `html/`, run the DOM parser without any network access:
```bash
make parse
```
This extracts structured records into `properties.json`, `out.csv`, and `out.json`.

### 5. Rank with Ollama (Gemma 2)
```bash
make rank
# Or with specific parameters:
python3 rank.py --model gemma2 --prompt-version v4
```

### 6. Merge Ratings & Export
```bash
make merge
# Creates out-rated.csv with all AI & human ratings
```

---

## 📖 CLI Reference

### 1. `scrape_links.py`
| Argument | Default | Description |
|---|---|---|
| `--capacity` | `18` | Minimum capacity query parameter. |
| `--rooms` | `2` | Minimum room count query parameter. |
| `--max-region` | `100` | Scan region IDs from 1 to `max-region`. |
| `--output`, `-o` | `urls.txt` | Output file for extracted URLs. |
| `--delay` | `0.5` | Polite delay between region requests in seconds. |
| `--append` | `False` | Append and merge with existing output file. |

### 2. `download_html.py`
| Argument | Default | Description |
|---|---|---|
| `--input`, `-i` | `urls.txt` | Input URLs list. |
| `--output-dir`, `-o` | `html` | Destination directory for `.html` files. |
| `--total-shards`, `-n` | `1` | Total number of distributed worker shards. |
| `--shard-id`, `-s` | `0` | Zero-indexed shard ID (`0..total_shards-1`). |
| `--delay` | `0.5` | Base delay between HTTP requests in seconds. |
| `--jitter` | `0.3` | Random jitter added to delay. |
| `--timeout` | `15` | Request timeout in seconds. |
| `--force` | `False` | Overwrite existing cached `.html` files. |
| `--cf-clearance` | `None` | Manual Cloudflare `cf_clearance` cookie token (or `CF_CLEARANCE` env var). |
| `--user-agent` | `None` | User-Agent matching the `cf_clearance` token (or `USER_AGENT` env var). |
| `--session-file` | `.cf_session.json` | Path to session cache file. |
| `--no-browser` | `False` | Pure HTTP mode (skip launching Playwright browser). |
| `--headless` | `False` | Run browser in headless mode during Cloudflare solving. |
| `--force-auth` | `False` | Force re-running browser solver even if session cache exists. |

#### Cloudflare & Remote Server Usage:
- **Local Machine (Auto Solver):**
  ```bash
  python3 download_html.py --total-shards 4 --shard-id 0
  ```
  Automatically solves Cloudflare Turnstile in ~2 seconds, saves the session to `.cf_session.json`, and downloads rapidly via `curl_cffi`.
- **Remote / Headless Server (No GUI / No Playwright):**
  Share the generated `.cf_session.json` file to the remote server, or pass the token directly:
  ```bash
  CF_CLEARANCE="<token>" USER_AGENT="<user_agent>" python3 download_html.py --no-browser -n 4 -s 1
  ```

### 3. Image Downloaders

#### Single-Property Gallery Extractor (`extract_property_images.py`)
Extracts full-resolution gallery photos specifically belonging to a single property (excluding recommendation cards and similar properties):
```bash
python3 extract_property_images.py o358
# Or save to JSON manifest:
python3 extract_property_images.py o358 -o hribek_images.json
```

#### Single-Property Image Downloader (`download_property_images.py`)
Downloads gallery photos with graceful timeouts, exponential retries, polite pacing, and image validation:
```bash
python3 download_property_images.py o358
# Or download a sample with custom delay:
python3 download_property_images.py o358 --limit 5 --delay 0.5
```
| Argument | Default | Description |
|---|---|---|
| `property` | *Required* | HTML file path, property slug, or ID (e.g. `o358` or `html/benecko-...html`). |
| `--output-dir`, `-o` | `images/<slug>/` | Destination directory for downloaded photos. |
| `--limit`, `-l` | `None` | Max images to download (useful for quick previews/testing). |
| `--delay` | `0.8` | Base delay between image downloads in seconds. |
| `--jitter` | `0.4` | Random jitter added to delay. |
| `--timeout`, `-t` | `15` | Request timeout per image in seconds. |
| `--max-retries` | `3` | Max retry attempts with exponential backoff on transient errors. |
| `--force`, `-f` | `False` | Overwrite existing cached images instead of skipping. |

#### Distributed Bulk Image Downloader (`download_images.py`)
| Argument | Default | Description |
|---|---|---|
| `--html-dir`, `-d` | `html` | Directory with downloaded HTML pages. |
| `--input-json`, `-j` | `None` | Alternative input JSON with image URLs. |
| `--output-dir`, `-o` | `imgs` | Destination images directory. |
| `--total-shards`, `-n` | `1` | Total number of worker shards. |
| `--shard-id`, `-s` | `0` | Zero-indexed shard ID. |
| `--delay` | `0.2` | Polite delay between image downloads. |

### 4. `web_crawler_bridge.py`
Local bridge server for slow, human-like background HTML crawling through your trusted Chrome browser:
```bash
python3 web_crawler_bridge.py --daily-limit 50
```
- Dashboard at `http://localhost:8765`
- Enforces strict persistent daily limit (50/day in `.daily_crawl_ledger.json`)
- Randomly shuffles unprocessed queue to avoid regional suspicion
- Polite 30s – 5.5 min delays between pages

### 5. `parse_dom.py`
| Argument | Default | Description |
|---|---|---|
| `--html-dir`, `-d` | `html` | Directory of local HTML files to parse. |
| `--output-properties` | `properties.json`| Raw extracted properties JSON. |
| `--output-csv`, `-c` | `out.csv` | Enriched & filtered CSV table. |
| `--output-json`, `-j` | `out.json` | Candidate accommodations JSON. |
| `--min-beds` | `22` | Minimum required bed capacity. |
| `--max-beds` | `42` | Maximum capacity limit. |
| `--min-rooms` | `7` | Minimum bedroom count. |
| `--max-price` | `15000` | Maximum daily rental cost in CZK. |
| `--max-restaurant-dist`| `1500` | Max distance to restaurant in meters. |

### 6. `rank.py` (Legacy Single-Pass Evaluator)
| Argument | Default | Description |
|---|---|---|
| `--model`, `-m` | `gemma2` | Ollama model name. |
| `--prompt-version`, `-p` | `v4` | Prompt template (`v4`, `v3`). |
| `--with-images` | `False` | Attach local photos for multimodal vision models. |
| `--limit` | `None` | Max unrated accommodations to evaluate. |
| `--dry-run` | `False` | Print prompts without sending Ollama requests. |

---

## 🎯 Modern Two-Pass AI Evaluation for `garage-trip.cz`

Tailored specifically for retreats of 25–35 people requiring large common spaces, sturdy tables for laptop hacking/board games, high toilet ratios, and private saunas.

### Pass 1: Structured Feature Extraction (`extract_features_llm.py`)
Parses raw HTML/DOM and extracts normalized, high-signal technical specs into `properties_structured.json` (exact bed layout, separate room counts, shower & toilet counts, sauna type, kitchen appliances, and exclusive private rental confirmation):
```bash
# Extract structured features for a single property:
python3 extract_features_llm.py o358

# Extract all downloaded HTML files:
python3 extract_features_llm.py -d html -o properties_structured.json
```

### Pass 2: Multimodal Scoring & Vision Reasoning (`rank_multimodal.py`)
Combines the structured metadata from Pass 1, property descriptions, and key gallery photos (`images/<slug>/`) to score the cottage:
```bash
# Score a specific property:
python3 rank_multimodal.py 358

# Score all properties with Pass 1 data:
python3 rank_multimodal.py -s properties_structured.json -o ratings_garage_trip.json

# Use a vision-enabled model (e.g. gemma4 / gemma4:e4b):
python3 rank_multimodal.py --model gemma4:e4b
```
Outputs detailed scores (`overall_score`, `common_room_score`, `tables_and_workspace_score`, `sleeping_comfort_score`, `toilets_ratio_score`, `wellness_score`) and explicit reasoning about visible tables, room distribution, and wellness facilities.


---

## 🤖 LLM Response Schema

When evaluated by Ollama, each accommodation is scored with **description first**:

```json
{
  "description": "Spacious mountain chalet with massive common room, 8 bedrooms, and excellent board game tables.",
  "rating": 0.92,
  "owner_in_house": false,
  "explanation": "Perfect fit for 30 people: dedicated large common room with chairs, 8 separate bedrooms preventing overcrowded rooms, high-speed Wi-Fi, and exclusive private rental."
}
```

---

## 🧪 Testing

Run the full automated test suite (46 unit tests):
```bash
make test
# Or directly:
python3 -m unittest discover -s tests -v
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).


