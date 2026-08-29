import unittest
from utils import numeric_stats


class TestUtils(unittest.TestCase):
    def test_empty_or_none(self):
        self.assertEqual(numeric_stats([]), {"samples": 0})
        self.assertEqual(numeric_stats(None), {"samples": 0})

    def test_single_element(self):
        res = numeric_stats([42])
        self.assertEqual(res["samples"], 1)
        self.assertEqual(res["max"], 42)
        self.assertEqual(res["min"], 42)
        self.assertEqual(res["mean"], 42)
        self.assertEqual(res["median"], 42)
        self.assertEqual(res["max_diff"], 0)
        self.assertNotIn("stdev", res)

    def test_multiple_elements(self):
        res = numeric_stats([10, 20, 30])
        self.assertEqual(res["samples"], 3)
        self.assertEqual(res["max"], 30)
        self.assertEqual(res["min"], 10)
        self.assertEqual(res["mean"], 20)
        self.assertEqual(res["median"], 20)
        self.assertEqual(res["max_diff"], 20)
        self.assertAlmostEqual(res["stdev"], 10.0)

    def test_identical_elements(self):
        res = numeric_stats([5, 5, 5, 5])
        self.assertEqual(res["samples"], 4)
        self.assertEqual(res["max_diff"], 0)
        self.assertEqual(res["stdev"], 0.0)


if __name__ == '__main__':
    unittest.main()
