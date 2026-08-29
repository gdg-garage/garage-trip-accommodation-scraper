import os
import tempfile
import unittest
from unittest.mock import MagicMock
from download_images import (
    image_url_to_filename,
    get_shard_items,
    collect_images_from_html_dir,
    collect_images_from_json,
    download_image_with_retry,
)


class TestDownloadImages(unittest.TestCase):
    def test_image_url_to_filename(self):
        url = "https://img.e-chalupy.cz/galerie/pecka/foto 1.jpg"
        encoded = image_url_to_filename(url)
        self.assertNotIn(" ", encoded)
        self.assertIn("img.e-chalupy.cz", encoded)

    def test_get_shard_items(self):
        items = ["img_0", "img_1", "img_2", "img_3"]
        shard_0 = get_shard_items(items, total_shards=2, shard_id=0)
        shard_1 = get_shard_items(items, total_shards=2, shard_id=1)
        self.assertEqual(shard_0, ["img_0", "img_2"])
        self.assertEqual(shard_1, ["img_1", "img_3"])

    def test_collect_images_from_html_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            html_file = os.path.join(tmpdir, "test.html")
            with open(html_file, "w") as f:
                f.write("""
                <div>
                    <a href="/foto/cottage-front.jpg" title="Cottage front"></a>
                    <img src="/foto/cottage-inside.png" alt="Cottage inside" />
                </div>
                """)
            imgs = collect_images_from_html_dir(tmpdir)
            self.assertEqual(len(imgs), 2)
            self.assertEqual(imgs[0], ("Cottage front", "https://www.e-chalupy.cz/foto/cottage-front.jpg"))
            self.assertEqual(imgs[1], ("Cottage inside", "https://www.e-chalupy.cz/foto/cottage-inside.png"))

    def test_download_image_with_retry_success(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\xff\xd8\xff\xe0...fake jpeg"
        mock_session.get.return_value = mock_response

        content, code, is_blocked = download_image_with_retry("https://test.com/img.jpg", mock_session)
        self.assertEqual(code, 200)
        self.assertFalse(is_blocked)
        self.assertEqual(content, b"\xff\xd8\xff\xe0...fake jpeg")

    def test_download_image_with_retry_cf_blocked(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.content = b"<!DOCTYPE html><html><title>Just a moment...</title></html>"
        mock_session.get.return_value = mock_response

        content, code, is_blocked = download_image_with_retry("https://test.com/img.jpg", mock_session)
        self.assertIsNone(content)
        self.assertTrue(is_blocked)


if __name__ == '__main__':
    unittest.main()

