# Changelog

## 2026-07-25

### Fixed
- **Price History wrong timestamps**: `/api/history` was returning MongoDB `ts`/`ts_last` values without a UTC marker. Browsers (running in IST) misinterpreted the bare timestamp as local time, then the dashboard's explicit IST conversion shifted it again — the two errors cancelled out and displayed the raw UTC clock value as IST, making times appear ~5.5 hours in the future (e.g. "Today 07:26 pm" shown when it was actually ~1:56 pm). Fixed by explicitly appending `+00:00` to naive UTC datetimes before serializing.
- **Duplicate/spurious TARGET HIT alerts on target edit**: Editing a product's target price used to call `_last.pop(pid)` and `_col.delete_many({"pid": pid})`, wiping the in-memory last-known price and all Mongo price history for that product. The next scrape would then compare against a stale fallback baseline, often triggering a duplicate alert with no real price change, and permanently erasing that product's price history graph.
  - Replaced with a persisted `last_alert_nep` field per product (stored in `_col_pids`), updated only when an alert actually fires for a target-based product.
  - Target-based alerts now fire only when `lowest <= target_lowest AND lowest != last_alert_nep` — i.e. only when this exact qualifying price hasn't already been reported, regardless of whether it's the same live price as last cycle.
  - This also fixes duplicate alerts caused by Flipkart intermittently returning an incomplete offers list (e.g. 3 vs 9 offers) for the same product, which previously caused NEP to flicker above/below target and re-fire alerts on every recovery.
  - Editing or removing a target no longer deletes Mongo price history or resets `_last`.

## 2026-07-24

### Fixed
- **Skip-on-no-offers logic firing too late**: `skip_product_no_offers` flag was set when both the live scrape and its retry returned no bank offers, but the `continue` that should skip Mongo writes/alerts was placed near the end of the loop body — after those writes/alerts had already executed. Replaced with an early `continue` immediately after the no-offers condition is detected, so no Mongo write, alert, or state update happens for that product/cycle.

### Added
- One-time live retry when a scrape returns zero bank offers, before deciding to skip the product for that cycle.
