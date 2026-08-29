import unittest
from collections import defaultdict
from process import (
    extract_normalized_distance,
    is_equipment_present,
    filtering,
    extract_normalized_price,
    distances_to_map,
    add_homepage,
)


class TestProcess(unittest.TestCase):
    def test_extract_normalized_distance(self):
        self.assertEqual(extract_normalized_distance("500 m"), 500.0)
        self.assertEqual(extract_normalized_distance("1.5 km"), 1500.0)
        self.assertEqual(extract_normalized_distance("2,5 km"), 2500.0)
        # 10 min at 5km/h (5000m / 60 min = 83.333 m/min * 10 = 833.3)
        self.assertAlmostEqual(extract_normalized_distance("10 min"), 833.3, places=1)
        self.assertEqual(extract_normalized_distance("unknown distance"), -1)
        self.assertEqual(extract_normalized_distance(""), -1)

    def test_is_equipment_present(self):
        prop = {"equipment": ["Wi-Fi připojení", "Venkovní gril", "Parkoviště u objektu"]}
        self.assertTrue(is_equipment_present(["wifi", "wi-fi"], prop))
        self.assertTrue(is_equipment_present(["gril"], prop))
        self.assertTrue(is_equipment_present(["parko"], prop))
        self.assertFalse(is_equipment_present(["sauna"], prop))

    def test_filtering_valid_property(self):
        counters = defaultdict(int)
        prop = {
            "name": "Super Chalupa",
            "capacity": 30,
            "rooms": 8,
            "equipment": ["Wi-Fi", "Společenská místnost", "Parkoviště", "Gril"],
            "restaurace_distance_m": 500,
            "price (per day per object)": 10000,
            "url": "https://www.e-chalupy.cz/krkonose/chalupa-1.php",
            "GPS": {"N": "50.5", "E": "15.5"},
        }
        filtering([prop], counters)
        self.assertFalse(prop.get("filtered", False))
        self.assertNotIn("filtered_reasons", prop)

    def test_filtering_invalid_capacity(self):
        counters = defaultdict(int)
        small_prop = {
            "name": "Mala Chata",
            "capacity": 10,
            "rooms": 4,
            "equipment": ["Wi-Fi", "Společenská místnost", "Parkoviště"],
            "url": "https://www.e-chalupy.cz/krkonose/chata.php",
        }
        filtering([small_prop], counters, min_beds=22)
        self.assertTrue(small_prop.get("filtered", False))
        self.assertIn("small_capacity_<22", small_prop.get("filtered_reasons", []))

    def test_filtering_expensive(self):
        counters = defaultdict(int)
        expensive_prop = {
            "name": "Luxury Chata",
            "capacity": 30,
            "rooms": 10,
            "price (per day per object)": 25000,
            "equipment": ["Wi-Fi", "Společenská místnost", "Parkoviště"],
            "url": "https://www.e-chalupy.cz/krkonose/chata.php",
        }
        filtering([expensive_prop], counters, max_price=15000)
        self.assertTrue(expensive_prop.get("filtered", False))
        self.assertIn("expensive", expensive_prop.get("filtered_reasons", []))

    def test_extract_normalized_price_weekly(self):
        counters = defaultdict(int)
        prices = []
        prop = {
            "capacity": 30,
            "rooms": 8,
            "pricelist": [
                "Cena za týden",
                "Letní sezona: 70 000 Kč",
            ]
        }
        extract_normalized_price([prop], counters, prices)
        self.assertEqual(prop.get("price (per day per object)"), 10000)
        self.assertEqual(prices, [10000])

    def test_extract_normalized_price_per_person(self):
        counters = defaultdict(int)
        prices = []
        prop = {
            "capacity": 20,
            "rooms": 5,
            "pricelist": [
                "Cena za osobu / noc",
                "Mimo sezonu: 500 Kč",
            ]
        }
        extract_normalized_price([prop], counters, prices)
        self.assertEqual(prop.get("price (per day per object)"), 10000)

    def test_distances_to_map(self):
        prop = {
            "distances": [
                ["Les", "500 m"],
                ["Restaurace", "1 km"],
            ]
        }
        distances_to_map([prop])
        self.assertEqual(prop["distances_map"], {"les": "500 m", "restaurace": "1 km"})

    def test_add_homepage(self):
        counters = defaultdict(int)
        prop = {
            "contact_links": ["https://www.chalupa.cz", "https://facebook.com/chalupa", "#"]
        }
        add_homepage([prop], counters)
        self.assertEqual(prop.get("homepage"), "https://www.chalupa.cz")
        self.assertEqual(counters["homepage_present"], 1)


if __name__ == '__main__':
    unittest.main()
