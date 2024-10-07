import csv
import json


def main():
    ratings = json.load(open("ratings.json"))

    properties = []

    with open('out.csv', 'r') as file:
        reader = csv.DictReader(file)
        for r in reader:
            if r["id"] in ratings:
                for rating_name, rating_value in ratings[r["id"]].items():
                    if type(rating_value) is dict:
                        for k, v in rating_value.items():
                            r[rating_name + "_" + k] = v
                    else:
                        r[rating_name] = rating_value

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
