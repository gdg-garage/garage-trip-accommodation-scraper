import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from scrape_links import get_links_in_region, save_links


class TestScrapeLinks(unittest.TestCase):
    @patch("requests.Session.post")
    def test_get_links_in_region(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <div id="vysledky_hledani">
            <div class="pl">
                <h3><a href="/krkonose/chalupa-1.php">Chalupa 1</a></h3>
            </div>
            <div class="pl">
                <h3><a href="https://www.e-chalupy.cz/sumava/chalupa-2.php">Chalupa 2</a></h3>
            </div>
            <div class="pl">
                <h3><a href="https://www.e-chalupy.cz/invalid-page.html">Not a property</a></h3>
            </div>
        </div>
        """
        mock_post.return_value = mock_response

        links = get_links_in_region(1)
        self.assertEqual(len(links), 2)
        self.assertIn("https://www.e-chalupy.cz/krkonose/chalupa-1.php", links)
        self.assertIn("https://www.e-chalupy.cz/sumava/chalupa-2.php", links)

    def test_save_links_txt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "urls.txt")
            urls = [
                "https://www.e-chalupy.cz/a/1.php",
                "https://www.e-chalupy.cz/b/2.php"
            ]
            save_links(urls, out_file)
            with open(out_file, "r") as f:
                lines = [l.strip() for l in f]
            self.assertEqual(lines, urls)

    def test_save_links_append(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "urls.txt")
            save_links(["https://www.e-chalupy.cz/a/1.php"], out_file)
            save_links(["https://www.e-chalupy.cz/b/2.php"], out_file, append=True)
            with open(out_file, "r") as f:
                lines = [l.strip() for l in f]
            self.assertEqual(len(lines), 2)


if __name__ == '__main__':
    unittest.main()
