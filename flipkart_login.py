"""
Flipkart Login Cookie Saver

Opens Flipkart in a browser, lets you manually login with your phone number
and OTP, then saves the cookies to 'client_cookies.json'.

Usage:
    python flipkart_login.py

After running:
1. Browser window will open to Flipkart
2. Click the login button and enter your phone number
3. Enter the OTP you receive
4. Once logged in, press Enter in the terminal
5. Cookies will be saved to client_cookies.json (used as primary login)
   - Vasu cookies backed up in vasu_cookies.json (fallback)
"""

import os
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from cookie_manager import save_cookies_to_mongo

# Optional SSL cert fix for MSYS2 / MinGW Python
try:
    import certifi as _certifi
    os.environ.setdefault("SSL_CERT_FILE", _certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _certifi.where())
except Exception:
    pass

# Optional stealth mode
try:
    from selenium_stealth import stealth
    HAS_STEALTH = True
except Exception:
    HAS_STEALTH = False

COOKIES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "client_cookies.json"
)


def save_flipkart_cookies():
    """Open Flipkart, wait for manual login, then save cookies."""
    
    print("=" * 60)
    print("Flipkart Login Cookie Saver")
    print("=" * 60)
    
    # Setup Chrome with visible window
    opts = Options()
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--lang=en-IN")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    
    # Create driver (let Selenium Manager auto-download the right version)
    print("\n[1] Starting Chrome (Selenium Manager downloading driver if needed)...")
    driver = webdriver.Chrome(options=opts)
    
    # Apply stealth if available
    if HAS_STEALTH:
        stealth(
            driver,
            languages=["en-IN", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
    
    try:
        # Open Flipkart
        print("\n[1] Opening Flipkart...")
        driver.get("https://www.flipkart.com")
        time.sleep(3)
        
        print("\n[2] Browser window opened!")
        print("\nNow complete these steps in the browser:")
        print("  • Click the 'Login' button")
        print("  • Enter your phone number")
        print("  • Enter the OTP you receive")
        print("  • Wait until you're logged in (you'll see your name)")
        print("\n" + "=" * 60)
        
        input("\nPress ENTER after you've logged in successfully... ")
        
        # Get cookies
        cookies = driver.get_cookies()
        
        # Ask for account name
        print("\n" + "=" * 60)
        account_name = input("Enter account name (e.g., 'Rahul', 'Vasu', 'Mobiles'): ").strip() or "default"
        
        # Save to local file (backup)
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)
        print(f"\n[+] Local backup saved to: {COOKIES_FILE}")
        
        # Save to MongoDB
        if save_cookies_to_mongo(cookies, account_name):
            print(f"[+] Cookies uploaded to MongoDB as '{account_name}'")
        else:
            print(f"[!] MongoDB upload failed, but local file saved")
        
        print(f"\n   Total cookies: {len(cookies)}")
        print("\nYou can now close the browser window.")
        print("The scraper will use these cookies from MongoDB (with local fallback).")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        time.sleep(2)
        driver.quit()


if __name__ == "__main__":
    save_flipkart_cookies()
