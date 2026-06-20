import json
import time
import re
import random
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from typing import Optional


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


@dataclass
class ProductPrice:
    pid: str
    name: Optional[str]
    mrp: Optional[int]
    selling_price: Optional[int]    # finalPrice
    fsp: Optional[int]              # Flipkart Special Price
    best_price: Optional[int]       # nepPrice — lowest after bank/exchange offers
    discount_pct: Optional[float]
    rating: Optional[str]
    rating_count: Optional[str]
    available: bool
    url: str
    error: Optional[str] = None


def find_in_json(obj, key):
    """Recursively find first occurrence of key in nested JSON."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = find_in_json(v, key)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = find_in_json(item, key)
            if result is not None:
                return result
    return None


def extract_initial_state(html: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        src = script.string or ""
        if "window.__INITIAL_STATE__" in src:
            json_str = src.split("window.__INITIAL_STATE__ = ", 1)[1].strip().rstrip(";")
            return json.loads(json_str)
    return None


def parse_product(state: dict, soup: BeautifulSoup, raw_html: str = "") -> dict:
    result = {}

    # --- Pricing from ppd (product price details) block ---
    raw = json.dumps(state)
    # Find all ppd blocks and take the one with the most complete data
    ppd_matches = re.findall(r'"ppd":\s*(\{[^}]+\})', raw)
    ppd = None
    for match in ppd_matches:
        try:
            candidate = json.loads(match)
            if "finalPrice" in candidate and "mrp" in candidate:
                ppd = candidate
                break
        except json.JSONDecodeError:
            continue

    if ppd:
        result["selling_price"] = ppd.get("finalPrice") or ppd.get("fsp")
        result["fsp"]        = ppd.get("fsp")
        result["mrp"]        = ppd.get("mrp")
        result["best_price"] = ppd.get("nepPrice")
        sp = result["selling_price"]
        mrp = result["mrp"]
        if sp and mrp and mrp > 0:
            result["discount_pct"] = round((mrp - sp) / mrp * 100, 1)
        else:
            result["discount_pct"] = None
    else:
        result.update({"selling_price": None, "fsp": None, "mrp": None,
                       "best_price": None, "discount_pct": None})

    # --- Product name from JSON-LD (most reliable) ---
    result["name"] = None
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            ld = json.loads(script.string)
            items = ld if isinstance(ld, list) else [ld]
            for item in items:
                if item.get("name"):
                    result["name"] = item["name"]
                    break
        except Exception:
            pass

    # --- Rating (from the block: "rating":4.3,"ratingsCount":7226) ---
    # Run regex on raw HTML — re-serialized JSON adds spaces that break the pattern
    rating_match = re.search(r'"rating":([\d.]+),"ratingsCount":(\d+)', raw_html)
    if rating_match:
        result["rating"] = rating_match.group(1)
        result["rating_count"] = f"{int(rating_match.group(2)):,}"
    else:
        result["rating"] = None
        result["rating_count"] = None

    # --- Availability ---
    page_text = soup.get_text().lower()
    result["available"] = "sold out" not in page_text and "notify me" not in page_text

    return result


def scrape_product(pid: str, name: str = None) -> ProductPrice:
    url = BASE_URL.format(pid=pid)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        if len(resp.text) < 5000 or "please solve the captcha" in resp.text.lower():
            return ProductPrice(
                pid=pid, name=name, mrp=None, selling_price=None, fsp=None, best_price=None,
                discount_pct=None, rating=None, rating_count=None,
                available=False, url=url, error="Blocked or captcha detected"
            )

        state = extract_initial_state(resp.text)
        if not state:
            return ProductPrice(
                pid=pid, name=name, mrp=None, selling_price=None, fsp=None, best_price=None,
                discount_pct=None, rating=None, rating_count=None,
                available=False, url=url, error="Could not find __INITIAL_STATE__"
            )

        soup = BeautifulSoup(resp.text, "html.parser")
        parsed = parse_product(state, soup, resp.text)

        return ProductPrice(
            pid=pid,
            name=parsed.get("name") or name,
            mrp=parsed.get("mrp"),
            selling_price=parsed.get("selling_price"),
            fsp=parsed.get("fsp"),
            best_price=parsed.get("best_price"),
            discount_pct=parsed.get("discount_pct"),
            rating=parsed.get("rating"),
            rating_count=parsed.get("rating_count"),
            available=parsed.get("available", True),
            url=url,
        )

    except requests.RequestException as e:
        return ProductPrice(
            pid=pid, name=name, mrp=None, selling_price=None, fsp=None, best_price=None,
            discount_pct=None, rating=None, rating_count=None,
            available=False, url=url, error=str(e)
        )


def main():
    with open("pids.json") as f:
        data = json.load(f)

    products = data.get("products", [])
    results = []

    for i, item in enumerate(products):
        pid = item["pid"]
        name = item.get("name")
        print(f"[{i+1}/{len(products)}] Scraping PID: {pid} ...")

        result = scrape_product(pid, name)
        results.append(asdict(result))

        print(f"  Name:          {result.name}")
        print(f"  Selling Price: ₹{result.selling_price:,}" if result.selling_price else "  Selling Price: N/A")
        print(f"  FSP:           ₹{result.fsp:,}" if result.fsp else "  FSP:           N/A")
        print(f"  MRP:           ₹{result.mrp:,}" if result.mrp else "  MRP:           N/A")
        print(f"  Best Price:    ₹{result.best_price:,}" if result.best_price else "  Best Price:    N/A")
        print(f"  Discount:      {result.discount_pct}%" if result.discount_pct else "  Discount:      N/A")
        print(f"  Rating:        {result.rating} ({result.rating_count})")
        print(f"  Available:     {result.available}")
        if result.error:
            print(f"  Error:         {result.error}")
        print()

        if i < len(products) - 1:
            time.sleep(random.uniform(2, 4))

    with open("results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Done. Results saved to results.json")


if __name__ == "__main__":
    main()
