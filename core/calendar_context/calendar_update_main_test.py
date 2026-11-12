import unittest
from datetime import date

import typer

from core.calendar_context.calendar_update_main import validate_date


class ValidateDateTest(unittest.TestCase):
    TODAY = date(2026, 11, 2)

    def test_spoken_and_iso_dates_resolve_to_iso(self):
        for text in ("2026-11-08", "November 8", "Nov 8th", "8 November", "the 8th of this month", "the 8th"):
            with self.subTest(text=text):
                self.assertEqual(validate_date(text, self.TODAY), "2026-11-08")
        self.assertEqual(validate_date("the 1st of next month", self.TODAY), "2026-12-01")

    def test_unreadable_dates_are_rejected(self):
        for text in ("2026-02-30", "the 31st of this month", "someday"):
            with self.subTest(text=text), self.assertRaises(typer.BadParameter):
                validate_date(text, self.TODAY)


if __name__ == "__main__":
    unittest.main()
