# 🏡 Garage Trip Accommodation Review Rubric

**Group**: ~22 adults (tech team), one week.  
**Use Case**: They work on laptops/desktops AND play board games at the same time, eat together, do many activities.  
**Core Rule**: The judgement must come from what the **PHOTOS actually show**. The listing text is only a claim; check it against the photos. Previous scoring of these places invented things ("exceptional common area for 30+" where photos showed nothing like it) — do not do that. If you cannot see it, it does not count (or counts against).

---

## Inputs per candidate (`<slug>`)
- `data/text/<slug>.txt` — listing text (Czech): header tags, description, rooms, equipment, prices, a few reviews.
- `data/sheets/<slug>/NN.jpg` — contact sheets, 3x3 photos each, each photo labelled with its number (yellow tag, e.g. 029). Look at EVERY sheet. If a detail matters (counting chairs, bed count, age of furniture), open the full photo: `data/photos/<slug>/<NNN>_*.jpg`.

---

## Score Breakdown (Total 100 / Meets Bar: ≥60/90, Common ≥20/35, ≤150k)

### 1. Common Area (0–35) — *THE most important*
- A big common area SEEN in photos: couches with tables near them, several separate sitting areas, ~20+ comfortable chairs, separate tables rather than one huge table.
- Benches (*lavice*) instead of chairs are bad.
- Room for laptops and board games at once.
- TV / projector is a plus.
- Wide/overhead shots that let you count chairs are a plus. If you can't tell the size or count chairs → low score.
- Count chairs you can actually see (estimate the total in the main common area(s) from overlapping shots; don't double-count the same chairs from two angles). Listing photographers shoot ONE room from 3–4 angles: before adding chairs from two photos, match landmarks (fireplace, TV, windows, curtains, lamps, sofas, bench cushions, floor).
- *Example mistake to avoid*: Chata za Grapou photos 007/008/009 look like three dining areas but are one room (same fireplace seen from the side in 007) → only ~6–8 real chairs, not 14. In `chairs_est`, name which photos show the same room. Wall benches (*lavice*), even upholstered, are not chairs.
- **Scoring Guide**:
  - **30–35**: Like the anchor (big bright room, 25–30+ real chairs over 3+ tables, 2 couch zones with TVs).
  - **20–29**: Big room, ~20 chairs, some couches, but one weakness (one long table, benches partly, couches far away, cramped).
  - **10–19**: Mid (dining room for ~20 but mostly benches / no lounge / split into small rooms / unclear).
  - **0–9**: Can't see a common space for 20, or tiny/old.

### 2. Bedrooms & Bathrooms (0–20)
- **18–20**: 2-person rooms with own shower (ideal).
- **13–17**: 3–4 per room (fine).
- **5–10**: Rooms of 5–6+ / dormitories / bunk-bed halls.
- Few/no bedroom photos lowers the score (cannot confirm).
- Count bathrooms/showers and toilets vs ~22 people ($\le 4$ people per shower is good).

### 3. Wellness & Outdoor (0–20)
- **Sauna**: Up to 10 points if seen in photos (a sauna only claimed in text = max 6).
- **Pool**: Up to 5 points (indoor/heated counts more).
- **Hot tub / bathing barrel (*koupací sud*)**: Counts within these amenities.
- **Outdoor Space**: Up to 5 points for sports/frisbee (lawn, court, pitch).

### 4. Kitchen (0–10)
- Big well-equipped kitchen seen in photos.
- Multiple fridges = sign of good group infrastructure.
- Grill = plus. Text-only claims count less.

### 5. Look & Honesty (0–10)
- Does the place look reasonably nice/modern and are the photos honest and current?
- Old/dated interiors, old-looking photos, low-res/blurry, few interior photos → low score.
- Description matching photos → higher; contradicted claims → lower (note them).

### 6. Price (0–5)
- Use full-object price per **WEEK** in CZK (take high-season / typical week price; if only per night or per person/night, compute for 22 people $\times$ 6 nights (a trip week = 6 paid nights) and specify so; a listed whole-house weekly package price is used as listed):
  - $\le 70\text{k}$ CZK $\rightarrow$ **5**
  - $70\text{k} - 80\text{k}$ CZK $\rightarrow$ **4**
  - $80\text{k} - 100\text{k}$ CZK $\rightarrow$ **3**
  - $100\text{k} - 130\text{k}$ CZK $\rightarrow$ **2**
  - $> 130\text{k}$ CZK $\rightarrow$ **1**
  - Unknown $\rightarrow$ **3**

---

## Anchor Reference (Gold Standard)
### Chalupa Nový Svět (Prostřední Lipka) — *The place the team stayed in and loved*
- **Common**: 33 (huge modern room, photo 029: long table with ~10 chairs + two more tables on the sides, ~30 chairs; two couch zones, each with a TV, foosball; floor plan 032)
- **Bedrooms**: 16 (7 apartments of 3–7 people split into 2–3 bedrooms, each with own bathroom, 11 WC)
- **Wellness & Outdoor**: 16 (Finnish sauna, hot tub barrel, no pool, big lawn + court + goals)
- **Kitchen**: 10 (4 fridges, 2 dishwashers, grill, beer tap)
- **Look**: 9
- **Price**: 4 (80k/week high season, 60k off-season)
- **Total**: **88**

---

## JSON Output Schema

```json
{
  "slug": "...",
  "name": "short name, e.g. Chalupa Nový Svět",
  "location": "village, region",
  "price_week_czk": 80000,
  "price_note": "80k summer/winter, 60k off-season",
  "capacity": "32 beds (31 per text)",
  "layout": "14 bedrooms in 7 apartments (4x4, 1x3, 1x5, 1x7), 7 bathrooms, 11 WC",
  "chairs_est": "~30 (029, 032)",
  "common_desc": "one line describing what the photos show",
  "sauna": "yes (photo 036) / text only / no",
  "pool": "...",
  "outdoor": "...",
  "kitchen_desc": "...",
  "photo_quality": "good, modern, 50 photos, 12 of common area",
  "scores": {
    "common": 33,
    "bedrooms": 16,
    "wellness_outdoor": 16,
    "kitchen": 10,
    "look": 9,
    "price": 4
  },
  "total": 88,
  "note": "2–3 sentences, honest, concrete: best thing, main problem, any text-vs-photo mismatch",
  "mismatches": "claims in text not supported by photos, or ''",
  "best_photos": ["029", "032"]
}
```

*Be harsh and consistent. Don't make anything up; when unsure, say so in the note.*
