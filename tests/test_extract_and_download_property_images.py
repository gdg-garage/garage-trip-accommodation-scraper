import os
import tempfile
import unittest
from extract_property_images import extract_property_images, slugify
from download_property_images import is_valid_image_bytes


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Chalupa Testovací (12345)</title>
    <link rel="canonical" href="https://www.e-chalupy.cz/chalupa-test-o12345">
</head>
<body>
    <h1>Chalupa Testovací (12345)</h1>
    <div class="gallery">
        <a href="/foto/obyvak-1234-abcd.jpg" title="Obývací pokoj s krbem">
            <img src="/nahledy/obyvak-1234-abcd.jpg" alt="Obývací pokoj s krbem">
        </a>
        <a href="/foto/bazen-5678-ef01.jpg" title="Venkovní bazén">
            <img src="/nahledy/bazen-5678-ef01.jpg" alt="Venkovní bazén">
        </a>
    </div>
</body>
</html>
"""


class TestExtractAndDownloadPropertyImages(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Obývací pokoj s krbem"), "obyvaci-pokoj-s-krbem")
        self.assertEqual(slugify("Test #1 / Special?"), "test-1-special")


    def test_extract_property_images(self):
        data = extract_property_images(SAMPLE_HTML, source_filename="chalupa-test-o12345.html")
        self.assertEqual(data["property_id"], "12345")
        self.assertEqual(data["name"], "Chalupa Testovací")
        self.assertEqual(data["slug"], "chalupa-test-o12345")
        self.assertEqual(data["total_images"], 2)
        
        first = data["images"][0]
        self.assertEqual(first["url"], "https://www.e-chalupy.cz/foto/obyvak-1234-abcd.jpg")
        self.assertEqual(first["caption"], "Obývací pokoj s krbem")
        self.assertTrue(first["filename"].startswith("001_"))

    def test_is_valid_image_bytes(self):
        # JPEG header
        self.assertTrue(is_valid_image_bytes(b"\xff\xd8\xff" + b"x" * 600))
        # PNG header
        self.assertTrue(is_valid_image_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 600))
        # WebP header
        self.assertTrue(is_valid_image_bytes(b"RIFF\x00\x00\x00\x00WEBP" + b"x" * 600))
        # HTML error string (not an image)
        self.assertFalse(is_valid_image_bytes(b"<!DOCTYPE html><html>Just a moment...</html>"))
        # Too short
        self.assertFalse(is_valid_image_bytes(b"\xff\xd8\xff"))


if __name__ == "__main__":
    unittest.main()
