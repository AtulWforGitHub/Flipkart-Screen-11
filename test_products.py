"""
Test script to scrape specific products without MongoDB.
Run specific PIDs to test scraper functionality.
"""

import sys
import json
from flipkart_scraper import FlipkartScraper


def load_products_from_json(filename="test_products.json"):
    """Load products from JSON file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('products', [])
    except FileNotFoundError:
        print(f"Error: {filename} not found!")
        return []
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {filename}: {e}")
        return []


def test_scrape():
    """Test scraping specific products."""
    print("=" * 60)
    print("FLIPKART SCRAPER TEST")
    print("=" * 60)
    
    # Load products from JSON
    products = load_products_from_json()
    
    if not products:
        print("No products to test. Add products to test_products.json")
        return
    
    print(f"Loaded {len(products)} products from test_products.json")
    print()
    
    # Initialize scraper (no MongoDB)
    scraper = FlipkartScraper(mongo_accounts_col=None)
    
    results = []
    
    try:
        for i, product in enumerate(products, 1):
            pid = product.get('pid')
            lid = product.get('lid', '').strip()
            name = product.get('name', 'Unknown')
            
            if not pid:
                print(f"[{i}/{len(products)}] Skipping: No PID provided")
                continue
            
            print(f"[{i}/{len(products)}] {name}")
            print(f"  PID: {pid}")
            
            # Build URL
            if lid:
                url = f"https://www.flipkart.com/p/itm?pid={pid}&lid={lid}"
                print(f"  LID: {lid}")
            else:
                url = f"https://www.flipkart.com/p/itm?pid={pid}"
                print(f"  LID: (none)")
            
            # Scrape
            result = scraper.scrape(url)
            results.append(result)
            
            # Display result
            if result.get('status_label') == 'OK':
                print(f"  ✓ FSP: ₹{result.get('price'):,}" if result.get('price') else "  ✓ FSP: —")
                print(f"    NEP: ₹{result.get('lowest'):,}" if result.get('lowest') else "    NEP: —")
                print(f"    Actual Name: {result.get('name', 'N/A')[:60]}")
            else:
                print(f"  ✗ Error: {result.get('status_label', 'Unknown error')}")
            
            print()
    
    finally:
        # Close scraper
        scraper.close()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successful = sum(1 for r in results if r.get('status_label') == 'OK')
    print(f"Successful: {successful}/{len(results)}")
    print(f"Failed: {len(results) - successful}/{len(results)}")
    print()


if __name__ == "__main__":
    test_scrape()
