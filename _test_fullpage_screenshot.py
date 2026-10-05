"""
LOCAL TEST ONLY - not part of the app.
Tests full-page screenshot via Chrome CDP captureBeyondViewport.
Loads Flipkart with production cookies, takes a full-page PNG, saves it locally.
"""
import base64, time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from cookie_manager import load_cookies_from_mongo

opts = Options()
opts.add_argument("--window-size=1440,900")
opts.add_argument("--lang=en-IN")
opts.add_argument("--disable-blink-features=AutomationControlled")
opts.add_experimental_option("excludeSwitches", ["enable-automation"])
opts.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(options=opts)

try:
    cookies = load_cookies_from_mongo("primary")
    print(f"Loaded {len(cookies)} cookies from Mongo")

    # Override viewport to 10,000px tall BEFORE loading the page.
    # This forces Flipkart (a React SPA with inner scroll container) to
    # render all content at once — no scrolling or stitching needed.
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "mobile": False,
        "width": 1440,
        "height": 10000,
        "deviceScaleFactor": 1,
    })

    driver.get("https://www.flipkart.com")
    time.sleep(1)
    driver.delete_all_cookies()
    for cookie in cookies:
        try:
            cookie.pop("storeId", None)
            if "sameSite" in cookie:
                ss = cookie.pop("sameSite")
                if ss:
                    cookie["sameSite"] = ss
            driver.add_cookie(cookie)
        except Exception:
            pass

    # Open any product page for a more interesting full-page test
    driver.get("https://www.flipkart.com/product/p/itm?pid=MOBHPHSHZ7GRRXNA")
    time.sleep(3)

    # --- VIEWPORT screenshot (current behaviour) ---
    t0 = time.time()
    viewport_png = driver.get_screenshot_as_png()
    t1 = time.time()
    print(f"Viewport screenshot: {len(viewport_png)//1024} KB, took {t1-t0:.2f}s")
    with open("_test_viewport.png", "wb") as f:
        f.write(viewport_png)

    # --- FULL-PAGE screenshot ---
    # With the 10,000px tall viewport set above, the page renders all
    # content upfront — normal get_screenshot_as_png() captures it all.
    t0 = time.time()
    full_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
    print(f"Page height after tall-viewport render: {full_height}px")
    fullpage_png = driver.get_screenshot_as_png()
    t1 = time.time()
    print(f"Full-page screenshot: {len(fullpage_png)//1024} KB, took {t1-t0:.2f}s")
    with open("_test_fullpage.png", "wb") as f:
        f.write(fullpage_png)

    print("\nBoth saved. Compare _test_viewport.png vs _test_fullpage.png")
    input("Press Enter to close browser...")
finally:
    driver.quit()
