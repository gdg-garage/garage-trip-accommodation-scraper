import unittest
from parse_dom import (
    parse_html_content,
    extract_normalized_distance,
    extract_normalized_price,
    apply_heuristics_and_filtering,
    clean,
)
from collections import defaultdict


class TestParseDom(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(clean("  hello\r\n world \n"), "hello world")
        self.assertEqual(clean(None), "")

    def test_parse_html_content_complete(self):
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head><link rel="canonical" href="https://www.e-chalupy.cz/krkonose/chalupa-100.php"></head>
        <body>
        <div class="chata">
            <span id="cislo_o">100</span>
            <h1>Horská Roubenka</h1>
            <h2>Krkonoše - Špindlerův Mlýn</h2>
            <div id="kapacita">24 až 32 osob | 8 pokojů</div>
            <div id="kontakty">
                Telefon: 777123456
                <a href="https://www.horskaroubenka.cz">Oficiální web</a>
            </div>
            <a id="vetsi_mapa" href="https://mapy.cz/s/123">Zvětšit mapu</a>
            <div id="ikony">
                <img alt="Wi-Fi" />
                <img alt="Parkování" />
            </div>
            <div class="prehled">
                <img alt="Společenská místnost" />
                <img alt="Venkovní gril" />
            </div>
            <div class="recenze">Celkové hodnocení: 96%</div>
            <div class="kamdal">Krkonoše</div>
            <table id="dest">
                <tr><td>Les</td><td>200 m</td></tr>
                <tr><td>Restaurace</td><td>500 m</td></tr>
            </table>
            <table id="cenik">
                <tr><td>Cena za týden</td><td>70 000 Kč</td></tr>
            </table>
            <div id="nahledy">
                <a href="https://img.e-chalupy.cz/foto1.jpg" title="Přední pohled"></a>
            </div>
            <p>Popis objektu: Krásná roubenka pro velké skupiny přátel. kontakty  mapa Detailní text pro hosty. Kontakt na pronajímatele nebo provozovatele Další info.</p>
            <div>GPS souřadnice: 50.7234N, 15.6123E</div>
        </div>
        </body>
        </html>
        """
        data = parse_html_content(sample_html, source_filename="krkonose_chalupa-100.html")
        self.assertIsNotNone(data)
        self.assertEqual(data["id"], "100")
        self.assertEqual(data["name"], "Horská Roubenka")
        self.assertEqual(data["capacity"], "32")
        self.assertEqual(data["rooms"], "8")
        self.assertIn("https://www.horskaroubenka.cz", data["contact_links"])
        self.assertIn("Wi-Fi", data["icons"])
        self.assertIn("Společenská místnost", data["equipment"])
        self.assertEqual(data["numeric_ratings"], ["96"])
        self.assertEqual(data["GPS"]["N"], "50.7234")
        self.assertEqual(data["GPS"]["E"], "15.6123")
        self.assertEqual(len(data["images"]), 1)

    def test_extract_normalized_distance(self):
        self.assertEqual(extract_normalized_distance("500 m"), 500.0)
        self.assertEqual(extract_normalized_distance("2.5 km"), 2500.0)
        self.assertAlmostEqual(extract_normalized_distance("15 min"), 1250.0, places=1)
        self.assertEqual(extract_normalized_distance("unknown"), -1)

    def test_apply_heuristics_and_filtering(self):
        counters = defaultdict(int)
        prop = {
            "name": "Ideální Chalupa",
            "capacity": 30,
            "rooms": 8,
            "equipment": ["Wi-Fi", "Společenská místnost", "Parkoviště", "Gril"],
            "pricelist": ["Cena za týden", "Letní sezóna: 70 000 Kč"],
            "distances": [["Restaurace", "400 m"], ["Les", "100 m"]],
            "url": "https://www.e-chalupy.cz/krkonose/ideal.php",
            "GPS": {"N": "50.5", "E": "15.5"},
        }
        apply_heuristics_and_filtering([prop], counters)
        self.assertFalse(prop.get("filtered", False))
        self.assertEqual(prop.get("price (per day per object)"), 10000)
        self.assertEqual(prop.get("restaurace_distance_m"), 400.0)


if __name__ == '__main__':
    unittest.main()
