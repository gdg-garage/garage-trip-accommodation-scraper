import unittest
from rank import extract_json_response, format_property, find_by_name


class TestRank(unittest.TestCase):
    def test_extract_json_response_clean(self):
        raw = '{"rating": 0.85, "description": "Spacious cottage", "owner_in_house": false, "explanation": "Fits all criteria"}'
        data = extract_json_response(raw)
        self.assertIsNotNone(data)
        self.assertEqual(data["rating"], 0.85)
        self.assertEqual(data["owner_in_house"], False)

    def test_extract_json_response_with_markdown_fences(self):
        raw = """```json
{
  "rating": 0.9,
  "description": "Great place with large common area",
  "owner_in_house": false,
  "explanation": "Perfect for board games"
}
```"""
        data = extract_json_response(raw)
        self.assertIsNotNone(data)
        self.assertEqual(data["rating"], 0.9)

    def test_extract_json_response_with_surrounding_text(self):
        raw = """Here is my evaluation of the accommodation:
{
  "rating": 0.75,
  "description": "Good cottage but slightly expensive",
  "owner_in_house": false,
  "explanation": "Decent tables and space"
}
Hope this helps organize your trip!"""
        data = extract_json_response(raw)
        self.assertIsNotNone(data)
        self.assertEqual(data["rating"], 0.75)

    def test_extract_json_response_invalid(self):
        self.assertIsNone(extract_json_response("This is not JSON"))
        self.assertIsNone(extract_json_response(""))
        self.assertIsNone(extract_json_response(None))

    def test_find_by_name(self):
        properties = [
            {"name": "Chalupa U Potoka", "id": "1"},
            {"name": "Resort Slapy", "id": "2"},
        ]
        self.assertEqual(find_by_name("potoka", properties)["id"], "1")
        self.assertEqual(find_by_name("SLAPY", properties)["id"], "2")
        self.assertIsNone(find_by_name("Nonexistent", properties))

    def test_format_property(self):
        prop = {
            "name": "Chalupa Test",
            "capacity": "30",
            "rooms": "8",
            "icons": ["Wi-Fi", "Parkování"],
            "equipment": ["Gril", "Krb"],
            "price (per day per object)": 8000,
            "filtered_reasons": ["no_grill_soft"],
            "text": "Úvodní text kontakty  mapa Popis chalupy pro hosty Kontakt na pronajímatele nebo provozovatele Další text",
            "ratings": ["Super pobyt", "Krásné prostředí"],
        }
        res = format_property(prop)
        self.assertIn("Name: Chalupa Test", res)
        self.assertIn("Capacity: 30", res)
        self.assertIn("Rooms: 8", res)
        self.assertIn("Wi-Fi, Parkování", res)
        self.assertIn("Popis chalupy pro hosty", res)
        self.assertIn("Super pobyt", res)


if __name__ == '__main__':
    unittest.main()
