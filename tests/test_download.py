import unittest
from unittest.mock import patch, MagicMock
from download import clean, get_links_in_region, get_property_info


class TestDownload(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(clean("  hello\r\n world \n"), "hello world")
        self.assertEqual(clean(None), "")

    @patch("requests.Session.post")
    def test_get_links_in_region(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <div id="vysledky_hledani">
            <div class="pl">
                <h3><a href="https://www.e-chalupy.cz/krkonose/chalupa-1.php">Chalupa 1</a></h3>
            </div>
            <div class="pl">
                <h3><a href="https://www.e-chalupy.cz/krkonose/chalupa-2.php">Chalupa 2</a></h3>
            </div>
        </div>
        """
        mock_post.return_value = mock_response

        links = get_links_in_region(1)
        self.assertEqual(len(links), 2)
        self.assertIn("https://www.e-chalupy.cz/krkonose/chalupa-1.php", links)
        self.assertIn("https://www.e-chalupy.cz/krkonose/chalupa-2.php", links)

    @patch("requests.Session.get")
    def test_get_property_info(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <div class="chata">
            <span id="cislo_o">1234</span>
            <h1>Roubenka U Lesa</h1>
            <h2>Krkonoše - Pec pod Sněžkou</h2>
            <div id="kapacita">20 až 30 osob | 8 pokojů</div>
            <div id="kontakty">
                Telefon: 123456789
                <a href="https://www.roubenka.cz">Web</a>
            </div>
            <a id="vetsi_mapa" href="https://mapy.cz/123">Mapa</a>
            <div id="ikony">
                <img alt="Wi-Fi" />
                <img alt="Parkování" />
            </div>
            <div class="prehled">
                <img alt="Gril" />
                <img alt="Krb" />
            </div>
            <div class="recenze">Celkové hodnocení: 98%</div>
            <div class="kamdal">Krkonoše</div>
            <table id="cenik">
                <tr><td>Cena za týden</td><td>80 000 Kč</td></tr>
            </table>
            <div id="nahledy">
                <a href="https://img.e-chalupy.cz/foto1.jpg" title="Pohled zepředu"></a>
            </div>
            <div>GPS lokace: 50.1234N, 15.5678E</div>
        </div>
        """
        mock_get.return_value = mock_response

        info = get_property_info("https://www.e-chalupy.cz/krkonose/chalupa-1234.php")
        self.assertEqual(info["id"], "1234")
        self.assertEqual(info["name"], "Roubenka U Lesa")
        self.assertEqual(info["locality"], "Krkonoše - Pec pod Sněžkou")
        self.assertEqual(info["capacity"], "30")
        self.assertEqual(info["rooms"], "8")
        self.assertIn("Wi-Fi", info["icons"])
        self.assertIn("Gril", info["equipment"])
        self.assertEqual(info["numeric_ratings"], ["98"])
        self.assertEqual(info["GPS"]["N"], "50.1234")
        self.assertEqual(info["GPS"]["E"], "15.5678")
        self.assertEqual(info["images"], [("Pohled zepředu", "https://img.e-chalupy.cz/foto1.jpg")])


if __name__ == '__main__':
    unittest.main()
