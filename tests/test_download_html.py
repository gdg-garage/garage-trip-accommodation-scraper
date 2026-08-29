import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from download_html import (
    url_to_filename,
    get_shard_urls,
    download_page_with_retry,
    load_cached_session,
    save_cached_session,
    get_authenticated_session,
)


class TestDownloadHtml(unittest.TestCase):
    def test_url_to_filename(self):
        url = "https://www.e-chalupy.cz/cesky_raj/chalupa-pecka-1234.php"
        self.assertEqual(url_to_filename(url), "cesky_raj_chalupa-pecka-1234.html")

    def test_get_shard_urls(self):
        urls = [f"url_{i}" for i in range(10)]
        
        # 3 shards
        shard_0 = get_shard_urls(urls, total_shards=3, shard_id=0)
        shard_1 = get_shard_urls(urls, total_shards=3, shard_id=1)
        shard_2 = get_shard_urls(urls, total_shards=3, shard_id=2)

        self.assertEqual(len(shard_0) + len(shard_1) + len(shard_2), 10)
        self.assertEqual(set(shard_0 + shard_1 + shard_2), set(urls))
        self.assertEqual(shard_0, ["url_0", "url_3", "url_6", "url_9"])
        self.assertEqual(shard_1, ["url_1", "url_4", "url_7"])
        self.assertEqual(shard_2, ["url_2", "url_5", "url_8"])

    def test_get_shard_urls_invalid_shard(self):
        with self.assertRaises(ValueError):
            get_shard_urls(["url_1"], total_shards=2, shard_id=3)

    def test_download_page_success(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.encoding = "utf-8"
        mock_session.get.return_value = mock_response

        text, code, is_blocked = download_page_with_retry("https://test.com", mock_session)
        self.assertEqual(code, 200)
        self.assertFalse(is_blocked)
        self.assertIn("Test", text)

    def test_download_page_cloudflare_blocked(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "<title>Just a moment...</title>"
        mock_session.get.return_value = mock_response

        text, code, is_blocked = download_page_with_retry("https://test.com", mock_session)
        self.assertIsNone(text)
        self.assertEqual(code, 403)
        self.assertTrue(is_blocked)

    def test_session_caching(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            temp_path = tf.name

        try:
            cookies = {"cf_clearance": "dummy_token_123"}
            ua = "CustomUA/1.0"
            save_cached_session(temp_path, cookies, ua)

            loaded = load_cached_session(temp_path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["cookies"]["cf_clearance"], "dummy_token_123")
            self.assertEqual(loaded["user_agent"], ua)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_get_authenticated_session_manual_token(self):
        session = get_authenticated_session(
            cf_clearance="explicit_token_xyz",
            user_agent="TestAgent/1.0",
            no_browser=True,
        )
        self.assertEqual(session.cookies.get("cf_clearance"), "explicit_token_xyz")


if __name__ == '__main__':
    unittest.main()

