import json
import os.path

import requests
import urllib.parse

OBJECTS_JSON_PATH = "out.json"


def load_objects():
    return json.load(open(OBJECTS_JSON_PATH))


def download_image(url):
    return requests.get(url).content


def main():
    properties = load_objects()

    print(f"loaded {len(properties)} objects")
    total = len(properties)

    for i, p in enumerate(properties):
        for _, image_url in p["images"]:
            filename = urllib.parse.quote(image_url, safe='')
            final_path = os.path.join("imgs", filename)
            if os.path.exists(final_path):
                continue
            img = download_image(image_url)
            with open(final_path, 'wb') as f:
                f.write(img)
        print(f"done {i}/{total}")


if __name__ == '__main__':
    main()
