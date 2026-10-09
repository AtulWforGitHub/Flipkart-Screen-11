from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from compare_cycle_offer_logs import CycleEntry, compare_entries, parse_cycle_log


class CompareCycleOfferLogsTests(unittest.TestCase):
    def test_parse_cycle_log_collects_product_and_offer_lines(self):
        content = """Oct 08 01:00:00 host uvicorn[1]: INFO - 200 ABCDE123456  FSP ₹10,000  NEP ₹9,500 (3 offers) [Rahul]
Oct 08 01:00:00 host uvicorn[1]: INFO -   1. [Best Value] - ₹500 off - ICICI - Credit Card
Oct 08 01:00:00 host uvicorn[1]: INFO -   2. ₹500 off - Axis - Credit Card
Oct 08 01:00:00 host uvicorn[1]: INFO -   3. ₹10 off - CRED - UPI
Oct 08 01:00:10 host uvicorn[1]: INFO - 200 XYZAB987654  FSP ₹20,000  NEP ₹18,500 (2 offers) [Rahul]
Oct 08 01:00:10 host uvicorn[1]: INFO -   1. [Best Value] - ₹1,500 off - SBI - Credit Card
Oct 08 01:00:10 host uvicorn[1]: INFO -   2. ₹1,500 off - HDFC - Credit Card
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cycle.log"
            path.write_text(content, encoding="utf-8")
            parsed = parse_cycle_log(str(path))

        self.assertEqual(set(parsed), {"ABCDE123456", "XYZAB987654"})
        self.assertEqual(len(parsed["ABCDE123456"].offers), 3)
        self.assertEqual(parsed["ABCDE123456"].offers[2], "₹10 off - CRED - UPI")

    def test_compare_entries_normalizes_cashback_variants(self):
        before = CycleEntry(
            pid="ABCDE123456",
            offers=[
                "[Best Value] - ₹500 off - Flipkart Axis - Credit Card • Cashback",
                "₹500 off - Flipkart SBI - Credit Card • Includes cashback",
            ],
        )
        after = CycleEntry(
            pid="ABCDE123456",
            offers=[
                "[Best Value] - ₹500 off - Flipkart Axis - Credit Card Cashback",
                "₹500 off - Flipkart SBI - Credit Card Includes cashback",
            ],
        )

        matched_count, missing, extra = compare_entries(before, after)

        self.assertEqual(matched_count, 2)
        self.assertEqual(missing, [])
        self.assertEqual(extra, [])

    def test_compare_entries_reports_missing_and_extra_offers(self):
        before = CycleEntry(
            pid="ABCDE123456",
            offers=[
                "₹10 off - CRED - UPI",
                "₹500 off - ICICI - Credit Card",
            ],
        )
        after = CycleEntry(
            pid="ABCDE123456",
            offers=[
                "₹500 off - ICICI - Credit Card",
                "₹400 off - HDFC - Credit Card",
            ],
        )

        matched_count, missing, extra = compare_entries(before, after)

        self.assertEqual(matched_count, 1)
        self.assertEqual(missing, ["₹10 off - CRED - UPI"])
        self.assertEqual(extra, ["₹400 off - HDFC - Credit Card"])


if __name__ == "__main__":
    unittest.main()