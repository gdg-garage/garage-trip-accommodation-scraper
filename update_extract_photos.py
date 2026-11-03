import re, os, glob, json
from bs4 import BeautifulSoup
import extract_image_urls

with open("queue_candidates_50plus.json", "r", encoding="utf-8") as f:
    queue = json.load(f)

updated_count = 0
for q in queue:
    plist = q.get("Photos_List") or []
    if len(plist) == 0:
        lid = q.get("Listing", "")
        m = re.search(r"\d+", lid)
        oid = m.group(0) if m else ""
        matches = glob.glob(f"html/*-o{oid}.html") or glob.glob(f"html/*_{oid}.html") or glob.glob(f"html/*{oid}*.html")
        if matches:
            with open(matches[0], encoding="utf-8", errors="ignore") as fh:
                imgs = extract_image_urls.extract_images_from_html(fh.read())
            if imgs:
                urls = [it["url"] for it in imgs if it.get("url")]
                q["Has_Local_Photos"] = True
                q["Photos_Folder"] = ""
                q["Photos_Count"] = len(urls)
                q["Photos_List"] = urls
                q["Primary_Photo"] = urls[0]
                updated_count += 1

print(f"Updated photo galleries for {updated_count} candidates.")

with open("queue_candidates_50plus.json", "w", encoding="utf-8") as f:
    json.dump(queue, f, indent=2, ensure_ascii=False)

with open("data/candidates_must_nice_all.json", "w", encoding="utf-8") as f:
    json.dump(queue, f, indent=2, ensure_ascii=False)

print("Saved updated queue files.")
