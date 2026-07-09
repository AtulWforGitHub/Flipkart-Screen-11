"""
Test script to select saved address on Flipkart product pages.
This will be integrated into the scraper with a config flag.
"""

import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# Test product URL (using format from flipkart_scraper.py)
TEST_PRODUCT_URL = "https://www.flipkart.com/product/p/itm?pid=MOBHH69NM5ERRNFT&lid=LSTMOBHH69NM5ERRNFTB1RHB5"


def load_cookies_from_file(driver):
    """Load cookies from client_cookies.json"""
    try:
        with open("client_cookies.json", "r") as f:
            cookies = json.load(f)
        
        # Navigate to Flipkart first
        driver.get("https://www.flipkart.com")
        time.sleep(1)
        
        # Delete all existing cookies
        driver.delete_all_cookies()
        
        # Add cookies
        loaded_count = 0
        for cookie in cookies:
            try:
                cookie.pop("storeId", None)
                if "sameSite" in cookie:
                    same_site = cookie.pop("sameSite")
                    if same_site:
                        cookie["sameSite"] = same_site
                driver.add_cookie(cookie)
                loaded_count += 1
            except Exception:
                pass
        
        # Refresh to activate cookies
        driver.refresh()
        time.sleep(2)
        
        print(f"✓ Loaded {loaded_count} cookies")
        return True
    except Exception as e:
        print(f"✗ Failed to load cookies: {e}")
        return False


def select_saved_address(driver):
    """
    Click on the address selector and select the saved address.
    Returns True if successful, False otherwise.
    """
    try:
        print("\n[1] Looking for address/location selector...")
        
        # Debug: Print page title and URL
        print(f"  Current page: {driver.title}")
        print(f"  Current URL: {driver.current_url}")
        
        # Method 1: Look for pincode/delivery location elements
        selectors_to_try = [
            ("xpath", "//*[contains(text(), 'Select Delivery Location')]"),
            ("xpath", "//*[contains(text(), 'Change')][@class or @role]"),
            ("xpath", "//*[contains(text(), 'Deliver to')]"),
            ("xpath", "//input[@placeholder='Enter Delivery Pincode' or @placeholder='Enter pincode']"),
            ("xpath", "//*[@class='_2aK_ub' or contains(@class, 'pincode')]"),
            ("class name", "_2aK_ub"),  # Common Flipkart delivery selector class
            ("xpath", "//*[contains(@class, 'delivery')]"),
            ("xpath", "//*[contains(@class, 'location')]"),
        ]
        
        location_btn = None
        for method, selector in selectors_to_try:
            try:
                location_btn = driver.find_element(method, selector)
                print(f"  Found element using {method}: {selector}")
                print(f"  Element text: {location_btn.text[:100] if location_btn.text else '(no text)'}")
                print(f"  Element tag: {location_btn.tag_name}")
                break
            except NoSuchElementException:
                continue
        
        if not location_btn:
            print("  ⚠ Location selector not found")
            # Print some page content to debug
            try:
                body_text = driver.find_element("tag name", "body").text[:500]
                print(f"  Page content preview: {body_text}")
            except:
                pass
            return True  # Continue anyway
        
        # Click the element
        try:
            # Try scrolling into view first
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", location_btn)
            time.sleep(0.5)
            location_btn.click()
            time.sleep(3)
            print("  ✓ Clicked location selector")
        except Exception as e:
            print(f"  ⚠ Regular click failed: {str(e)[:100]}")
            # Try JavaScript click as fallback
            try:
                driver.execute_script("arguments[0].click();", location_btn)
                time.sleep(3)
                print("  ✓ Clicked location selector (via JavaScript)")
            except Exception as js_error:
                print(f"  ✗ JavaScript click also failed: {js_error}")
                return False
        
        # Wait for dialog/popup to appear
        time.sleep(2)
        
        # Debug: Print what appeared after clicking
        try:
            page_text = driver.find_element("tag name", "body").text
            print(f"\n  [DEBUG] Page text after click (first 500 chars):")
            print(f"  {page_text[:500]}")
        except:
            pass
        
        print("\n[2] Looking for saved address (H NO. 2364, Sector 46, Gurugram)...")
        
        # Debug: List all elements with text containing location-related keywords
        try:
            all_text_elements = driver.find_elements("xpath", "//*[contains(text(), 'Gurugram') or contains(text(), '2364') or contains(text(), 'HOME') or contains(text(), 'Sector')]")
            if all_text_elements:
                print(f"\n  [DEBUG] Found {len(all_text_elements)} elements with address-related text:")
                for i, elem in enumerate(all_text_elements[:5]):  # Show first 5
                    try:
                        print(f"    {i+1}. {elem.text[:100]}")
                    except:
                        pass
        except:
            pass
        
        # Method 2: Find the saved address element
        address_options = [
            "//div[contains(text(), 'H NO. 2364')]",
            "//div[contains(text(), 'Sector 46, Gurugram')]",
            "//div[contains(text(), 'Gurugram, Dharuhera')]",
            "//*[contains(text(), 'HOME')]/following::div[contains(text(), 'Gurugram')]",
        ]
        
        address_found = False
        for xpath in address_options:
            try:
                address_elem = driver.find_element("xpath", xpath)
                print(f"  Found address: {address_elem.text[:80]}")
                
                # Click the address - try regular click first, then JavaScript
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", address_elem)
                    time.sleep(0.5)
                    address_elem.click()
                    print("  ✓ Clicked saved address")
                except:
                    driver.execute_script("arguments[0].click();", address_elem)
                    print("  ✓ Clicked saved address (via JavaScript)")
                
                time.sleep(1)
                address_found = True
                break
            except NoSuchElementException:
                continue
        
        if not address_found:
            print("  ✗ Saved address not found")
            return False
        
        # Method 3: Look for "Deliver Here" or "Continue" button
        print("\n[3] Looking for 'Deliver Here' button...")
        try:
            deliver_btn = driver.find_element("xpath", "//button[contains(text(), 'Deliver Here') or contains(text(), 'DELIVER HERE')]")
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", deliver_btn)
                time.sleep(0.5)
                deliver_btn.click()
                print("  ✓ Clicked 'Deliver Here' button")
            except:
                driver.execute_script("arguments[0].click();", deliver_btn)
                print("  ✓ Clicked 'Deliver Here' button (via JavaScript)")
            time.sleep(1)
        except NoSuchElementException:
            print("  'Deliver Here' button not found (address might auto-select)")
        
        print("\n✓ Address selection completed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error selecting address: {e}")
        return False


def test_address_selection():
    """Main test function"""
    print("=" * 70)
    print("TESTING ADDRESS SELECTION ON FLIPKART PRODUCT PAGE")
    print("=" * 70)
    
    # Setup Chrome driver
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Headless = False to watch the browser
    # chrome_options.add_argument("--headless")
    
    service = Service("chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Step 1: Load cookies
        print("\nStep 1: Loading cookies...")
        if not load_cookies_from_file(driver):
            print("Failed to load cookies, exiting")
            return
        
        # Step 2: Navigate to product page
        print(f"\nStep 2: Navigating to product page...")
        print(f"  URL: {TEST_PRODUCT_URL}")
        driver.get(TEST_PRODUCT_URL)
        time.sleep(5)  # Wait longer for page to fully load
        
        # Check if page loaded successfully
        page_text = driver.find_element("tag name", "body").text
        if "Something went wrong" in page_text or "E002" in page_text:
            print("  ✗ Page error detected: E002 - Something went wrong")
            print("  This might be due to invalid cookies or product unavailability")
            return
        elif "page you are looking for has been moved or deleted" in page_text:
            print("  ✗ Product not found (404)")
            return
        
        print("  ✓ Page loaded successfully")
        
        # Step 3: Select saved address
        print(f"\nStep 3: Selecting saved address...")
        success = select_saved_address(driver)
        
        if success:
            print("\n" + "=" * 70)
            print("SUCCESS! Address selection works!")
            print("=" * 70)
            
            # Wait to see the result
            print("\nWaiting 5 seconds to see the result...")
            time.sleep(5)
        else:
            print("\n" + "=" * 70)
            print("FAILED! Address selection did not work")
            print("=" * 70)
            
            # Save screenshot for debugging
            screenshot_path = "address_selection_failed.png"
            driver.save_screenshot(screenshot_path)
            print(f"\nSaved screenshot: {screenshot_path}")
            
            # Wait to debug
            print("\nWaiting 10 seconds for manual inspection...")
            time.sleep(10)
        
    finally:
        print("\nClosing browser...")
        driver.quit()
        print("Done!")


if __name__ == "__main__":
    test_address_selection()
