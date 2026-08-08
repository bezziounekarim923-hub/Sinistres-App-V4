import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import database as db


class MonthFilterTests(unittest.TestCase):
    def test_apply_post_filters_matches_month(self):
        rows = [
            {"id": 1, "date_sinistre": "01-01-2025"},
            {"id": 2, "date_sinistre": "15-02-2025"},
            {"id": 3, "date_sinistre": "20-01-2024"},
        ]

        filtered = db._apply_post_filters(rows, {"month": 1})

        self.assertEqual([r["id"] for r in filtered], [1, 3])


if __name__ == "__main__":
    unittest.main()
