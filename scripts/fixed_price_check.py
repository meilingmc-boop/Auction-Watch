"""Daily check of pickles.com.au fixed-price / Buy Now listings for a 2024
Tesla Model Y or a 2024/2025 BYD SEALION 7 under $41k.

Prints a single JSON object to stdout: {"checked_at": ..., "hits": [...]}.
Dedup'd against state/fixedprice_seen.json so re-running only surfaces new
qualifying listings. Does not send notifications itself.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import auction_client as client  # noqa: E402

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state", "fixedprice_seen.json")
PRICE_LIMIT = 41000

TARGETS = [
    {"path": "/used/search/cars/tesla/model-y", "years": {2024}},
    {"path": "/used/search/cars/byd/sealion-7", "years": {2024, 2025}},
]


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"notified": {}}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def summarize(p: dict) -> dict:
    sale = p.get("sale") or {}
    loc = p.get("productLocation") or {}
    return {
        "stockNumber": p.get("stockNumber"),
        "year": p.get("year"),
        "make": p.get("make"),
        "model": p.get("model"),
        "shortDescription": p.get("shortDescription"),
        "buyNowPrice": p.get("buyNowPrice"),
        "buyMethod": p.get("buyMethod"),
        "salvage": p.get("salvage"),
        "saleName": (sale.get("name") or "").strip(),
        "suburb": loc.get("suburb"),
        "state": loc.get("state"),
        "url": client.detail_url(p),
    }


def main() -> None:
    state = load_state()
    notified = state.setdefault("notified", {})
    now = datetime.now(timezone.utc)

    hits = []
    for target in TARGETS:
        html = client.fetch_html(target["path"])
        for p in client.extract_products(html):
            lot = summarize(p)
            if lot["salvage"] == "Salvage":
                continue
            if lot["year"] not in target["years"]:
                continue
            price = lot["buyNowPrice"]
            if not price or price <= 0 or price >= PRICE_LIMIT:
                continue
            stock = lot["stockNumber"]
            if stock in notified:
                continue
            hit = dict(lot)
            hit["priceLimit"] = PRICE_LIMIT
            hits.append(hit)
            notified[stock] = {"buyNowPrice": price, "notified_at": now.isoformat()}
        time.sleep(1)

    save_state(state)
    print(json.dumps({"checked_at": now.isoformat(), "hits": hits}, indent=2))


if __name__ == "__main__":
    main()
