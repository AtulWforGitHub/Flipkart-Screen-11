from __future__ import annotations

import argparse
import re
import statistics
from dataclasses import dataclass

PRODUCT_LINE_RE = re.compile(
    r"(?P<pid>[A-Z0-9]{10,})\s+FSP\s+₹[\d,]+\s+NEP\s+₹[\d,]+(?:\s+\((?P<count>\d+) offers\))?"
)
OFFER_LINE_RE = re.compile(r"\s+\d+\.\s+(?P<offer>.+)$")


@dataclass
class CycleEntry:
    pid: str
    offers: list[str]


def normalize_offer(offer: str) -> str:
    offer = re.sub(r"\s+", " ", offer.strip())
    offer = offer.replace("• Cashback", "Cashback")
    offer = offer.replace("• Includes cashback", "Includes cashback")
    return offer.lower()


def parse_cycle_log(path: str) -> dict[str, CycleEntry]:
    entries: list[CycleEntry] = []
    current: CycleEntry | None = None

    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            product_match = PRODUCT_LINE_RE.search(line)
            if product_match:
                if current and current.offers:
                    entries.append(current)
                current = CycleEntry(pid=product_match.group("pid"), offers=[])
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

    parsed: dict[str, CycleEntry] = {}
    for entry in entries:
        parsed[entry.pid] = entry
    return parsed


def compare_entries(before: CycleEntry, after: CycleEntry) -> tuple[int, list[str], list[str]]:
    before_norm = {normalize_offer(offer): offer for offer in before.offers}
    after_norm = {normalize_offer(offer): offer for offer in after.offers}
    matched = set(before_norm).intersection(after_norm)
    missing = [before_norm[key] for key in before_norm.keys() if key not in matched]
    extra = [after_norm[key] for key in after_norm.keys() if key not in matched]
    return len(matched), missing, extra


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("before_log")
    parser.add_argument("after_log")
    parser.add_argument("--limit", type=int, default=0, help="Only print the first N per-product diffs (0 = all)")
    args = parser.parse_args()

    before = parse_cycle_log(args.before_log)
    after = parse_cycle_log(args.after_log)

    common_pids = sorted(set(before).intersection(after))
    if not common_pids:
        print("No overlapping product entries found.")
        return 1

    match_rates: list[float] = []
    count_deltas: list[int] = []
    exact_matches = 0

    printed = 0
    for pid in common_pids:
        before_entry = before[pid]
        after_entry = after[pid]
        matched_count, missing, extra = compare_entries(before_entry, after_entry)
        denom = max(len(before_entry.offers), 1)
        match_rate = matched_count / denom
        match_rates.append(match_rate)
        count_deltas.append(len(after_entry.offers) - len(before_entry.offers))
        if not missing and not extra:
            exact_matches += 1

        if args.limit == 0 or printed < args.limit:
            print(f"{pid} | before={len(before_entry.offers)} after={len(after_entry.offers)} matched={matched_count}/{len(before_entry.offers)}")
            if missing:
                print(f"  missing: {missing[:3]}")
            if extra:
                print(f"  extra:   {extra[:3]}")
            printed += 1

    print("\nSummary")
    print(f"  overlapping products: {len(common_pids)}")
    print(f"  average offer match rate: {statistics.mean(match_rates):.1%}")
    print(f"  median offer match rate:  {statistics.median(match_rates):.1%}")
    print(f"  average offer count delta: {statistics.mean(count_deltas):+.2f}")
    print(f"  exact product matches: {exact_matches}/{len(common_pids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
