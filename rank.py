import ollama
import json

import urllib.parse
import os
from pathlib import Path

OBJECTS_JSON_PATH = "out.json"
INCLUDE_IMAGES = False
# model="llama3",
# model="llama3.2:7b",
# model="gemma2",
# model="llama3.1",
# model="llava:34b",
# model = "llava-llama3",
MODEL = "llama3.1"
PROMPT_VERSION = "v2"
PROMPTS = {
    "v2": """"
I want to go to organize an event for more then 25 of my friends. 
Anything with lower capacity would need to be really amazing for us to consider. In general capacity around 30 places is ideal because we have more flexibility.
We are looking for accommodation and we needs something with a nice common room to play board games, therefore we need many chairs and tables. 
We prefer not to have more than 5 people in one room.
We also love PC games so we need a place where to put the desktops and ideally a good internet connection.
Places where the owner stays with us are probably not great because we have long nights and that may be uncomfortable for the owner. So places like guesthouses (penzion in Czech) are not great.
Also apartments are a no-go for us we need to rent the whole property.

The descriptions I will provide will be in Czech but always reply in English.

Make sure to take the visitor reviews with a grain of salt mainly when there is not enough of them.

We already visited the following 2 accommodations with my friends and we really liked it.

The structured description of the first accommodation follows:
{}

The structured description of the second accommodation follows:
{}

The structured description of the accommodation which should be rated follows:
{}

Your task is to rate the described object based on our requirements in json format containing the following fields (and only that):
* "rating": which is a number between 0 and 1 where 1 means very suitable object for the event.
* "description": max one sentence description for the object. Examples: "Fancy wooden cottage with sauna.", "Moldy dump."
* "owner_in_house": boolean, if the owner is present in the house which may be mentioned in the equipment or visitor reviews.
* "explanation": Explain the motivation for the rating.

{}
Make sure to reply with only the valid JSON and nothing more and only in english!
""",
    "v3": """"
I want to organize an event for more then 25 of my friends. 
Anything with lower capacity would need to be really amazing for us to consider. In general capacity around 30 places is ideal because we have more flexibility.
We are looking for accommodation and we needs something with a nice common room to play board games, therefore we need many chairs and tables. 
We prefer not to have more than 5 people in one room.
We also love PC games so we need a place where to put the desktops and ideally a good internet connection.
Places where the owner stays with us are probably not great because we have long nights and that may be uncomfortable for the owner. So places like guesthouses (penzion in Czech) are not great.
Also apartments are a no-go for us we need to rent the whole property.
We do not care about winter amenities because our event is happening in September.

The descriptions I will provide will be in Czech but always reply in English.

Make sure to take the visitor reviews with a grain of salt mainly when there is not enough of them.

We already visited the following 2 accommodations with my friends and we really liked it.

The structured description of the first accommodation follows:
{}

The structured description of the second accommodation follows:
{}

The structured description of the accommodation which should be rated follows:
{}

Your task is to rate the described object based on our requirements in json format containing the following fields (and only that):
* "rating": which is a number between 0 and 1 where 1 means very suitable object for the event.
* "description": max one sentence description for the object. Examples: "Fancy wooden cottage with sauna.", "Moldy dump."
* "owner_in_house": boolean, if the owner is present in the house which may be mentioned in the equipment or visitor reviews.
* "explanation": Explain the motivation for the rating.

{}
Make sure to reply with only the valid JSON and nothing more and only in english!
""",
}


#

def format_property(p):
    # url 	 https://ww...
    # id 	 objekt č. ...
    # name 	 Chalupa Pa...
    # locality 	 Pecka...
    # capacity 	 18...
    # rooms 	 4...
    # icons 	 ['Domácí m...
    # contact_raw 	     Telefo...
    # contact_links 	 ['http://w...
    # map_link 	 https://ww...
    # distances 	 [['autobus...
    # equipment 	 ['Možnost ...
    # ratings 	 ['Jaro 202...
    # numeric_ratings 	 [100, 100,...
    # place 	 Pecka - da...
    # pricelist 	 ['Ceny za ...
    # images 	 [['Chalupa...
    # text
    # Chalupa P...
    # GPS 	 {'N': '50....
    # homepage 	 http://www...
    # rating_stats 	 {'max': 10...
    # distances_map 	 {'autobus'...
    # les_distance_m 	 500.0...
    # restaurace_distance_m 	 200.0...
    # obchod_distance_m 	 200.0...
    # price (per day per object) 	 5580...
    # filtered_reasons 	 ['not_enou...
    # filtered 	 True...
    # area 	 cesky_raj...

    ratings = ["  * " + i.replace("\r\n", " ").replace("\n", "") for i in p["ratings"]]

    return f"""
Name: {p["name"]}
Capacity: {p["capacity"]}
Rooms: {p["rooms"]}
Features: {','.join(p["icons"])}
Equipment: {','.join(p["equipment"])}
Price: {p.get("price (per day per object)", 0)}
Bad features: {','.join(p.get("filtered_reasons", []))}
Description: {p["text"].replace("\r\n", " ").replace("\n", " ").split("Kontakt na pronajímatele nebo provozovatele")[0].split("kontakty  mapa")[1].strip()}
Visitor reviews: 
{'\n'.join(ratings)}
"""


def load_objects():
    return json.load(open(OBJECTS_JSON_PATH))


def find_by_name(name, properties):
    for p in properties:
        if name in p["name"].lower():
            return p


def main():
    properties = load_objects()

    print(f"loaded {len(properties)} objects")

    properties = [p for p in properties if not p.get("filtered", False)]
    print(f"filtered to {len(properties)} objects")

    simia = find_by_name("chalupa simia", properties)
    centrum_slapy = find_by_name("drevníky resort slapy", properties)

    # prompt = PROMPT.format(format_property(simia))
    #
    # response = ollama.generate(
    #     # model="llama3",
    #     # model="llama3.2:1b",
    #     model="gemma2",
    #     prompt=prompt
    # )
    #
    # print(json.loads(response["response"].replace("```", "").replace("json", "")))
    #
    # prompt = PROMPT.format(format_property(centrum_slapy))
    #
    # response = ollama.generate(
    #     # model="llama3",
    #     # model="llama3.2:1b",
    #     model="gemma2",
    #     prompt=prompt
    # )
    #
    # print(json.loads(response["response"].replace("```", "").replace("json", "")))

    processed = 0

    ratings = json.load(open("ratings.json"))

    for p in properties:
        print(p["name"], p["url"])

        result_id = f"{MODEL}_{PROMPT_VERSION}"

        present_ratings = ratings.get(p["id"], {})
        if result_id in present_ratings:
            print(f"already rated with {MODEL} and prompt {PROMPT_VERSION} skip")
            processed += 1
            print(f"{processed}/{len(properties)}")
            continue

        prompt = PROMPTS[PROMPT_VERSION].format(
            format_property(centrum_slapy), format_property(simia), format_property(p),
            "Do not forget to use attached images of the accommodation for the analysis.\n" if INCLUDE_IMAGES else "")
        # print(prompt)

        images = []
        if INCLUDE_IMAGES:
            images = [os.path.abspath(os.path.join("imgs", urllib.parse.quote(i[1], safe=''))) for i in p["images"]]

        response = ollama.generate(
            model=MODEL,
            prompt=prompt,
            images=images,
        )

        # print(response["response"])
        try:
            rating = json.loads(response["response"].replace("```", "").replace("json", "").strip())
            print(rating)
            # print("---")

            present_ratings[result_id] = rating
            ratings[p["id"]] = present_ratings
        except:
            print(f"rating failed")

        processed += 1
        # if processed > 2:
        #     break

        print(f"{processed}/{len(properties)}")

        json.dump(ratings, open("ratings.json", "w"))


if __name__ == '__main__':
    main()
