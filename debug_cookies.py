"""Debug script to verify Flipkart cookies are working"""
import json
import re
from flipkart_scraper import FlipkartScraper

def check_login_status(html):
    """Check if user appears to be logged in"""
    # Look for login indicators
    if 'login' in html.lower() and 'logout' not in html.lower():
        return "❌ NOT logged in"
    if '"accountId"' in html or '"userId"' in html:
        return "✓ Logged in (accountId found)"
    if 'My Account' in html or 'myAccount' in html:
        return "✓ Logged in (My Account found)"
    return "⚠ Unknown login status"

def extract_all_prices(html):
    """Extract all price-related data from page"""
    prices = {}
    
    # Find ppd JSON
    ppd_match = re.search(r'"ppd"\s*:\s*\{[^}]+\}', html)
    if ppd_match:
        try:
            ppd_json = '{' + ppd_match.group(0) + '}'
            ppd_json = ppd_json.replace('"ppd":{', '{')
            ppd = json.loads(ppd_json)
            prices['ppd'] = ppd
        except:
            pass
    
    return prices

print("🔍 Cookie Debug Test\n")
print("=" * 60)

# Test with scraper
scraper = FlipkartScraper(headless=False)  # Use visible browser
driver = scraper._ensure_driver()

print("\n📋 Step 1: Loading product page...")
driver.get("https://www.flipkart.com/lenovo-loq-intel-core-i5-13th-gen-13450hx-16-gb-512-gb-ssd-windows-11-home-4-graphics-nvidia-geforce-rtx-3050a-144-hz-15irx9-gaming-laptop/p/itm66c74c31dbd4c?pid=COMHEYV7U4CRVF33")

import time
time.sleep(3)

html = driver.page_source

print("\n🔐 Step 2: Checking login status...")
login_status = check_login_status(html)
print(f"   {login_status}")

print("\n💰 Step 3: Extracting prices from page...")
prices_data = extract_all_prices(html)

if 'ppd' in prices_data:
    ppd = prices_data['ppd']
    print(f"\n   Raw PPD data:")
    print(f"   - fsp (Flipkart Special Price): ₹{ppd.get('fsp', 'N/A'):,}" if ppd.get('fsp') else f"   - fsp: {ppd.get('fsp')}")
    print(f"   - nepPrice (Bank Offer): ₹{ppd.get('nepPrice', 'N/A'):,}" if ppd.get('nepPrice') else f"   - nepPrice: {ppd.get('nepPrice')}")
    print(f"   - finalPrice: ₹{ppd.get('finalPrice', 'N/A'):,}" if ppd.get('finalPrice') else f"   - finalPrice: {ppd.get('finalPrice')}")
    print(f"   - mrp: ₹{ppd.get('mrp', 'N/A'):,}" if ppd.get('mrp') else f"   - mrp: {ppd.get('mrp')}")
    print(f"   - All PPD keys: {list(ppd.keys())}")
else:
    print("   ❌ No PPD data found in page!")

print("\n🔍 Step 4: Looking for account indicators in HTML...")
account_indicators = []
if '"accountId"' in html:
    account_indicators.append("accountId found")
if '"userId"' in html:
    account_indicators.append("userId found")
if 'My Account' in html:
    account_indicators.append("My Account found")

if account_indicators:
    print(f"   ✓ Found: {', '.join(account_indicators)}")
else:
    print("   ❌ No account indicators found")

print("\n" + "=" * 60)
print("\n⏸  Browser window is open - check manually:")
print("   1. Are you logged in? (Check top-right corner)")
print("   2. What prices do you see?")
print("   3. Press Enter here when done...")

input()

scraper.close()
print("\n✅ Debug complete!")
