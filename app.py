import json
import re
import time
import queue
import threading
import certifi
import requests as req
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from pymongo import MongoClient, ASCENDING, DESCENDING

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = "8953384321:AAGwWwD-7fkcR7hIMYrIxm-m8wZfXpKbKAs"
TELEGRAM_CHAT_ID = "1124426595"  # Vasu
MONGO_URI        = "mongodb+srv://vasu4651_db_user:8Jgyc1ZaTDw5Y5cn@cluster0.rt55a2o.mongodb.net/?appName=Cluster0"

# ── MongoDB ───────────────────────────────────────────────────────────────────
_mongo    = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
_db       = _mongo["flipkart"]
_col      = _db["price_history"]   # {pid, name, url, ts, fsp, nep}
_col_pids = _db["products"]        # {pid, name, url}

# ── Shared state ──────────────────────────────────────────────────────────────
_state    = {}   # pid → latest snapshot
_last     = {}   # pid → {price, lowest_price} for change detection
_baseline = {}   # pid → {price, lowest_price} seeded from last MongoDB record
_records  = {}   # pid → {high, low} all-time records
_alerts   = []
_clients  = []
_lock     = threading.Lock()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}
BASE_URL = "https://www.flipkart.com/product/p/itm?pid={pid}"


# ── MongoDB helpers ───────────────────────────────────────────────────────────
def load_products():
    return list(_col_pids.find({}, {"_id": 0, "pid": 1, "name": 1, "url": 1}))


def load_baseline():
    for item in load_products():
        pid = item["pid"]
        doc = _col.find_one({"pid": pid}, sort=[("ts", DESCENDING)])
        if doc:
            _baseline[pid] = {
                "price":        doc.get("fsp"),
                "lowest_price": doc.get("nep"),
            }
        # Load all-time high (fsp) and low (nep) from history
        high_doc = _col.find_one({"pid": pid, "fsp": {"$ne": None}}, sort=[("fsp", DESCENDING)])
        low_doc  = _col.find_one({"pid": pid, "nep": {"$ne": None}}, sort=[("nep", ASCENDING)])
        _records[pid] = {
            "high": high_doc.get("fsp") if high_doc else None,
            "low":  low_doc.get("nep")  if low_doc  else None,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────
def send_telegram(msg: str):
    if not TELEGRAM_TOKEN:
        return
    try:
        r = req.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5,
        )
        print(f"[Telegram] status={r.status_code} ok={r.json().get('ok')} err={r.json().get('description','')}", flush=True)
    except Exception as e:
        print(f"[Telegram] ERROR: {e}", flush=True)


def broadcast(payload: dict):
    data = json.dumps(payload)
    with _lock:
        dead = []
        for q in _clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _clients.remove(q)


# ── Background scraper ────────────────────────────────────────────────────────
def scrape_loop():
    i = 0
    while True:
        products = load_products()
        if not products:
            time.sleep(2)
            continue

        item = products[i % len(products)]
        i += 1

        pid  = item["pid"]
        name = item.get("name", pid)
        url  = item.get("url", "")
        ts   = datetime.now().strftime("%H:%M:%S")

        rec = _records.get(pid, {})
        snapshot = {
            "pid": pid, "name": name, "url": url,
            "price": None, "lowest_price": None,
            "price_prev": None, "lowest_prev": None,
            "price_dir": None,  "lowest_dir": None,
            "all_time_high": rec.get("high"),
            "all_time_low":  rec.get("low"),
            "http_status": None, "size_kb": 0,
            "status": "PENDING", "ts": ts,
        }

        try:
            resp = req.get(BASE_URL.format(pid=pid), headers=HEADERS, timeout=10)
            snapshot["http_status"] = resp.status_code
            snapshot["size_kb"]     = round(len(resp.text) / 1024, 1)

            if resp.status_code == 200 and len(resp.text) > 5000:
                ppd_m = re.search(r'"ppd":\{([^}]+)\}', resp.text)
                ppd = {}
                if ppd_m:
                    try:
                        ppd = json.loads('{' + ppd_m.group(1) + '}')
                    except Exception:
                        pass

                price  = ppd.get("fsp")
                lowest = ppd.get("nepPrice")
                snapshot["price"]        = price
                snapshot["lowest_price"] = lowest
                snapshot["status"]       = "OK" if (price or lowest) else "NO_PRICE"

                if price or lowest:
                    _col.insert_one({
                        "pid":  pid,
                        "name": name,
                        "url":  url,
                        "ts":   datetime.now(timezone.utc),
                        "fsp":  price,
                        "nep":  lowest,
                    })

                last = _last.get(pid, _baseline.get(pid, {}))
                alerts_to_send = []

                if price is not None:
                    prev = last.get("price")
                    if prev is not None and price != prev:
                        d = "DOWN" if price < prev else "UP"
                        snapshot["price_prev"] = prev
                        snapshot["price_dir"]  = d
                        emoji = "📉" if d == "DOWN" else "📈"
                        alerts_to_send.append(
                            f"{emoji} <b>{name}</b>\nPrice: ₹{prev:,} → ₹{price:,}"
                        )

                if lowest is not None:
                    prev = last.get("lowest_price")
                    if prev is not None and lowest != prev:
                        d = "DOWN" if lowest < prev else "UP"
                        snapshot["lowest_prev"] = prev
                        snapshot["lowest_dir"]  = d
                        emoji = "📉" if d == "DOWN" else "📈"
                        alerts_to_send.append(
                            f"{emoji} <b>{name}</b>\nLowest: ₹{prev:,} → ₹{lowest:,}"
                        )

                for msg in alerts_to_send:
                    send_telegram(msg)
                    _alerts.append({"ts": ts, "pid": pid, "name": name, "msg": msg})
                    if len(_alerts) > 100:
                        _alerts.pop(0)

                _last[pid] = {"price": price, "lowest_price": lowest}
                if pid not in _baseline:
                    _baseline[pid] = {"price": price, "lowest_price": lowest}

                # Update all-time records
                rec = _records.setdefault(pid, {"high": None, "low": None})
                if price is not None and (rec["high"] is None or price > rec["high"]):
                    rec["high"] = price
                if lowest is not None and (rec["low"] is None or lowest < rec["low"]):
                    rec["low"] = lowest
                snapshot["all_time_high"] = rec["high"]
                snapshot["all_time_low"]  = rec["low"]

            else:
                snapshot["status"] = (
                    "BLOCKED" if resp.status_code == 200 else f"HTTP {resp.status_code}"
                )

        except req.exceptions.Timeout:
            snapshot["status"] = "TIMEOUT"
        except Exception as e:
            snapshot["status"] = f"ERROR: {type(e).__name__}"

        _state[pid] = snapshot
        broadcast({"type": "product", "data": snapshot})
        time.sleep(1)


HEARTBEAT_INTERVAL = 60 * 2  # every 2 minutes


def heartbeat_loop():
    time.sleep(30)  # wait for first scrape cycle to complete
    while True:
        try:
            products = load_products()
            lines = [f"✅ <b>Flipkart Monitor running</b>"]
            lines.append(f"🕐 {datetime.now().strftime('%H:%M')} · {len(products)} products tracked\n")

            for p in products:
                snap = _state.get(p["pid"], {})
                price  = snap.get("price")
                lowest = snap.get("lowest_price")
                name   = p.get("name", p["pid"])
                p_str  = f"₹{price:,}" if price else "—"
                l_str  = f"₹{lowest:,}" if lowest else "—"
                lines.append(f"• {name}\n  Price: {p_str}  |  Lowest: {l_str}")

            recent = [a for a in _alerts if True][-5:]  # last 5 alerts
            if recent:
                lines.append("\n🔔 <b>Recent changes:</b>")
                for a in recent:
                    lines.append(f"  [{a['ts']}] {a['name']}: {a['msg'].split(chr(10))[-1]}")
            else:
                lines.append("\n— No price changes since last update")

            send_telegram("\n".join(lines))
        except Exception:
            pass
        time.sleep(HEARTBEAT_INTERVAL)


# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    _col.create_index([("pid", ASCENDING), ("ts", DESCENDING)])
    _col_pids.create_index("pid", unique=True)
    load_baseline()
    threading.Thread(target=scrape_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)


# ── Request models ────────────────────────────────────────────────────────────
class AddProduct(BaseModel):
    pid:  str
    name: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/hello")
def hello():
    return {"ok": True, "ts": datetime.now().isoformat()}


@app.get("/test-telegram")
def test_telegram():
    send_telegram("🔔 <b>Test</b> — Flipkart Monitor is working!")
    return {"sent": True}


@app.get("/products")
def get_products():
    return list(_state.values())


@app.post("/products")
def add_product(body: AddProduct):
    pid  = body.pid.strip().upper()
    name = body.name.strip() or pid
    url  = f"https://www.flipkart.com/product/p/itm?pid={pid}"
    if not pid:
        raise HTTPException(status_code=400, detail="PID is required")
    if _col_pids.find_one({"pid": pid}):
        raise HTTPException(status_code=409, detail="Product is already being tracked")

    _col_pids.insert_one({"pid": pid, "name": name, "url": url})
    return {"ok": True, "pid": pid, "name": name, "url": url}


@app.get("/history/{pid}")
def get_history(pid: str, limit: int = 60):
    docs = list(_col.find(
        {"pid": pid},
        {"_id": 0, "ts": 1, "fsp": 1, "nep": 1},
        sort=[("ts", DESCENDING)],
        limit=limit,
    ))
    docs.reverse()
    return [{"ts": d["ts"].strftime("%H:%M"), "fsp": d.get("fsp"), "nep": d.get("nep")} for d in docs]


@app.get("/alerts")
def get_alerts():
    return list(reversed(_alerts))


@app.get("/stream")
def stream():
    q: queue.Queue = queue.Queue(maxsize=200)
    with _lock:
        _clients.append(q)
    for snap in list(_state.values()):
        try:
            q.put_nowait(json.dumps({"type": "product", "data": snap}))
        except queue.Full:
            break

    def generator():
        try:
            while True:
                try:
                    yield f"data: {q.get(timeout=30)}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
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