import os
import tempfile
import unittest
from download_images import (
    image_url_to_filename,
    get_shard_items,
    collect_images_from_html_dir,
    collect_images_from_json,
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
                <div id="nahledy">
                    <a href="https://img.e-chalupy.cz/foto1.jpg" title="Cottage front"></a>
                    <a href="/foto2.jpg" title="Cottage inside"></a>
                </div>
                """)
            imgs = collect_images_from_html_dir(tmpdir)
            self.assertEqual(len(imgs), 2)
            self.assertEqual(imgs[0], ("Cottage front", "https://img.e-chalupy.cz/foto1.jpg"))
            self.assertEqual(imgs[1], ("Cottage inside", "https://www.e-chalupy.cz/foto2.jpg"))


if __name__ == '__main__':
    unittest.main()
