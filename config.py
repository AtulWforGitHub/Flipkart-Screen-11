# ── Scraper configuration ─────────────────────────────────────────────────────
#
# SCRAPE_METHOD controls how prices are fetched from Flipkart.
#
#   "api"     — fast, lightweight HTTP requests (current default).
#               No browser needed. Can get 403-blocked under heavy load;
#               the exponential-backoff scheduler handles recovery.
#
#   "browser" — drives a real Chrome browser via Selenium.
#               Much harder to block, but slower (~5-10s per product)
#               and requires Chrome + chromedriver installed.
#               Place chromedriver.exe next to this file, or let
#               Selenium Manager (Selenium 4.6+) auto-download it.
#
SCRAPE_METHOD = "browser"   # switch to "api" to use lightweight requests

# ── Browser-scraper settings (used only when SCRAPE_METHOD = "browser") ───────
BROWSER_HEADLESS    = True    # set False to watch Chrome during debugging
BROWSER_RENDER_WAIT = 0.5     # seconds to wait after page load before reading DOM

# ── Bank offers extraction (browser mode only) ─────────────────────────────────
# Enable extraction of bank offers, cashback, and discount information.
# This scrolls through the bank offers carousel to capture all available offers.
# Adds ~3-5 seconds to scraping time per product.
EXTRACT_BANK_OFFERS = True    # set False to disable bank offers extraction
BANK_OFFERS_VERBOSE = False   # set True to see extraction progress in console

# ── Test mode ─────────────────────────────────────────────────────────────────
# When TEST_MODE = True, only the PIDs listed in TEST_PIDS will be scraped.
# All other products are filtered out. Set False for normal operation.
TEST_MODE = False
TEST_PIDS = [
    "COMHBFRJEWGN4FMY"
]
