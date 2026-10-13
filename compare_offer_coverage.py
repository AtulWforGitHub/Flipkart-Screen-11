"""Compare production offer logs against current scraper output.

Usage:
    python compare_offer_coverage.py path/to/log.txt --limit 12

The log file should contain entries in the same format as activity.log / journal
product lines, for example:

    2026-10-07 23:24:31 ... 200 COMHKQAD2DWA4Y8U FSP ... (3 offers) [Rahul]
    2026-10-07 23:24:31 ...   1. [Best Value] - ...
    2026-10-07 23:24:31 ...   2. ...
"""

from __future__ import annotations

import argparse
import re
import statistics
from dataclasses import dataclass

import certifi
from pymongo import MongoClient

from flipkart_scraper import FlipkartScraper


MONGO_URI = "mongodb+srv://jagsir:JWff45t518S1d8F0@cluster0.rt55a2o.mongodb.net/?appName=Cluster0"


PRODUCT_LINE_RE = re.compile(
    r"(?P<pid>[A-Z0-9]{10,})\s+FSP\s+₹[\d,]+\s+NEP\s+₹[\d,]+(?:\s+\((?P<count>\d+) offers\))?"
)
OFFER_LINE_RE = re.compile(r"\s+\d+\.\s+(?P<offer>.+)$")


@dataclass
class BaselineEntry:
    pid: str
    expected_count: int
    offers: list[str]


def normalize_offer(offer: str) -> str:
    offer = re.sub(r"\s+", " ", offer.strip())
    offer = offer.replace("• Cashback", "Cashback")
    offer = offer.replace("• Includes cashback", "Includes cashback")
    return offer.lower()


def parse_log(log_path: str) -> list[BaselineEntry]:
    entries: list[BaselineEntry] = []
    current: BaselineEntry | None = None

    with open(log_path, "r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            product_match = PRODUCT_LINE_RE.search(line)
            if product_match:
                if current and current.offers:
                    entries.append(current)
                count = int(product_match.group("count") or 0)
                current = BaselineEntry(
                    pid=product_match.group("pid"),
                    expected_count=count,
                    offers=[],
                )
                continue

            if current is None:
                continue

            offer_match = OFFER_LINE_RE.search(line)
            if offer_match:
                current.offers.append(offer_match.group("offer").strip())
                continue

            if current.offers:
                entries.append(current)
                current = None

    if current and current.offers:
        entries.append(current)

    deduped: dict[str, BaselineEntry] = {}
    for entry in reversed(entries):
        deduped.setdefault(entry.pid, entry)
    return list(deduped.values())


def load_products_by_pid(pids: list[str]) -> dict[str, dict]:
    mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    products = mongo["flipkart"]["products"]
    found = products.find(
        {"pid": {"$in": pids}},
        {"_id": 0, "pid": 1, "name": 1, "lid": 1, "url": 1},
    )
    return {doc["pid"]: doc for doc in found if doc.get("pid")}


def compare_offers(expected: list[str], actual: list[str]) -> tuple[int, list[str], list[str]]:
    expected_norm = {normalize_offer(offer): offer for offer in expected}
    actual_norm = {normalize_offer(offer): offer for offer in actual}

    matched = set(expected_norm).intersection(actual_norm)
    missing = [expected_norm[key] for key in expected_norm.keys() if key not in matched]
    extra = [actual_norm[key] for key in actual_norm.keys() if key not in matched]
    return len(matched), missing, extra


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log_path")
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    baseline = parse_log(args.log_path)
    if not baseline:
        print("No product entries found in baseline log.")
        return 1

    sample = baseline[:args.limit]
    products = load_products_by_pid([entry.pid for entry in sample])

    print(f"Loaded {len(sample)} baseline products from log.")
    print(f"Resolved {len(products)} products with LID/url from MongoDB.\n")

    match_rates: list[float] = []
    count_deltas: list[int] = []

    scraper = FlipkartScraper(headless=True)
    try:
        for index, entry in enumerate(sample, 1):
            product = products.get(entry.pid)
            if not product:
                print(f"[{index}/{len(sample)}] {entry.pid}: skipped (no Mongo product metadata)")
                continue

            result = scraper.scrape(entry.pid, product.get("lid", ""))
            actual_offers = result.get("bank_offers", [])
            matched_count, missing, extra = compare_offers(entry.offers, actual_offers)

            denom = max(len(entry.offers), 1)
            match_rate = matched_count / denom
            match_rates.append(match_rate)
            count_deltas.append(len(actual_offers) - len(entry.offers))

            print(f"[{index}/{len(sample)}] {entry.pid} | baseline={len(entry.offers)} current={len(actual_offers)} matched={matched_count}/{len(entry.offers)}")
            if missing:
                print(f"  missing: {missing[:3]}")
            if extra:
                print(f"  extra:   {extra[:3]}")

        if match_rates:
            print("\nSummary")
            print(f"  average offer match rate: {statistics.mean(match_rates):.1%}")
            print(f"  median offer match rate:  {statistics.median(match_rates):.1%}")
            print(f"  average offer count delta: {statistics.mean(count_deltas):+.2f}")
            print(f"  exact count matches: {sum(delta == 0 for delta in count_deltas)}/{len(count_deltas)}")
        else:
            print("No comparable products were scraped.")
            return 1
    finally:
        scraper.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())