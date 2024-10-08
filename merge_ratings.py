import csv
import json

from utils import numeric_stats


def main():
    ratings = json.load(open("ratings.json"))

    properties = []

    with open('out.csv', 'r') as file:
        reader = csv.DictReader(file)
        for r in reader:
            prop_ratings = []
            if r["id"] in ratings:
                for rating_name, rating_value in ratings[r["id"]].items():
                    if type(rating_value) is dict:
                        for k, v in rating_value.items():
                            r[rating_name + "_" + k] = v
                    else:
                        r[rating_name] = rating_value
                    if "rating" in rating_value and "v3" in rating_name and "llama3.2_v3" != rating_name:
                        prop_ratings.append(float(rating_value["rating"]))

            if prop_ratings:
                ratings_stats = numeric_stats(prop_ratings)
                for k, v in ratings_stats.items():
                    r[f"ratings_{k}"] = v

            properties.append(r)

    all_fieldnames = set()
    for prop in properties:
        all_fieldnames |= set(prop.keys())

    with open('out-rated.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=sorted(all_fieldnames))

        writer.writeheader()
        for prop in properties:
            writer.writerow(prop)


if __name__ == '__main__':
    main()
