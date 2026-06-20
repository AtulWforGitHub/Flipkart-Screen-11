import json
import re
import sys
import time
import requests
import itertools
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BASE_URL = "https://www.flipkart.com/product/p/itm?pid={pid}"


def extract_prices(body: str) -> str:
    ppd_m = re.search(r'"ppd":\{([^}]+)\}', body)
    if ppd_m:
        try:
            ppd = json.loads('{' + ppd_m.group(1) + '}')
            final = ppd.get("finalPrice") or ppd.get("fsp")
            fsp   = ppd.get("fsp")
            nep   = ppd.get("nepPrice")
            parts = []
            if final:  parts.append(f"₹{final:,}")
            if fsp and fsp != final: parts.append(f"FSP ₹{fsp:,}")
            if nep:    parts.append(f"NEP ₹{nep:,}")
            return " | ".join(parts) if parts else "N/A"
        except Exception:
            pass
    m = re.search(r'"finalPrice":(\d+)', body)
    return f"₹{int(m.group(1)):,}" if m else "N/A"


def status_label(status: int, body: str) -> str:
    if status == 200:
        if "please solve the captcha" in body.lower():
            return "CAPTCHA"
        if len(body) < 5000:
            return "BLOCKED (tiny response)"
        if "window.__INITIAL_STATE__" in body:
            return "OK"
        return "OK (no state)"
    if status == 429:
        return "RATE LIMITED"
    if status == 403:
        return "FORBIDDEN"
    if status == 503:
        return "SERVICE UNAVAILABLE"
    return f"HTTP {status}"


def main():
    with open("pids.json") as f:
        pids = [p["pid"] for p in json.load(f)["products"]]

    pid_cycle = itertools.cycle(pids)
    count = 0

    print(f"Starting rate test — 1 req/sec — Ctrl+C to stop")
    print(f"{'#':<6} {'Timestamp':<26} {'PID':<22} {'St':>6} {'Size':>8}  Prices                           Label")
    print("-" * 115)

    while True:
        pid = next(pid_cycle)
        url = BASE_URL.format(pid=pid)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        count += 1

        try:
            t0 = time.perf_counter()
            resp = requests.get(url, headers=HEADERS, timeout=10)
            elapsed = time.perf_counter() - t0

            label = status_label(resp.status_code, resp.text)
            size_kb = len(resp.text) / 1024
            prices = extract_prices(resp.text) if label.startswith("OK") else "---"

            line = (
                f"{count:<6} {ts:<26} {pid:<22} {resp.status_code:>6} {size_kb:>6.1f}KB  {prices:<32}  {label}"
                f"  ({elapsed:.2f}s)"
            )
            print(line, flush=True)

        except requests.exceptions.Timeout:
            print(f"{count:<6} {ts:<26} {pid:<22} {'---':>6} {'---':>8}  TIMEOUT", flush=True)
        except requests.exceptions.ConnectionError as e:
            print(f"{count:<6} {ts:<26} {pid:<22} {'---':>6} {'---':>8}  CONNECTION ERROR: {e}", flush=True)
        except Exception as e:
            print(f"{count:<6} {ts:<26} {pid:<22} {'---':>6} {'---':>8}  ERROR: {e}", flush=True)

        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
