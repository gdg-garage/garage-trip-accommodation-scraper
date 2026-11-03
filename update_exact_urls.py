import openpyxl, json, re, glob
from bs4 import BeautifulSoup

wb = openpyxl.load_workbook("sheet_updated_with_extractors.xlsx")
ws = wb["ranking"]

sheet_urls = {}
for r in range(2, ws.max_row + 1):
    c12 = str(ws.cell(r, 12).value or "")
    c35 = str(ws.cell(r, 35).value or "")
    
    # Extract url from HYPERLINK("url", "text")
    m_url = re.search(r'HYPERLINK\("([^"]+)"', c12) or re.search(r'HYPERLINK\("([^"]+)"', c35)
    m_name = re.search(r'HYPERLINK\("[^"]+",\s*"([^"]+)"\)', c12)
    listing_name = m_name.group(1).strip() if m_name else c12.strip()
    
    if m_url and listing_name:
        sheet_urls[listing_name] = m_url.group(1).strip()

with open("queue_candidates_50plus.json", "r", encoding="utf-8") as f:
    queue = json.load(f)

for q in queue:
    lid = q.get("Listing", "")
    current_url = q.get("Url", "")
    
    # If sheet has a clean URL
    if lid in sheet_urls and ("e-chalupy.cz" in sheet_urls[lid] or "booking.com" in sheet_urls[lid]):
        q["Url"] = sheet_urls[lid]
    elif not current_url or current_url.endswith(f"/{re.search(r'[0-9]+', lid).group(0) if re.search(r'[0-9]+', lid) else 'none'}"):
        if lid in sheet_urls:
            q["Url"] = sheet_urls[lid]

print("Sample 15 URLs:")
for q in queue[:15]:
    print(f"  {q['Listing']}: {q['Url']}")

with open("queue_candidates_50plus.json", "w", encoding="utf-8") as f:
    json.dump(queue, f, indent=2, ensure_ascii=False)

with open("data/candidates_must_nice_all.json", "w", encoding="utf-8") as f:
    json.dump(queue, f, indent=2, ensure_ascii=False)

print("Saved updated URLs to queue_candidates_50plus.json and candidates_must_nice_all.json")
