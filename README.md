# 🏡 Garage Trip Accommodation Scraper & AI Ranker

An intelligent web scraping, data processing, and LLM-powered ranking pipeline designed for finding, filtering, and scoring holiday cottages and chalets (*chaty a chalupy*) on [e-chalupy.cz](https://www.e-chalupy.cz).

Specially optimized for planning **large group weekend trips** (25–40 people), such as board game weekends, LAN gaming parties, and team offsites.

---

## 📌 Features

- **Automated Web Scraping**: Crawls and parses structured details from hundreds of properties across Czech regions on `e-chalupy.cz`.
- **Heuristic Filtering & Normalization**:
  - Capacity & Room count validation (e.g., 22–42 beds, min 7 rooms).
  - Price normalization per day and per property across various pricing schemes (per week, per person/night, off-season).
  - Walking and driving distance calculations to key Points of Interest (forests, restaurants, grocery stores).
  - Essential amenities detection (Wi-Fi, large common room / *společenská místnost*, grill, dedicated parking).
  - Geolocation filtering (GPS coordinate constraints and region blocklists).
- **AI Ranking with Local LLMs via Ollama**:
  - Leverages local open models (e.g. `llama3.2`, `llama3.1`, `gemma2`) or multimodal vision models (e.g. `llava`) to evaluate suitability, comfort, owner presence, and common space layout.
  - Few-shot structured prompt templates with baseline calibration examples.
- **Multimodal Visual Analysis**: Downloads accommodation photos for visual inspection of common rooms, seating, and table capacity.
- **Collaborative Scoring**: Integrates automated LLM evaluations with manual human ratings into a unified CSV ready for Google Sheets or spreadsheet analysis.

---

## 🏗 Pipeline Architecture

```
                       +-------------------+
                       |  e-chalupy.cz     |
                       +---------+---------+
                                 |
                                 v  (download.py / make scrape)
                       +-------------------+
                       |  properties.json  |
                       +---------+---------+
                                 |
                                 v  (process.py / make process)
                  +--------------+--------------+
                  |                             |
                  v                             v
            +-----------+                 +-----------+
            |  out.csv  |                 | out.json  |
            +-----+-----+                 +-----+-----+
                  |                             |
                  |                +------------+------------+
                  |                |                         |
                  |                v (get_images.py)         v (rank.py)
                  |          +-----------+             +-----------+
                  |          |   imgs/   |             |   Ollama  |
                  |          +-----+-----+             +-----+-----+
                  |                |                         |
                  |                +------------>------------+
                  |                                          |
                  |                                          v
                  |                                    +------------+
                  |                                    |ratings.json|
                  |                                    +-----+------+
                  |                                          |
                  |         +------------------------+       |
                  |         | manual-ratings.csv     |       |
                  |         +-----------+------------+       |
                  |                     |                    |
                  |                     v (add_manual_ratings.py)
                  |                     |                    |
                  +------------>--------+----------<---------+
                                        |
                                        v (merge_ratings.py / make merge)
                                +---------------+
                                | out-rated.csv |
                                +---------------+
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) (for AI evaluation)
- Desired LLM model pulled locally:
  ```bash
  ollama pull llama3.2
  # Or for multimodal vision evaluations:
  ollama pull llava
  ```

### 2. Installation
Clone repository and install required dependencies:
```bash
git clone https://github.com/gdg-garage/garage-trip-accommodation-scraper.git
cd garage-trip-accommodation-scraper
pip install -r requirements.txt
```

---

## 🛠 Step-by-Step Workflow

### Step 1: Scrape Accommodations
Download property listings from `e-chalupy.cz`:
```bash
make scrape
# Or with custom filters:
python3 download.py --capacity 20 --rooms 6 --max-region 100 -o properties.json
```

### Step 2: Enrich & Filter Data
Extract normalized prices, distance calculations, and filter based on party size:
```bash
make process
# Or customize thresholds:
python3 process.py --min-beds 22 --max-beds 40 --min-rooms 7 --max-price 16000
```
This produces:
- `out.csv`: Filtered table with all attributes.
- `out.json`: Structured JSON for programmatic steps.

### Step 3 (Optional): Download Images
Download property photos for visual LLM evaluation or manual gallery browsing:
```bash
make images
# Or download a subset:
python3 get_images.py --limit 50 --output-dir imgs
```

### Step 4: AI Ranking with Ollama
Run local LLMs to evaluate cottage descriptions and reviews:
```bash
make rank
# Or run with a specific model or prompt version:
python3 rank.py --model llama3.2 --prompt-version v3
# Or with multimodal visual inspection:
python3 rank.py --model llava --with-images
```
Ratings are saved incrementally into `ratings.json`.

### Step 5: Merge Ratings & Export
Combine model ratings and manual human votes with the property dataset:
```bash
make merge
# Or with specific input paths:
python3 merge_ratings.py --ratings ratings.json --input-csv out.csv --output-csv out-rated.csv
```

---

## 📖 CLI Reference

### `download.py`
| Argument | Default | Description |
|---|---|---|
| `--capacity` | `18` | Minimum capacity query parameter for e-chalupy search. |
| `--rooms` | `2` | Minimum rooms query parameter. |
| `--max-region` | `100` | Scan region IDs from 1 to `max-region`. |
| `--output`, `-o` | `properties.json` | Destination JSON lines file. |
| `--limit` | `None` | Max number of properties to scrape. |
| `--timeout` | `15` | HTTP request timeout in seconds. |
| `--verbose`, `-v` | `False` | Enable debug logging. |

### `process.py`
| Argument | Default | Description |
|---|---|---|
| `--input`, `-i` | `properties.json.gz` / `properties.json` | Path to scraped input. |
| `--output-csv` | `out.csv` | Output CSV path. |
| `--output-json` | `out.json` | Output JSON path. |
| `--min-beds` | `22` | Minimum bed count. |
| `--max-beds` | `42` | Maximum bed count. |
| `--min-rooms` | `7` | Minimum room count. |
| `--max-price` | `15000` | Maximum daily rental cost (CZK). |
| `--max-restaurant-dist`| `1500` | Max distance to restaurant in meters. |
| `--no-csv` / `--no-json` | `False` | Skip exporting CSV or JSON. |

### `rank.py`
| Argument | Default | Description |
|---|---|---|
| `--model`, `-m` | `llama3.2` | Ollama model tag. |
| `--prompt-version`, `-p` | `v3` | Prompt template (`v2` or `v3`). |
| `--with-images` | `False` | Attach downloaded photos to Ollama request. |
| `--limit` | `None` | Max candidate cottages to evaluate in this run. |
| `--dry-run` | `False` | Test prompt rendering without sending requests to Ollama. |

### `merge_ratings.py`
| Argument | Default | Description |
|---|---|---|
| `--ratings`, `-r` | `ratings.json` | Ratings source JSON. |
| `--input-csv`, `-i` | `out.csv` | Input property CSV. |
| `--output-csv`, `-o` | `out-rated.csv` | Merged output CSV. |

---

## 📊 Output Data Dictionary

In `out.csv` and `out-rated.csv`:
- `name`: Cottage name.
- `locality`: Region and town.
- `capacity`: Maximum number of guests.
- `rooms`: Number of bedrooms.
- `price (per day per object)`: Calculated normalized cost in CZK per day.
- `homepage`: External direct website of the property if available.
- `url`: Direct link to property on e-chalupy.cz.
- `les_distance_m`: Distance to forest in meters.
- `restaurace_distance_m`: Distance to nearest restaurant in meters.
- `obchod_distance_m`: Distance to grocery shop in meters.
- `rating_mean`, `rating_median`, `rating_samples`: Statistics on guest reviews from e-chalupy.cz.
- `ratings_mean`, `ratings_median`: Aggregated score across AI evaluations (0.0 to 1.0).
- `filtered`: Boolean flag indicating if the property violated any hard criteria.
- `filtered_reasons`: Comma-separated list of criteria violations (e.g. `small_capacity_<22`, `no_internet`).

---

## 🧪 Testing

Run the automated test suite with Python's built-in `unittest` runner:
```bash
make test
# Or directly:
python3 -m unittest discover -s tests -v
```

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
