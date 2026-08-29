import unittest
from extract_links import extract_accommodation_links, is_property_url


class TestExtractLinks(unittest.TestCase):
    def test_is_property_url(self):
        self.assertTrue(is_property_url("https://www.e-chalupy.cz/ubytovani-vrchlabi-apartman-pod-slunecnim-vrchem-o22928"))
        self.assertTrue(is_property_url("https://www.e-chalupy.cz/wellness-roubenka-inffinity-zacler-pronajem-o17068"))
        self.assertTrue(is_property_url("https://www.e-chalupy.cz/krkonose/chalupa-pecka-1234.php"))
        self.assertFalse(is_property_url("https://www.e-chalupy.cz/krkonose/chaty-chalupy-pronajem.php"))
        self.assertFalse(is_property_url("https://www.e-chalupy.cz/last-minute"))
        self.assertFalse(is_property_url("https://www.e-chalupy.cz/vyhledavani?limit=20000"))

    def test_extract_accommodation_links(self):
        sample_html = """
        <div class="c-property">
            <a href="https://www.e-chalupy.cz/chata-severka-rokytnice-nad-jizerou-pronajem-o12300">Severka</a>
        </div>
        <div class="property-box">
            <a href="/ubytovani-harrachov-pension-svaty-jan-o3681">Pension Svaty Jan</a>
        </div>
        <a href="/last-minute">Last minute</a>
        """
        links = extract_accommodation_links(sample_html)
        self.assertEqual(len(links), 2)
        self.assertIn("https://www.e-chalupy.cz/chata-severka-rokytnice-nad-jizerou-pronajem-o12300", links)
        self.assertIn("https://www.e-chalupy.cz/ubytovani-harrachov-pension-svaty-jan-o3681", links)


if __name__ == '__main__':
    unittest.main()
