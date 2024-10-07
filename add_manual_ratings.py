import csv
import json


def main():
    ratings = json.load(open("ratings.json"))

    with open('manual-ratings-9-2024.csv', 'r') as file:
        reader = csv.DictReader(file)
        for r in reader:
            if r["id"] not in ratings:
                ratings[r["id"]] = {}
            ratings[r["id"]]["tivvit"] = {"like": r['tivvit like'], "veto": r["tivvit veto"]}
            ratings[r["id"]]["simon"] = r['simon']
            ratings[r["id"]]["eve"] = r['eve']
            ratings[r["id"]]["tomas"] = r['tomas']

    json.dump(ratings, open("ratings.json", "w"))


if __name__ == '__main__':
    main()
