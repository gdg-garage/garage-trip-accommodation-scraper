#!/usr/bin/env python3
import unittest
from filter_booking_candidates import parse_capacity
from download_booking_photos import extract_photos_from_html
from cross_validate_sources import normalize_tokens


class TestBookingPipeline(unittest.TestCase):
    def test_parse_capacity_bed_breakdown(self):
        text = "Six-Bedroom House | Entire holiday home | 6 bedrooms | 21 beds (14 singles, 2 sofa beds, 5 large doubles)"
        total_beds, cap_min, cap_max, breakdowns, reason = parse_capacity(text, "Na jelení stezce")
        self.assertEqual(total_beds, 21)
        self.assertEqual(cap_min, 26)  # 14*1 + 5*2 + 2*1 = 26
        self.assertEqual(cap_max, 28)  # 14*1 + 5*2 + 2*2 = 28
        self.assertEqual(reason, "bed_breakdown")

    def test_parse_capacity_title_explicit(self):
        text = "One-Bedroom Chalet | Entire chalet"
        total_beds, cap_min, cap_max, breakdowns, reason = parse_capacity(text, "Horská chata až pro 30 lidí")
        self.assertEqual(cap_min, 30)
        self.assertEqual(cap_max, 30)
        self.assertEqual(reason, "title_explicit")

    def test_extract_photos_from_html(self):
        sample_html = '''
        <html>
        <body>
            <img src="https://cf.bstatic.com/xdata/images/hotel/max500/123456.jpg?k=abcdef123&o=" alt="a spacious living room with table and chairs" />
            <img src="https://cf.bstatic.com/xdata/images/hotel/square600/789012.webp?k=987654321&o=" alt="sauna room" />
        </body>
        </html>
        '''
        photos = extract_photos_from_html(sample_html)
        self.assertEqual(len(photos), 2)
        self.assertEqual(photos[0]["photo_id"], "123456")
        self.assertEqual(photos[0]["caption"], "a spacious living room with table and chairs")
        self.assertIn("max1280x900", photos[0]["url"])

    def test_normalize_tokens(self):
        tokens1 = normalize_tokens("Horská Chata Hříbek")
        tokens2 = normalize_tokens("benecko-chalupa-pronajmuti-hribek-o358")
        self.assertIn("hribek", tokens1)
        self.assertIn("hribek", tokens2)
        self.assertTrue(tokens1.intersection(tokens2))


if __name__ == '__main__':
    unittest.main()
