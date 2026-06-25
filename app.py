import json
import re
import time
import random
import queue
import threading
import certifi
import requests as req
import logging
import sys
import os
import atexit
from collections import deque
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from pymongo import MongoClient, ASCENDING, DESCENDING
import config

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = "8953384321:AAGwWwD-7fkcR7hIMYrIxm-m8wZfXpKbKAs"
TELEGRAM_CHAT_ID = "1124426595"  # Vasu
MONGO_URI        = "mongodb+srv://vasu4651_db_user:8Jgyc1ZaTDw5Y5cn@cluster0.rt55a2o.mongodb.net/?appName=Cluster0"
 

# ── MongoDB ───────────────────────────────────────────────────────────────────
_mongo    = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
_db       = _mongo["flipkart"]
_col      = _db["price_history"]   # {pid, name, url, ts, fsp, nep}
_col_pids = _db["products"]        # {pid, name, url}
_col_subs = _db["tg_subscribers"]  # {chat_id}

# ── Shared state ──────────────────────────────────────────────────────────────
_state    = {}   # pid → latest snapshot
_last     = {}   # pid → {price, lowest_price} for change detection
_baseline = {}   # pid → {price, lowest_price} seeded from last MongoDB record
_records  = {}   # pid → {low_fsp, low_nep, high_fsp, high_nep} all-time records
_last_success = {}  # pid → ISO string of last successful 200 (persisted via MongoDB)
_last_scrape_time = {}  # pid → timestamp of last scrape (for fair rotation)
_alerts   = []
_clients  = []
_lock     = threading.Lock()

# ── Live Logs ─────────────────────────────────────────────────────────────────
_logs = deque(maxlen=200)  # Keep last 200 log lines
_log_clients = []  # SSE clients for log streaming
_app_start_time = datetime.now()  # Track when app started
_auto_restart_enabled = True  # Toggle for auto-restart - enabled by default

class LogCapture(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_line = f"[{timestamp}] {msg}"
            _logs.append(log_line)
            # Notify all log stream clients (asyncio queues)
            import asyncio
            for q in _log_clients:
                try:
                    # asyncio.Queue.put_nowait() works from sync code
                    q.put_nowait(log_line)
                except (asyncio.QueueFull, Exception):
                    pass
        except:
            pass

# Set up logging to capture print statements and logs
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        LogCapture()
    ]
)
logger = logging.getLogger(__name__)

# Suppress noisy urllib3 retry warnings from Selenium
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.ERROR)

# ── Scraper abstraction ───────────────────────────────────────────────────────
# One browser instance reused across all scrapes (only when method=browser)
_browser_scraper = None

# Cleanup function to close browser on exit
def _cleanup_browser():
    global _browser_scraper
    if _browser_scraper is not None:
        try:
            _browser_scraper.close()
        except:
            pass

# Register cleanup handler
atexit.register(_cleanup_browser)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}
BASE_URL = "https://www.flipkart.com/product/p/itm?pid={pid}"


def _fetch_prices(pid: str) -> dict:
    """Unified fetch interface. Returns:
        {http_status, size_kb, fsp, nep, status_label, error_msg}
    """
    if config.SCRAPE_METHOD == "browser":
        from flipkart_scraper import FlipkartScraper
        global _browser_scraper
        if _browser_scraper is None:
            _browser_scraper = FlipkartScraper(
                headless=config.BROWSER_HEADLESS,
                render_wait=config.BROWSER_RENDER_WAIT,
            )
        
        try:
            data = _browser_scraper.scrape(pid)
        except Exception as e:
            error_str = str(e).lower()
            # Chrome crashed or connection lost - force browser recreation
            if any(x in error_str for x in ['connection', 'winerror 10061', 'refused', 'reset']):
                logger.warning(f"🔄 Chrome crashed - forcing browser reload (Error: {e})")
                try:
                    _browser_scraper.close()
                except:
                    pass
                _browser_scraper = None
                return {"http_status": None, "size_kb": 0,
                        "fsp": None, "nep": None,
                        "status_label": "RETRY", "error_msg": "Chrome crashed - will retry"}
            # Other error - propagate
            raise
        
        if data.get("error"):
            return {"http_status": None, "size_kb": 0,
                    "fsp": None, "nep": None,
                    "status_label": f"ERROR: {data['error']}", "error_msg": data["error"]}
        return {"http_status": 200, "size_kb": 0,
                "fsp": data.get("fsp"), "nep": data.get("nep"),
                "status_label": "OK" if (data.get("fsp") or data.get("nep")) else "NO_PRICE",
                "error_msg": None}

    # ── default: lightweight HTTP/requests ────────────────────────────────
    resp = req.get(BASE_URL.format(pid=pid), headers=HEADERS, timeout=10)
    size_kb = round(len(resp.text) / 1024, 1)
    if resp.status_code == 200 and len(resp.text) > 5000:
        ppd_m = re.search(r'"ppd":\{([^}]+)\}', resp.text)
        ppd = {}
        if ppd_m:
            try:
                ppd = json.loads('{' + ppd_m.group(1) + '}')
            except Exception:
                pass
        fsp = ppd.get("fsp")
        nep = ppd.get("nepPrice")
        return {"http_status": resp.status_code, "size_kb": size_kb,
                "fsp": fsp, "nep": nep,
                "status_label": "OK" if (fsp or nep) else "NO_PRICE",
                "error_msg": None}
    label = "BLOCKED" if resp.status_code == 200 else f"HTTP {resp.status_code}"
    return {"http_status": resp.status_code, "size_kb": size_kb,
            "fsp": None, "nep": None, "status_label": label, "error_msg": label}


# ── MongoDB helpers ───────────────────────────────────────────────────────────
def load_products():
    return list(_col_pids.find({}, {"_id": 0, "pid": 1, "name": 1, "url": 1}))


def load_baseline():
    for item in load_products():
        pid = item["pid"]
        name = item.get("name", pid)
        url = item.get("url", "")
        
        # Load latest non-null fsp and nep independently — the last row may have
        # nep=null if the offer briefly expired, so we query each field separately
        # to guarantee we seed in-memory state with the best known values.
        fsp_doc = _col.find_one({"pid": pid, "fsp": {"$gt": 0}}, sort=[("ts", DESCENDING)])
        nep_doc = _col.find_one({"pid": pid, "nep": {"$gt": 0}}, sort=[("ts", DESCENDING)])
        any_doc = _col.find_one({"pid": pid}, sort=[("ts", DESCENDING)])
        if fsp_doc or nep_doc:
            # Load into both _baseline AND _last so alerts work immediately after restart
            price_data = {
                "price":        fsp_doc.get("fsp") if fsp_doc else None,
                "lowest_price": nep_doc.get("nep") if nep_doc else None,
            }
            _baseline[pid] = price_data
            _last[pid] = price_data.copy()  # Also populate _last for immediate alerts
        doc = any_doc
        if doc:
            raw_ts = doc.get("ts_last") or doc.get("ts")
            if raw_ts:
                if hasattr(raw_ts, "tzinfo") and raw_ts.tzinfo is None:
                    _last_success[pid] = raw_ts.isoformat() + "+00:00"
                else:
                    _last_success[pid] = raw_ts.isoformat()
                # Initialize last scrape time from MongoDB for fair rotation
                _last_scrape_time[pid] = raw_ts.timestamp() if hasattr(raw_ts, "timestamp") else 0
        # Load all-time low/high fsp and nep from history
        low_fsp_doc = _col.find_one({"pid": pid, "fsp": {"$ne": None}}, sort=[("fsp", ASCENDING)])
        low_nep_doc = _col.find_one({"pid": pid, "nep": {"$ne": None}}, sort=[("nep", ASCENDING)])
        high_fsp_doc = _col.find_one({"pid": pid, "fsp": {"$ne": None}}, sort=[("fsp", DESCENDING)])
        high_nep_doc = _col.find_one({"pid": pid, "nep": {"$ne": None}}, sort=[("nep", DESCENDING)])
        _records[pid] = {
            "low_fsp": low_fsp_doc.get("fsp") if low_fsp_doc else None,
            "low_nep": low_nep_doc.get("nep") if low_nep_doc else None,
            "high_fsp": high_fsp_doc.get("fsp") if high_fsp_doc else None,
            "high_nep": high_nep_doc.get("nep") if high_nep_doc else None,
        }
        
        # Populate _state with baseline snapshot so products appear immediately on dashboard
        baseline = _baseline.get(pid, {})
        rec = _records.get(pid, {})
        _state[pid] = {
            "pid": pid,
            "name": name,
            "url": url,
            "price": baseline.get("price"),
            "lowest_price": baseline.get("lowest_price"),
            "price_prev": None,
            "lowest_prev": None,
            "price_dir": None,
            "lowest_dir": None,
            "all_time_low_fsp": rec.get("low_fsp"),
            "all_time_low_nep": rec.get("low_nep"),
            "all_time_high_fsp": rec.get("high_fsp"),
            "all_time_high_nep": rec.get("high_nep"),
            "http_status": 200,
            "size_kb": 0,
            "status": "LOADED",
            "ts": datetime.now().strftime("%H:%M:%S"),
            "last_success_ts": _last_success.get(pid),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────
def send_telegram(msg: str):
    if not TELEGRAM_TOKEN:
        return
    # Always include Vasu + any registered subscribers
    chat_ids = {TELEGRAM_CHAT_ID}
    for doc in _col_subs.find({}, {"chat_id": 1}):
        chat_ids.add(str(doc["chat_id"]))
    for cid in chat_ids:
        try:
            r = req.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": cid, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=5,
            )
            logger.info(f"[Telegram] → {cid} status={r.status_code} ok={r.json().get('ok')}")
        except Exception as e:
            logger.info(f"[Telegram] ERROR to {cid}: {e}")


def broadcast(payload: dict):
    import asyncio
    data = json.dumps(payload)
    with _lock:
        dead = []
        for q in _clients:
            try:
                # asyncio.Queue.put_nowait() works from sync code
                q.put_nowait(data)
            except (asyncio.QueueFull, Exception):
                dead.append(q)
        for q in dead:
            _clients.remove(q)


# ── Background scraper ────────────────────────────────────────────────────────
def scrape_loop():
    while True:
        products = load_products()
        if not products:
            time.sleep(5)
            continue

        # Sort products by oldest scrape time first (fair rotation)
        products_sorted = sorted(
            products,
            key=lambda p: _last_scrape_time.get(p["pid"], 0)
        )

        # Dynamic gap: max 10 requests/min = 1 request per 6s minimum
        # Slower when fewer products, faster when many products
        gap = max(6, min(30, 300 / len(products)))

        for item in products_sorted:
            pid  = item["pid"]
            name = item.get("name", pid)
            url  = item.get("url", "")
            ts   = datetime.now().strftime("%H:%M:%S")

            rec  = _records.get(pid, {})
            last = _last.get(pid, _baseline.get(pid, {}))
            snapshot = {
                "pid": pid, "name": name, "url": url,
                "price":        last.get("price"),
                "lowest_price": last.get("lowest_price"),
                "price_prev": None, "lowest_prev": None,
                "price_dir": None,  "lowest_dir": None,
                "all_time_low_fsp": rec.get("low_fsp"),
                "all_time_low_nep": rec.get("low_nep"),
                "all_time_high_fsp": rec.get("high_fsp"),
                "all_time_high_nep": rec.get("high_nep"),
                "http_status": None, "size_kb": 0,
                "status": "PENDING", "ts": ts,
                "last_success_ts": _last_success.get(pid),
            }

            try:
                fetched = _fetch_prices(pid)
                snapshot["http_status"] = fetched["http_status"]
                snapshot["size_kb"]     = fetched["size_kb"]

                if fetched["status_label"] in ("OK", "NO_PRICE"):
                    price  = fetched["fsp"]
                    lowest = fetched["nep"]
                    # Carry forward the last known value if the scraper returned
                    # falsy (None or 0) — Flipkart sometimes returns nepPrice:0
                    # when a bank offer isn't active, which is indistinguishable
                    # from a partial read. Always keep last known until a positive
                    # value arrives.
                    if not price:
                        price = last.get("price")
                    if not lowest:
                        lowest = last.get("lowest_price")
                    snapshot["price"]        = price
                    snapshot["lowest_price"] = lowest
                    snapshot["status"]       = "OK" if (price or lowest) else "NO_PRICE"

                    if price or lowest:
                        now_utc = datetime.now(timezone.utc)
                        latest  = _col.find_one({"pid": pid}, sort=[("ts", DESCENDING)])
                        if latest and latest.get("fsp") == price and latest.get("nep") == lowest:
                            _col.update_one({"_id": latest["_id"]}, {"$set": {"ts_last": now_utc}})
                        else:
                            _col.insert_one({
                                "pid": pid, "name": name, "url": url,
                                "ts": now_utc, "ts_last": now_utc,
                                "fsp": price, "nep": lowest,
                            })
                        _last_success[pid] = now_utc.isoformat()

                    price_changed = False
                    price_dir = None
                    lowest_changed = False
                    lowest_dir = None

                    if price is not None:
                        prev = last.get("price")
                        if prev is not None and price != prev:
                            price_changed = True
                            price_dir = "DOWN" if price < prev else "UP"
                            snapshot["price_prev"] = prev
                            snapshot["price_dir"] = price_dir

                    if lowest is not None:
                        prev = last.get("lowest_price")
                        if prev is not None and lowest != prev:
                            lowest_changed = True
                            lowest_dir = "DOWN" if lowest < prev else "UP"
                            snapshot["lowest_prev"] = prev
                            snapshot["lowest_dir"] = lowest_dir

                    if price_changed or lowest_changed:
                        overall = price_dir if price_changed else lowest_dir
                        if price_changed and lowest_changed and price_dir != lowest_dir:
                            overall = "CHANGED"

                        # Format price lines - always show both
                        price_lines = []
                        if price is not None:
                            price_lines.append(f"Price: <b>₹{price:,}</b>")
                        if lowest is not None:
                            price_lines.append(f"Lowest: <b>₹{lowest:,}</b>")
                        price_text = "\n".join(price_lines)
                        
                        product_link = f'<a href="{url}">{name}</a>'
                        
                        if overall == "DOWN":
                            msg = (
                                f"🔻 <b>PRICE DROPPED</b> 🔻\n\n"
                                f"<b>{product_link}</b>\n"
                                f"━━━━━━━━━━━━━━\n"
                                f"{price_text}"
                            )
                        elif overall == "UP":
                            msg = (
                                f"🔺 <b>PRICE INCREASED</b> 🔺\n\n"
                                f"<b>{product_link}</b>\n"
                                f"━━━━━━━━━━━━━━\n"
                                f"{price_text}"
                            )
                        else:
                            msg = (
                                f"🔶 <b>PRICE CHANGED</b> 🔶\n\n"
                                f"<b>{product_link}</b>\n"
                                f"━━━━━━━━━━━━━━\n"
                                f"{price_text}"
                            )

                        send_telegram(msg)
                        _alerts.append({"ts": ts, "pid": pid, "name": name, "msg": msg})
                        logger.info(f"[Alert] {ts}  {pid[:12]:<12}  {msg.replace(chr(10), ' | ')}")
                        if len(_alerts) > 100:
                            _alerts.pop(0)

                    _last[pid] = {"price": price, "lowest_price": lowest}
                    if pid not in _baseline:
                        _baseline[pid] = {"price": price, "lowest_price": lowest}
                    snapshot["last_success_ts"] = _last_success.get(pid)

                    rec = _records.setdefault(pid, {"low_fsp": None, "low_nep": None, "high_fsp": None, "high_nep": None})
                    if price is not None:
                        if rec["low_fsp"] is None or price < rec["low_fsp"]:
                            rec["low_fsp"] = price
                        if rec["high_fsp"] is None or price > rec["high_fsp"]:
                            rec["high_fsp"] = price
                    if lowest is not None:
                        if rec["low_nep"] is None or lowest < rec["low_nep"]:
                            rec["low_nep"] = lowest
                        if rec["high_nep"] is None or lowest > rec["high_nep"]:
                            rec["high_nep"] = lowest
                    snapshot["all_time_low_fsp"] = rec["low_fsp"]
                    snapshot["all_time_low_nep"] = rec["low_nep"]
                    snapshot["all_time_high_fsp"] = rec["high_fsp"]
                    snapshot["all_time_high_nep"] = rec["high_nep"]

                    fsp_str = f"FSP ₹{price:,}" if price else "FSP —"
                    nep_str = f"NEP ₹{lowest:,}" if lowest else "NEP —"
                    
                    # Add login status
                    login_status = ""
                    if _browser_scraper and hasattr(_browser_scraper, 'account_name'):
                        if _browser_scraper.account_name:
                            login_status = f" [{_browser_scraper.account_name}]"
                        else:
                            login_status = " [🚨 not logged in]"
                    
                    logger.info(f"[{ts}] {fetched['http_status'] or 200} {pid[:12]:<12}  {fsp_str}  {nep_str}{login_status}")

                else:
                    snapshot["status"] = fetched["status_label"]
                    logger.info(f"[{ts}] {fetched['http_status'] or '—'} {pid[:12]:<12}  {snapshot['status']}")

            except req.exceptions.Timeout:
                snapshot["status"] = "TIMEOUT"
                logger.info(f"[{ts}]  — {pid[:12]:<12}  TIMEOUT")
            except Exception as e:
                snapshot["status"] = f"ERROR: {type(e).__name__}"
                logger.info(f"[{ts}]  — {pid[:12]:<12}  ERROR: {type(e).__name__}")

            # Skip if deleted mid-iteration
            if not _col_pids.find_one({"pid": pid}, {"_id": 1}):
                continue

            _state[pid] = snapshot
            broadcast({"type": "product", "data": snapshot})
            
            # Track scrape time for fair rotation
            _last_scrape_time[pid] = time.time()

            # Dynamic gap + random breaks (10% chance of 60s pause)
            if random.random() < 0.1:
                time.sleep(60)
            else:
                time.sleep(gap)


# ── Telegram bot helpers ──────────────────────────────────────────────────────
import html as _html

_tg_awaiting = {}   # chat_id → "add" while waiting for a product link

HELP_TEXT = (
    "🤖 <b>Flipkart Price Monitor</b>\n\n"
    "<b>Add a product</b>\n"
    "• Paste a Flipkart link any time, or\n"
    "• /addproduct then send the link\n\n"
    "<b>See &amp; remove</b>\n"
    "• /list — live prices with ❌ remove buttons\n\n"
    "<b>Alerts</b>\n"
    "• /start subscribe · /stop pause\n"
    "• You get a 🔥 alert whenever a tracked price drops."
)


def _tg_send(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        req.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                 json=payload, timeout=15)
    except Exception as e:
            pass

def _tg_edit(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text,
               "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        req.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
                 json=payload, timeout=5)
    except Exception as e:
            pass

def _tg_answer_callback(cb_id, text=""):
    try:
        req.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                 json={"callback_query_id": cb_id, "text": text}, timeout=5)
    except Exception:
        pass


def _set_bot_commands():
    try:
        req.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands",
            json={"commands": [
                {"command": "list",       "description": "Tracked products + prices (remove buttons)"},
                {"command": "addproduct", "description": "Add a product (send a Flipkart link)"},
                {"command": "help",       "description": "How to use this bot"},
                {"command": "start",      "description": "Subscribe to price alerts"},
                {"command": "stop",       "description": "Pause price alerts"},
            ]},
            timeout=5,
        )
    except Exception as e:
        pass


def _name_from_slug(slug: str) -> str:
    out = []
    for w in slug.replace("-", " ").split():
        wl = w.lower()
        if re.fullmatch(r"\d+gb", wl):
            out.append(wl[:-2] + "GB")
        elif re.fullmatch(r"\d+tb", wl):
            out.append(wl[:-2] + "TB")
        elif wl in ("gb", "tb", "3g", "4g", "5g"):
            out.append(wl.upper())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _parse_flipkart_url(raw: str):
    raw = (raw or "").strip()
    pid = name = clean_url = ""
    m = re.search(r"[?&]pid=([A-Za-z0-9]+)", raw)
    if m:
        pid = m.group(1).upper()
    # Handles both www.flipkart.com/<slug>/p/<itm> and
    # dl.flipkart.com/dl/<slug>/p/<itm> (share/deep-link URLs)
    slug_m = re.search(r"flipkart\.com/(?:dl/)?([^/]+)/p/([^/?#&]+)", raw, re.I)
    if slug_m:
        slug, itm = slug_m.group(1), slug_m.group(2)
        name = _name_from_slug(slug)
        if pid:
            clean_url = f"https://www.flipkart.com/{slug}/p/{itm}?pid={pid}"
    return pid, name, clean_url


def _register_product(raw: str, custom_name: str = "") -> dict:
    raw = (raw or "").strip()
    pid, derived_name, clean_url = _parse_flipkart_url(raw)
    if not pid:
        bare = raw.upper()
        if re.fullmatch(r'[A-Z0-9]{6,25}', bare):
            pid = bare
    if not pid or not re.match(r'^[A-Z0-9]{6,25}$', pid):
        return {"status": "invalid"}
    existing = _col_pids.find_one({"pid": pid})
    if existing:
        return {"status": "exists", "pid": pid,
                "name": existing.get("name", pid), "url": existing.get("url", "")}
    final_name = (custom_name or "").strip() or derived_name or pid
    url = clean_url or f"https://www.flipkart.com/product/p/itm?pid={pid}"
    _col_pids.insert_one({"pid": pid, "name": final_name, "url": url})
    return {"status": "added", "pid": pid, "name": final_name, "url": url}


def _remove_product(pid: str) -> bool:
    pid = (pid or "").strip().upper()
    res = _col_pids.delete_one({"pid": pid})
    if res.deleted_count == 0:
        return False
    _col.delete_many({"pid": pid})
    _state.pop(pid, None)
    _last.pop(pid, None)
    _baseline.pop(pid, None)
    _records.pop(pid, None)
    broadcast({"type": "delete", "pid": pid})
    return True


def _tg_list_view():
    products = load_products()
    if not products:
        return ("📭 No products tracked yet.\nSend a Flipkart link or /addproduct to start.", None)
    lines = [f"🛒 <b>Tracking {len(products)} product{'s' if len(products) != 1 else ''}</b>\n"]
    rows = []
    for i, p in enumerate(products):
        pid = p["pid"]
        name = p.get("name", pid)
        url = p.get("url", f"https://www.flipkart.com/product/p/itm?pid={pid}")
        snap = _state.get(pid, {})
        price = snap.get("price")
        lowest = snap.get("lowest_price")
        ps = f"₹{price:,}" if price else "—"
        ls = f"₹{lowest:,}" if lowest else "—"
        product_link = f'<a href="{url}">{_html.escape(name)}</a>'
        lines.append(f"<b>{i+1}.</b> <b>{product_link}</b>\n   💰 Price: {ps}  |  🏷 Lowest: {ls}\n")
        label = name if len(name) <= 28 else name[:27] + "…"
        rows.append([{"text": f"❌ {label}", "callback_data": f"rm:{pid}"}])
    lines.append("\nTap ❌ next to a product to stop tracking it.")
    return ("\n".join(lines), {"inline_keyboard": rows})


def _tg_add_from_text(chat_id, fname, raw):
    result = _register_product(raw)
    if result["status"] == "added":
        reply = (f"✅ Now tracking <b>{_html.escape(result['name'])}</b>\n"
                 f"You'll get a 🔥 alert when the price drops.")
    elif result["status"] == "exists":
        reply = f"ℹ️ <b>{_html.escape(result['name'])}</b> is already being tracked."
    else:
        reply = ("❌ I couldn't find a Flipkart product in that.\n"
                 "Send the full product URL (it should contain pid=…).")
    _tg_send(chat_id, reply)
    pass


def _tg_handle_callback(cb):
    data = cb.get("data", "")
    cb_id = cb.get("id")
    message = cb.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    msg_id = message.get("message_id")
    if data.startswith("rm:"):
        pid = data[3:]
        ok = _remove_product(pid)
        _tg_answer_callback(cb_id, "Removed ✅" if ok else "Already removed")
        view_text, markup = _tg_list_view()
        _tg_edit(chat_id, msg_id, view_text, markup)
    else:
        _tg_answer_callback(cb_id)


def telegram_poll_loop():
    """Long-poll Telegram for commands, product links, and inline buttons."""
    offset = None
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
            if offset:
                params["offset"] = offset
            r = req.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params=params, timeout=35,
            )
            updates = r.json().get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1
                if "callback_query" in upd:
                    try:
                        _tg_handle_callback(upd["callback_query"])
                    except Exception as e:
                        pass
                    continue
                msg = upd.get("message", {})
                raw_text = (msg.get("text") or "").strip()
                text    = raw_text.lower()
                chat_id = str(msg.get("chat", {}).get("id", ""))
                fname   = msg.get("chat", {}).get("first_name", "there")
                if not chat_id or not raw_text:
                    continue
                cmd = text.split()[0].split("@")[0]
                if cmd in ("/start", "start", "hi", "hello"):
                    _col_subs.update_one(
                        {"chat_id": chat_id},
                        {"$set": {"chat_id": chat_id, "name": fname}},
                        upsert=True,
                    )
                    _tg_send(chat_id, f"👋 Hi {fname}! You're now subscribed to Flipkart price alerts.\n\nSend a Flipkart link to track a product, or tap /list to see what's tracked.")
                    pass
                elif cmd == "/stop":
                    _col_subs.delete_one({"chat_id": chat_id})
                    _tg_send(chat_id, "✅ Unsubscribed. Send /start to re-subscribe.")
                    pass
                elif cmd in ("/help", "help"):
                    _tg_awaiting.pop(chat_id, None)
                    _tg_send(chat_id, HELP_TEXT)
                elif cmd in ("/list", "/products"):
                    _tg_awaiting.pop(chat_id, None)
                    view_text, markup = _tg_list_view()
                    _tg_send(chat_id, view_text, markup)
                elif cmd == "/addproduct":
                    arg = raw_text[len("/addproduct"):].strip().lstrip("@").strip()
                    if arg and "flipkart" in arg.lower() or (arg and re.search(r'[?&]pid=', arg)):
                        _tg_awaiting.pop(chat_id, None)
                        _tg_add_from_text(chat_id, fname, arg)
                    else:
                        _tg_awaiting[chat_id] = "add"
                        _tg_send(chat_id, "📎 Send me the Flipkart product link now and I'll track it.\n(Or just paste a link any time.)")
                elif _tg_awaiting.get(chat_id) == "add":
                    _tg_awaiting.pop(chat_id, None)
                    _tg_add_from_text(chat_id, fname, raw_text)
                elif ("flipkart.com" in text) or ("pid=" in text) or (
                    re.fullmatch(r'[A-Za-z0-9]{12,25}', raw_text) is not None
                    and any(ch.isdigit() for ch in raw_text)
                    and any(ch.isalpha() for ch in raw_text)
                ):
                    _tg_add_from_text(chat_id, fname, raw_text)
        except Exception as e:
            pass
            time.sleep(5)


HEARTBEAT_INTERVAL = 60 * 10  # every 10 minutes


def heartbeat_loop():
    time.sleep(30)  # wait for first scrape cycle to complete
    while True:
        try:
            products = load_products()
            recent = _alerts[-5:] if _alerts else []  # Get last 5 alerts
            lines = ["📊 <b>Price Update</b>\n"]

            num_emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
            for i, p in enumerate(products):
                snap   = _state.get(p["pid"], {})
                price  = snap.get("price")
                lowest = snap.get("lowest_price")
                name   = p.get("name", p["pid"])
                p_str  = f"₹{price:,}" if price else "—"
                l_str  = f"₹{lowest:,}" if lowest else "—"
                lines.append(f"<b>{i+1}.</b> <b>{_html.escape(name)}</b>\n   💰 Price: {p_str}  |  🏷 Lowest: {l_str}\n")
            if recent:
                lines.append("\n🚨 <b>Recent price changes:</b>")
                for j, a in enumerate(reversed(recent), 1):
                    change_line = a["msg"].split(chr(10))[-1]
                    lines.append(f"  {j}. {_html.escape(a['name'])} — {change_line}")
            else:
                lines.append("\n🟢 No price changes since last update")

            send_telegram("\n".join(lines))
        except Exception:
            pass
        time.sleep(HEARTBEAT_INTERVAL)


# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    _col.create_index([("pid", ASCENDING), ("ts", DESCENDING)])
    _col_pids.create_index("pid", unique=True)
    _col_subs.create_index("chat_id", unique=True)
    load_baseline()
    _set_bot_commands()
    threading.Thread(target=scrape_loop,        daemon=True).start()
    threading.Thread(target=heartbeat_loop,     daemon=True).start()
    threading.Thread(target=telegram_poll_loop, daemon=True).start()
    threading.Thread(target=auto_restart_timer, daemon=True).start()
    yield
    if _browser_scraper is not None:
        _browser_scraper.close()


app = FastAPI(lifespan=lifespan)

# Skip ngrok browser warning for all responses
class NgrokBypassMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

app.add_middleware(NgrokBypassMiddleware)


# ── Request models ────────────────────────────────────────────────────────────
class AddProduct(BaseModel):
    url:  str = ""
    pid:  str = ""
    name: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/hello")
def hello():
    return {"ok": True, "ts": datetime.now().isoformat()}


@app.get("/test-telegram")
def test_telegram():
    send_telegram("🔔 <b>Test</b> — Flipkart Monitor is working!")
    return {"sent": True}


@app.post("/reload-browser")
def reload_browser():
    """Force close and recreate browser to reload fresh cookies"""
    global _browser_scraper
    if _browser_scraper is not None:
        try:
            _browser_scraper.close()
        except:
            pass
        _browser_scraper = None
    logger.info("🔄 Browser closed - will reload with fresh cookies on next scrape")
    return {"ok": True, "message": "Browser will reload on next scrape"}


@app.get("/products")
def get_products():
    return list(_state.values())


@app.post("/products")
def add_product(body: AddProduct):
    result = _register_product(body.url or body.pid, body.name)
    if result["status"] == "invalid":
        raise HTTPException(status_code=400, detail="Couldn't find a PID. Paste the full Flipkart product URL.")
    if result["status"] == "exists":
        raise HTTPException(status_code=409, detail="Product is already being tracked")
    return {"ok": True, "pid": result["pid"], "name": result["name"], "url": result["url"]}


@app.delete("/products/{pid}")
def delete_product(pid: str):
    if not _remove_product(pid):
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True, "pid": pid.strip().upper()}


@app.get("/alerts")
def get_alerts():
    return list(reversed(_alerts))


@app.get("/stream")
async def stream():
    import asyncio
    q = asyncio.Queue(maxsize=200)
    with _lock:
        _clients.append(q)
    for snap in list(_state.values()):
        try:
            q.put_nowait(json.dumps({"type": "product", "data": snap}))
        except asyncio.QueueFull:
            break

    async def generator():
        try:
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            with _lock:
                if q in _clients:
                    _clients.remove(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ── Admin Dashboard ───────────────────────────────────────────────────────────
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard():
    """Main admin dashboard with stats, controls, and logs"""
    uptime = datetime.now() - _app_start_time
    uptime_str = str(uptime).split('.')[0]  # Remove microseconds
    
    product_count = len(load_products())
    browser_status = "Active" if _browser_scraper else "Not initialized"
    login_status = "Unknown"
    if _browser_scraper and hasattr(_browser_scraper, 'account_name'):
        login_status = _browser_scraper.account_name or "Not logged in"
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard - Flipkart Monitor</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            font-size: 2rem;
            margin-bottom: 30px;
            text-align: center;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.2);
        }}
        .stat-label {{
            font-size: 0.9rem;
            opacity: 0.8;
            margin-bottom: 8px;
        }}
        .stat-value {{
            font-size: 1.8rem;
            font-weight: bold;
        }}
        .controls {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            border: 1px solid rgba(255,255,255,0.2);
        }}
        .controls h2 {{
            font-size: 1.3rem;
            margin-bottom: 20px;
        }}
        .button-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .btn {{
            padding: 14px 24px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            background: rgba(255,255,255,0.2);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
        }}
        .btn:hover {{
            background: rgba(255,255,255,0.3);
            transform: translateY(-2px);
        }}
        .btn-danger {{
            background: rgba(239, 68, 68, 0.8);
            border-color: rgba(239, 68, 68, 0.5);
        }}
        .btn-danger:hover {{
            background: rgba(239, 68, 68, 1);
        }}
        .logs-section {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.2);
        }}
        .logs-section h2 {{
            font-size: 1.3rem;
            margin-bottom: 15px;
        }}
        .logs-container {{
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            padding: 15px;
            height: 400px;
            overflow-y: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85rem;
            line-height: 1.6;
        }}
        .log-line {{
            margin-bottom: 5px;
            opacity: 0.9;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
            background: rgba(34, 197, 94, 0.2);
            border: 1px solid rgba(34, 197, 94, 0.5);
        }}
        .status-badge.inactive {{
            background: rgba(239, 68, 68, 0.2);
            border-color: rgba(239, 68, 68, 0.5);
        }}
        .toast {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.9);
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            display: none;
            z-index: 1000;
        }}
        .toast.show {{
            display: block;
            animation: slideIn 0.3s ease-out;
        }}
        @keyframes slideIn {{
            from {{ transform: translateX(400px); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛠️ Admin Dashboard</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">App Uptime</div>
                <div class="stat-value">{uptime_str}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Last Restarted</div>
                <div class="stat-value">{_app_start_time.strftime('%H:%M:%S')}</div>
                <div class="stat-label" style="font-size:0.75rem;margin-top:4px">{_app_start_time.strftime('%Y-%m-%d')}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Products Tracked</div>
                <div class="stat-value">{product_count}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Browser Status</div>
                <div class="stat-value" style="font-size:1.2rem">
                    <span class="status-badge {'' if _browser_scraper else 'inactive'}">{browser_status}</span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Login Status</div>
                <div class="stat-value" style="font-size:1.3rem">{login_status}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Auto-Restart</div>
                <div class="stat-value" style="font-size:1.2rem">
                    <span class="status-badge {'' if _auto_restart_enabled else 'inactive'}">{'Enabled' if _auto_restart_enabled else 'Disabled'}</span>
                </div>
            </div>
        </div>

        <div class="controls">
            <h2>⚙️ Controls</h2>
            <div class="button-grid">
                <button class="btn" onclick="reloadBrowser()">🔄 Reload Browser</button>
                <button class="btn" onclick="toggleAutoRestart()">⏰ Toggle Auto-Restart</button>
                <button class="btn" onclick="window.location.href='/admin/logs'">📋 Detailed Logs</button>
                <button class="btn" onclick="window.location.href='/'">📊 View Dashboard</button>
                <button class="btn btn-danger" onclick="restartApp()">🔴 Restart App</button>
            </div>
        </div>

        <div class="logs-section">
            <h2>📝 Live Logs <span style="font-size:0.9rem;opacity:0.7">(last 50 lines)</span></h2>
            <div class="logs-container" id="logs">
                <div class="log-line" style="opacity:0.5">Connecting to log stream...</div>
            </div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        function showToast(message) {{
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }}

        async function reloadBrowser() {{
            try {{
                const response = await fetch('/reload-browser', {{ method: 'POST' }});
                const data = await response.json();
                showToast(data.message);
            }} catch (e) {{
                showToast('Failed to reload browser');
            }}
        }}

        async function toggleAutoRestart() {{
            try {{
                const response = await fetch('/admin/toggle-auto-restart', {{ method: 'POST' }});
                const data = await response.json();
                showToast(data.message);
                setTimeout(() => location.reload(), 1500);
            }} catch (e) {{
                showToast('Failed to toggle auto-restart');
            }}
        }}

        async function restartApp() {{
            if (!confirm('Are you sure you want to restart the app? It will be back online in ~10 seconds.')) return;
            try {{
                const response = await fetch('/admin/restart', {{ method: 'POST' }});
                const data = await response.json();
                showToast(data.message);
            }} catch (e) {{
                showToast('Restart triggered - app restarting...');
            }}
        }}

        // Live log streaming
        const logsDiv = document.getElementById('logs');
        const eventSource = new EventSource('/admin/logs/stream');
        let logLines = [];
        
        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
        
        eventSource.onmessage = function(event) {{
            const data = JSON.parse(event.data);
            if (data.line) {{
                logLines.push(data.line);
                if (logLines.length > 50) logLines.shift();
                logsDiv.innerHTML = logLines.map(line => `<div class="log-line">${{escapeHtml(line)}}</div>`).join('');
                logsDiv.scrollTop = logsDiv.scrollHeight;
            }}
        }};

        eventSource.onerror = function() {{
            logsDiv.innerHTML = '<div class="log-line" style="color:#ef4444">Log stream disconnected. Refresh to reconnect.</div>';
        }};
    </script>
</body>
</html>
    """


# ── Admin Logs Endpoint ───────────────────────────────────────────────────────
@app.get("/admin/logs", response_class=HTMLResponse)
def admin_logs_page():
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - Live Logs</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Consolas', 'Monaco', monospace;
            background: #0d1117;
            color: #c9d1d9;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #30363d;
        }
        h1 {
            font-size: 24px;
            color: #58a6ff;
        }
        .controls {
            display: flex;
            gap: 10px;
        }
        button {
            background: #238636;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
        }
        button:hover {
            background: #2ea043;
        }
        .restart-btn {
            background: #da3633;
        }
        .restart-btn:hover {
            background: #f85149;
        }
        #status {
            padding: 8px 12px;
            background: #1f6feb;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        }
        #logs {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 15px;
            height: calc(100vh - 140px);
            overflow-y: auto;
            font-size: 13px;
            line-height: 1.6;
        }
        .log-line {
            padding: 2px 0;
            border-bottom: 1px solid #21262d;
        }
        .log-line:last-child {
            border-bottom: none;
        }
        .timestamp {
            color: #8b949e;
            margin-right: 8px;
        }
        #logs::-webkit-scrollbar {
            width: 10px;
        }
        #logs::-webkit-scrollbar-track {
            background: #0d1117;
        }
        #logs::-webkit-scrollbar-thumb {
            background: #30363d;
            border-radius: 5px;
        }
        #logs::-webkit-scrollbar-thumb:hover {
            background: #484f58;
        }
        .confirmation {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #161b22;
            border: 2px solid #30363d;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
            display: none;
            z-index: 1000;
        }
        .confirmation.show {
            display: block;
        }
        .confirmation h2 {
            color: #f85149;
            margin-bottom: 15px;
        }
        .confirmation p {
            margin-bottom: 20px;
            color: #8b949e;
        }
        .confirmation .buttons {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
        }
        .cancel-btn {
            background: #6e7681;
        }
        .cancel-btn:hover {
            background: #8b949e;
        }
        .overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            display: none;
            z-index: 999;
        }
        .overlay.show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔧 Admin - Live Logs</h1>
        <div class="controls">
            <span id="status">● Connected</span>
            <button onclick="clearLogs()">Clear Logs</button>
            <button class="restart-btn" onclick="showRestartConfirm()">🔄 Restart App</button>
        </div>
    </div>
    <div id="logs"></div>
    
    <div class="overlay" id="overlay" onclick="hideRestartConfirm()"></div>
    <div class="confirmation" id="confirmDialog">
        <h2>⚠️ Restart Application?</h2>
        <p>This will kill the current process and restart the app using start-app-ngrok.ps1</p>
        <div class="buttons">
            <button class="cancel-btn" onclick="hideRestartConfirm()">Cancel</button>
            <button class="restart-btn" onclick="confirmRestart()">Yes, Restart Now</button>
        </div>
    </div>

    <script>
        const logsDiv = document.getElementById('logs');
        const statusSpan = document.getElementById('status');
        let eventSource;
        let autoScroll = true;

        // Auto-scroll detection
        logsDiv.addEventListener('scroll', () => {
            const isAtBottom = logsDiv.scrollHeight - logsDiv.scrollTop <= logsDiv.clientHeight + 50;
            autoScroll = isAtBottom;
        });

        function connectLogs() {
            eventSource = new EventSource('/admin/logs/stream');
            
            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.line) {
                    const line = document.createElement('div');
                    line.className = 'log-line';
                    line.textContent = data.line;
                    logsDiv.appendChild(line);
                    
                    // Keep only last 200 lines in DOM
                    while (logsDiv.children.length > 200) {
                        logsDiv.removeChild(logsDiv.firstChild);
                    }
                    
                    if (autoScroll) {
                        logsDiv.scrollTop = logsDiv.scrollHeight;
                    }
                }
            };
            
            eventSource.onerror = () => {
                statusSpan.textContent = '● Reconnecting...';
                statusSpan.style.background = '#f85149';
                setTimeout(() => {
                    eventSource.close();
                    connectLogs();
                }, 2000);
            };
            
            eventSource.onopen = () => {
                statusSpan.textContent = '● Connected';
                statusSpan.style.background = '#1f6feb';
            };
        }

        function clearLogs() {
            logsDiv.innerHTML = '';
        }

        function showRestartConfirm() {
            document.getElementById('overlay').classList.add('show');
            document.getElementById('confirmDialog').classList.add('show');
        }

        function hideRestartConfirm() {
            document.getElementById('overlay').classList.remove('show');
            document.getElementById('confirmDialog').classList.remove('show');
        }

        async function confirmRestart() {
            hideRestartConfirm();
            try {
                const response = await fetch('/admin/restart', { method: 'POST' });
                const data = await response.json();
                alert(data.message || 'Restart triggered!');
            } catch (error) {
                alert('Error triggering restart: ' + error.message);
            }
        }

        // Start connection
        connectLogs();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html)


@app.get("/admin/logs/stream")
async def admin_logs_stream():
    import asyncio
    async def event_stream():
        q = asyncio.Queue()
        _log_clients.append(q)
        
        # Send existing logs first
        for log_line in _logs:
            yield f"data: {{\"line\": {json.dumps(log_line)}}}\n\n"
        
        try:
            while True:
                try:
                    log_line = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {{\"line\": {json.dumps(log_line)}}}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"  # SSE keepalive
        except asyncio.CancelledError:
            pass
        finally:
            if q in _log_clients:
                _log_clients.remove(q)
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/admin/restart")
def admin_restart():
    """Trigger app restart using start-app-ngrok.ps1"""
    try:
        import subprocess
        # Log the restart
        logger.info("🔄 RESTART TRIGGERED via admin endpoint")
        
        # Execute restart script in background
        script_path = r"c:\Users\Vasu\Desktop\Freelancer\flipkart-screen\start-app-ngrok.ps1"
        subprocess.Popen(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", script_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        # Exit this process after a short delay
        def delayed_exit():
            time.sleep(3)  # Give script time to start ngrok
            os._exit(0)
        
        threading.Thread(target=delayed_exit, daemon=True).start()
        
        return {"ok": True, "message": "Restart triggered! App will restart in 2 seconds."}
    except Exception as e:
        logger.error(f"Restart failed: {e}")
        return {"ok": False, "message": f"Restart failed: {str(e)}"}


@app.post("/admin/toggle-auto-restart")
def toggle_auto_restart():
    """Toggle automatic 2-hour restart"""
    global _auto_restart_enabled
    _auto_restart_enabled = not _auto_restart_enabled
    status = "enabled" if _auto_restart_enabled else "disabled"
    logger.info(f"⏰ Auto-restart {status}")
    return {"ok": True, "message": f"Auto-restart {status}", "enabled": _auto_restart_enabled}


# ── Auto-restart timer ────────────────────────────────────────────────────────
def auto_restart_timer():
    """Restart app every 2 hours if enabled"""
    while True:
        time.sleep(300)  # Check every 5 minutes
        if _auto_restart_enabled:
            uptime = (datetime.now() - _app_start_time).total_seconds()
            if uptime >= 7200:  # 2 hours = 7200 seconds
                logger.info("⏰ Auto-restart triggered (2 hours uptime)")
                import subprocess
                script_path = r"c:\Users\Vasu\Desktop\Freelancer\flipkart-screen\start-app-ngrok.ps1"
                subprocess.Popen(
                    ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", script_path],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                time.sleep(2)
                os._exit(0)
 