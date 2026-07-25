# Project Context

Living design/behavior reference for the Flipkart price-tracker (`app.py`). Update
this file whenever alerting, timestamp, or persistence logic changes — it exists
so future sessions don't have to re-derive intended behavior from scratch.

## Storage
- MongoDB Atlas, db `flipkart`.
- `_col` (aka `price_history`): one doc per price *change* — `pid`, `name`, `url`,
  `ts` (first seen, UTC), `ts_last` (most recently confirmed, UTC), `fsp`, `nep`.
  Same fsp+nep just bumps `ts_last` instead of inserting a new doc.
- `_col_pids` (aka `products`): one doc per tracked product — `pid`, `name`, `url`,
  `lid`, `target_lowest` (optional int), `last_alert_nep` (optional int, see below).
- `MongoClient` is created **without** `tz_aware=True`, so pymongo returns naive
  Python `datetime` objects for BSON dates even though the underlying value is UTC.
  Anything read from Mongo and sent to the browser as JSON must have `+00:00`
  appended explicitly (see `_utc_iso()` in `/api/history/{pid}`) or the dashboard
  (which does its own explicit IST conversion) will double-shift the time and
  display it hours in the future/past.

## Alerting logic (target-based alerts)
Goal: alert exactly once per genuinely new "price reached target" event — never
spam duplicates, never permanently go silent.

State: `last_alert_nep` on the product doc — the NEP value we last alerted on
for the *current* target-qualifying streak. `None` means "not currently in an
alerted streak."

Each scrape cycle, when `target_lowest` is set:
- **Fires** when `lowest <= target_lowest AND lowest != last_alert_nep`. On fire,
  `last_alert_nep` is set to `lowest`.
- **Resets** (`last_alert_nep -> None`) the moment `lowest > target_lowest` (single
  observation, no debounce — see "Accepted trade-offs" below). This lets a later
  return to the same qualifying price re-alert instead of being silently
  suppressed forever.
- Editing/removing the target does **not** wipe price history or `_last` (that
  used to happen and caused spurious duplicate alerts from stale-baseline
  comparisons — fixed 2026-07-25). Removing a target (`target_lowest -> None`)
  also clears `last_alert_nep` back to `None`, so re-adding a target later is a
  clean slate.
- Editing the target to a *different* value while price already qualifies does
  **not** clear `last_alert_nep` directly — only the runtime "lowest >
  target_lowest" check can clear it. This is intentional: it's what prevents a
  pure target edit (with no real price movement) from causing a duplicate alert.

When no `target_lowest` is set: alert on any `price_changed or lowest_changed`
(simple change-detection, unrelated to the above).

### Accepted trade-offs (explicitly decided, not oversights)
- No consecutive-cycle/time debounce on the "reset when above target" check.
  Flipkart's known offer-count flakiness (returning e.g. 3 offers instead of 9,
  shifting computed NEP above/below target on alternating scrapes) is
  deliberately treated as genuine data per product owner's decision
  (2026-07-25) — accept the possibility of an extra alert rather than add
  complexity to filter it out.
- A rapid target edit-then-revert (e.g. lower then raise back within the same
  scrape pass) is naturally protected against because `load_products()` takes
  one Mongo snapshot per full pass — edits landing after the snapshot but before
  this pid is reached aren't seen until the next pass. An edit-then-revert that
  spans a full pass boundary is not specially guarded against; considered
  acceptable given it requires a deliberate rapid double-edit on the same
  product.

## Timestamps
- All Mongo-stored timestamps are UTC (`datetime.now(timezone.utc)`), but stored
  naive (no tzinfo) once round-tripped through pymongo — see Storage section.
- `/api/history/{pid}` uses `_utc_iso()` to append `+00:00` before serializing.
- `dashboard.html` converts to IST for display (`toLocaleTimeString('en-IN',
  {timeZone: 'Asia/Kolkata'})`) — do not change this without also checking the
  backend is still sending a properly-marked UTC ISO string.

## Restart safety
- `auto_restart_timer()` restarts the process roughly every 60-61 minutes;
  `load_baseline()` re-syncs in-memory state from Mongo on every startup.
- Anything that must survive a restart (like alert dedup state) must be
  persisted to Mongo — in-memory-only flags/sets are lost on every restart.

## Known non-issues / minor lag (not currently addressed)
- `products_sorted` (and each item's `target_lowest`) is only refreshed once per
  full scrape pass (`load_products()` at the top of the loop). A target edit
  mid-pass won't be seen by that pid until the next pass. Low impact given pass
  duration is typically well under a minute.
