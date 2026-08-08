import os
import sys
import unittest
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import main


class DateAndDelayBehaviorTests(unittest.TestCase):
    def test_parse_date_input_supports_dd_mm_yyyy(self):
        self.assertEqual(main.parse_date_input("14-03-2024"), datetime.date(2024, 3, 14))
        self.assertEqual(main.parse_date_input("2024-03-14"), datetime.date(2024, 3, 14))

    def test_format_date_for_display_uses_dd_mm_yyyy(self):
        self.assertEqual(main.format_date_for_display(datetime.date(2024, 3, 14)), "14-03-2024")

    def test_calculate_reglement_delay_uses_confirmation_to_reglement(self):
        self.assertEqual(main.calculate_reglement_delay("10-03-2024", "20-03-2024"), 10)
        self.assertEqual(main.calculate_reglement_delay("2024-03-10", "2024-03-20"), 10)


if __name__ == "__main__":
    unittest.main()
