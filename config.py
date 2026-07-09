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
BROWSER_HEADLESS    = False   # set False to watch Chrome during debugging
BROWSER_RENDER_WAIT = 1.0     # seconds to wait after page load before reading DOM
