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

### Pass 1: Text-Only Scoring (`score_text_pass1.py`)
Scores all 366 properties from `properties_structured.json` using the 100-point rubric tailored for 25–35 techies/gamers (capacity, tables/common room, beds, toilets, sauna, beer tap) and ranks them:
```bash
python3 score_text_pass1.py --input properties_structured.json --top 42 -o rankings_text_pass1.json
```

### Gallery Photos & Google Drive Archive (`download_top_candidates_images.py`)
Downloads complete photo galleries for the top candidate properties with polite pacing (random jitter per photo, 8–12s between cottages):
```bash
python3 download_top_candidates_images.py --rankings rankings_text_pass1.json --top 42 -o images
```

> [!TIP]
> **Google Drive Data & Media Archive**:
> Raw media, scraped HTML, and candidate exports are gitignored and archived in Google Drive for team access:
> - 📁 **Retreat Folder**: [Garage Trip 7.0 2026](https://drive.google.com/drive/folders/1sf3RsOdqQoInitC5ukjvDsAR-axxs98G)
> - 🖼️ **e-chalupy Photos**: [accommodation_candidates_photos/](https://drive.google.com/drive/folders/1lrIb23I96fDfNPQxfh_ZYEOWa0X8isnn) (~385 MB, 1,900+ photos)
> - 🖼️ **Booking Photos**: `accommodation_candidates_booking_photos/` (~218 MB, 1,605 high-res photos across 108 properties)
> - 📄 **Booking HTML Pages**: [accommodation_candidates_booking_html/](https://drive.google.com/drive/folders/1uNtouJ89cBmhJUQufvJ-GkfOYvaIsPp_) (~541 MB, 382 pages)
> - 📄 **e-chalupy HTML Pages**: [accommodation_candidates_html/](https://drive.google.com/drive/folders/1RwdFhUVoeKJSaCatEL7NYPET3gzZQuzM) (~97 MB, 366 pages)
> - 📦 **Raw Search MHTML Dumps**: [accommodation_candidates_raw_regions/](https://drive.google.com/drive/folders/1uGb2vsbUO_KfLRQhyyuXZ62QgYyd1keT) (~736 MB, 5 `.mhtml` files)
> - 📊 **Google Sheets & CSVs**: Available in the root folder, including `rankings_booking_final_multimodal.csv`, `booking_whole_objects_20_40.csv`, `accommodations_master_index.csv`, and [`rankings_garage_trip_final.csv`](https://drive.google.com/file/d/15p28_nwTZUqCYohED7Xiyq5xMUnmvh0S/view).

### Pass 2: Multimodal Scoring & Vision Reasoning (`rank_multimodal.py`)
Uses vision-capable `gemma4:e4b` to inspect common room photos, verify tables and seating for laptops/board games, review bedroom comfort, and evaluate saunas/wellness:
```bash
python3 rank_multimodal.py --rankings rankings_text_pass1.json --top 42 -o rankings_final_multimodal.json
```
Produces final scores, table confirmations, pros, cons, image reasoning, and verdicts for the organizers.

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

## 🏨 Booking.com Integration & Multi-Source Expansion

To complement *e-chalupy.cz* and discover modern villas, wellness chalets, and private buy-out pensions, a complete scraping, filtering, and cross-validation pipeline was added for **Booking.com**:

### 1. Raw Candidate Extraction & Capacity Filtering
- **Raw Export**: [`booking_cz_25plus_filtered.mhtml`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/booking_cz_25plus_filtered.mhtml) (**70 MB**, 616 property cards) exported from a browser session with property types: *Chalets*, *Holiday homes*, *Villas*, *Country houses*, *Lodges*, *Guest houses*, and *Farm stays*.
- **Filter Heuristics (`filter_booking_candidates.py`)**:
  - Parses card text for explicit capacity titles (*"až pro 30 lidí"*), room-by-room bed composition (*"21 beds (14 singles, 2 sofa beds, 5 large doubles)"*), and multi-room combinations.
  - **Filtered Out (< 20 capacity)**: **201 properties** (tiny 1-bedroom cabins, family suites, glamping pods).
  - **Filtered Out (> 40 capacity)**: **33 properties** (large hotel complexes / giant youth hostels).
  - **Retained Suitable Range (20–40 capacity)**: **382 unique accommodations** saved to [`booking_candidates_20_40.json`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/booking_candidates_20_40.json) and [`booking_candidates_20_40.csv`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/booking_candidates_20_40.csv).
  - **URL Export**: [`booking_urls_20_40.txt`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/booking_urls_20_40.txt) (382 candidate URLs).

### 2. Stealth Detail Page Downloader (`download_booking_html.py`)
Because Booking.com uses AWS WAF with JavaScript challenges, requests are handled via Playwright:
```bash
python3 download_booking_html.py --delay 0.6
```
- Reuses authenticated Chrome browser context to clear AWS WAF on launch.
- Automatically caches full DOM and embedded scripts into [`booking_html/<slug>.html`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/booking_html).
- Polite pacing (0.8s–1.8s random jitter) and automatic resumption on interruption.

### 3. Structured Feature Extraction (`extract_booking_features.py`)
Normalizes Booking data to match the schema used in [`properties_structured.json`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/properties_structured.json):
```bash
python3 extract_booking_features.py
```
- Extracts `schema.org/Hotel` JSON-LD (official names, addresses, localities, regions).
- Identifies amenities (sauna types, indoor/outdoor pools, hot tubs, Wi-Fi, dishwashers, beer taps).
- Extracts AI scene captions from image tags (e.g. *"a large kitchen with a wooden table and chairs"*).
- Produces [`booking_properties_structured.json`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/booking_properties_structured.json) and [`booking_properties_structured.csv`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/booking_properties_structured.csv).

### 4. High-Resolution Photo Downloader (`download_booking_photos.py`)
Downloads original uncompressed 1280x900 gallery photos from Booking's CDN:
```bash
# Download photos for a specific property:
python3 download_booking_photos.py --slug na-jeleni-stezce --limit-photos 20

# Download photos across all Booking properties:
python3 download_booking_photos.py --limit-photos 15
```
- Saves photos to [`booking_images/<slug>/`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/booking_images) along with a `photos_manifest.json` containing photo IDs and scene captions.

### 5. Whole-House Exclusive Buyout Filter (`export_booking_whole_objects.py`)
To ensure complete group privacy without sharing premises with strangers, the 382 suitable properties are filtered down to verified **exclusive whole-object rentals** (*Entire holiday home, Entire villa, Entire chalet, Entire private cottage*):
```bash
python3 export_booking_whole_objects.py
```
- **108 Whole-House Accommodations**: Retained and ranked by review score.
- **274 Multi-Room Combinations Excluded**: Filtered out public pensions or aparthotels that assemble separate rooms across shared buildings.
- **Exports**: Saved to [`booking_whole_objects_20_40.json`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/booking_whole_objects_20_40.json) and [`booking_whole_objects_20_40.csv`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/booking_whole_objects_20_40.csv) (and automatically synced to Google Drive).

### 6. Pass 1 Text & Structured Scoring (`score_text_pass1.py`)
Evaluates all 108 whole-house accommodations against the garage-trip.cz rubric (capacity, bedrooms, tables, wellness, kitchen, privacy):
```bash
python3 score_text_pass1.py -i booking_whole_objects_20_40.json -o rankings_booking_text_pass1.json -t 30
```
- Saved to [`rankings_booking_text_pass1.json`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/rankings_booking_text_pass1.json).

### 7. Pass 2 Multimodal AI Vision Scoring (`rank_booking_multimodal.py`)
Inspects downloaded gallery photos using local Apple Silicon GPU (`gemma4:e4b` on Metal) to confirm table sizes, common room space, bed quality, and wellness:
```bash
python3 rank_booking_multimodal.py --rankings rankings_booking_text_pass1.json
```
- **100% of 108 Whole-House Properties Evaluated**:
- **Output Files**: Saved to [`rankings_booking_final_multimodal.csv`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/rankings_booking_final_multimodal.csv) and [`rankings_booking_final_multimodal.json`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/rankings_booking_final_multimodal.json) (and synced to Google Drive).

#### Top Booking Accommodations by Final Score:
| Rank | Score | Name | Capacity | Bedrooms | Tables | Room | Wellness | Tables Confirmed | Notes |
|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| 1 | **78.0** | **Bret CZ** | 28 | 8 | 25/25 | 23/25 | 14/15 | Yes | Outstanding common room, large gaming tables |
| 2 | **78.0** | **Roubenka za Horou** | 26 | 10 | 20/25 | 23/25 | 14/15 | Yes | 10 bedrooms, Finnish sauna, ideal retreat fit |
| 3 | **78.0** | **Statek Hostačov** | 33 | 6 | 25/25 | 23/25 | 14/15 | Yes | Dual-listed on e-chalupy; massive hall and tables |
| 4 | **78.0** | **Sládků statek** | 29 | 10 | 24/25 | 23/25 | 13/15 | Yes | Dual-listed; spacious rustic barn & workshop area |
| 5 | **78.0** | **Chalupa Líšenka** | 25 | 7 | 24/25 | 23/25 | 14.5/15 | Yes | Dual-listed; premium wellness & dining space |
| 6 | **75.0** | **Vila Hamrska** | 26 | 7 | 22/25 | 23/25 | 14/15 | Yes | Spacious villa with sauna and outdoor space |
| 7 | **75.0** | **Pension Salma** | 32 | 8 | 24/25 | 23/25 | 12/15 | Yes | High table count, large dining & lounge room |
| 8 | **75.0** | **Na jelení stezce** | 28 | 6 | 20/25 | 23/25 | 12/15 | Yes | Modern chalet with sauna and generous living area |
| 9 | **75.0** | **Vila Baška** | 29 | 6 | 24/25 | 23/25 | 13/15 | Yes | Lake villa with confirmed banquet tables |
| 10 | **75.0** | **Tauhaus** | 35 | 8 | 24/25 | 23/25 | 12/15 | Yes | Historic converted manor with huge gathering rooms |

---

## ⚖️ Comparison: Booking.com vs. e-chalupy.cz

| Feature / Metric | e-chalupy.cz | Booking.com |
|---|---|---|
| **Raw Scraped Listings** | 1,199 links / 366 downloaded | 616 search cards |
| **Filtered Candidates (20–40 cap)** | 84 passed heuristic filter | **382 suitable accommodations** |
| **Exclusive Whole-House Rentals** | 84 whole chalets | **108 whole villas/chalets** (274 multi-room excluded) |
| **Pricing Model** | Fixed catalog pricing (weekend & weekly rates in CZK, off-season) independent of dates | Dynamic inventory-driven pricing requiring specific check-in/out dates |
| **Data Completeness** | Rich Czech descriptions, explicit owner-on-site statements, technical table of WC/shower counts | Standardized verified amenities, guest review ratings (e.g. 9.8), and detailed address metadata |
| **Photo Quality** | Mixed quality user uploads (often watermarked) | High-resolution 1280x900 CDN photos with automated computer-vision scene captions |
| **Property Types** | Traditional Czech chalupy, roubenky, and converted mountain lodges | Modern wellness villas, boutique chalets, and private buy-out pensions |

---

## 🔍 Cross-Validation & Overlap Analysis (`cross_validate_sources.py`)

Run cross-validation between Booking and e-chalupy:
```bash
python3 cross_validate_sources.py
```

### Overlap Summary:
* **Booking Candidates (20–40 capacity)**: **382**
* **e-chalupy Scraped Catalog**: **366**
* **Cross-Platform Verified Matches (on Both Portals)**: **11** (100% of matches are whole-house properties)
* **Booking-Exclusive Accommodations**: **371**
* **e-chalupy-Exclusive Accommodations**: **355**
* **Total Combined Unique Accommodations Pool**: **726 properties**

### Verified Dual-Listed Accommodations:
1. **Wellness roubenka Inffinity** (Booking: 31 cap, 9.4 rating) ⟷ e-chalupy ID `o17068`
2. **Chata Františkov** (Booking: 38 cap, 9.4 rating) ⟷ e-chalupy ID `o21177` (35 cap)
3. **Chalupa Javořinka** (Booking: 29 cap, 9.0 rating) ⟷ e-chalupy ID `o21545`
4. **Sládků statek** (Booking: 29 cap, 9.5 rating) ⟷ e-chalupy ID `o95` (29 cap)
5. **Statek Hostačov** (Booking: 33 cap) ⟷ e-chalupy ID `o18555` (29 cap)
6. **Chata Buchtovna** (Booking: 31 cap, 9.6 rating) ⟷ e-chalupy ID `o318`
7. **Chalupa Borovka** (Booking: 24 cap) ⟷ e-chalupy ID `o23159`
8. **Chata Urban Filipovice** (Booking: 34 cap, 9.2 rating) ⟷ e-chalupy ID `o4063`
9. **Chalupa Líšenka** (Booking: 25 cap) ⟷ e-chalupy ID `o17430` (30 cap)
10. **Relax Zone Vrchovina** (Booking: 25 cap, 9.4 rating) ⟷ e-chalupy ID `o8551` (25 cap)
11. **Chata Jablůňka** (Booking: 25 cap, 9.7 rating) ⟷ e-chalupy ID `o7357`

---

## 📚 Multi-Year Master Accommodation Index & Registry (`build_master_index.py`)

To prevent duplicate scraping and preserve evaluations across future retreat years, a multi-year master registry tracks all accommodations across both platforms:

```bash
# Search registry by name, village, or ID:
python3 build_master_index.py --lookup "Hříbek"
python3 build_master_index.py --lookup "Františkov"

# Display registry statistics:
python3 build_master_index.py --stats

# Rebuild / update the master index:
python3 build_master_index.py --build
```

### Registry Highlights:
* **737 Unique Accommodations Tracked**:
  * Unified records for cross-listed venues (links to both e-chalupy and Booking).
  * Capacity, bedroom counts, bed breakdowns, and verified amenities (sauna, pool, hot tub, beer tap).
  * Lifecycle tracking: `first_seen_year` (e.g. 2026), `evaluated_years`, `status` (`candidate`, `evaluated`, `booked`, `rejected`), and AI verdicts.
* **Output Files**:
  * [`accommodations_master_index.json`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/accommodations_master_index.json)
  * [`accommodations_master_index.csv`](file:///Users/tivvit/git/gdg-garage/garage-trip-accommodation-scraper/accommodations_master_index.csv) (synced to Google Drive)

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


