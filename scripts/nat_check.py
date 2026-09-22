"""Every-30-minutes check of the "National Online Hybrid & Electric Motor
Vehicle Sale" (NAT) on pickles.com.au.

Flags 2024 Tesla Model Y, XPeng G6, and BYD SEALION 7 lots currently sitting
below a price threshold, and reports the upcoming schedule of Model Y /
SEALION 7 auctions (any sale, not just NAT) so the user can see what's coming.

IMPORTANT CAVEAT: pickles.com.au does not expose a true "hammer price" before
a lot closes (that only exists once the auction ends and the lot sells). The
closest pre-close proxy available without being logged in is `minimumBid`
(the next bid required) - `highestBid` was observed to always be null on
every lot sampled during investigation, whether or not that's because
bidding genuinely hasn't started or because it's hidden from anonymous
users is unconfirmed. This script therefore reports and thresholds against
minimumBid, and calls it out explicitly as such (never as "hammer price") in
its output.

Prints a single JSON object to stdout. Does not send notifications or touch
cron jobs itself - the calling agent turn is expected to read the JSON and
act (PushNotification on new hits, CronDelete once nat.closed is true).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import auction_client as client  # noqa: E402

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state", "nat_seen.json")

NAT_SALE_NAME = "National Online Hybrid & Electric Motor Vehicle Sale"

TARGETS = [
    # (make search path, model filter, year filter or None, price threshold)
    {"key": "model_y", "path": "/used/search/cars/tesla/model-y", "make": "TESLA", "model": "Model Y", "year": 2024, "threshold": 41000},
    {"key": "g6", "path": "/used/search/cars/xpeng", "make": "XPENG", "model": "G6", "year": None, "threshold": 37000},
    {"key": "sealion_7", "path": "/used/search/cars/byd/sealion-7", "make": "BYD", "model": "SEALION 7", "year": None, "threshold": 38000},
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
        "minimumBid": p.get("minimumBid"),
        "buyMethod": p.get("buyMethod"),
        "salvage": p.get("salvage"),
        "saleName": (sale.get("name") or "").strip(),
        "saleId": sale.get("saleId"),
        "closeUtc": p.get("productBidEnd"),
        "closeLocal": sale.get("saleEndString"),
        "suburb": loc.get("suburb"),
        "state": loc.get("state"),
        "url": client.detail_url(p),
    }


def main() -> None:
    state = load_state()
    notified = state.setdefault("notified", {})

    all_by_target: dict[str, list[dict]] = {}
    for target in TARGETS:
        html = client.fetch_html(target["path"])
        products = client.extract_products(html)
        all_by_target[target["key"]] = [summarize(p) for p in products]
        time.sleep(1)

    now = datetime.now(timezone.utc)

    # Find the current (soonest-closing) NAT sale instance from whatever we fetched.
    nat_lots_all = []
    for lots in all_by_target.values():
        nat_lots_all.extend(l for l in lots if l["saleName"] == NAT_SALE_NAME)

    current_instance = None
    if nat_lots_all:
        with_close = [l for l in nat_lots_all if l["closeUtc"]]
        if with_close:
            soonest = min(with_close, key=lambda l: l["closeUtc"])
            current_instance = {"saleId": soonest["saleId"], "closeUtc": soonest["closeUtc"], "closeLocal": soonest["closeLocal"]}

    nat_closed = False
    if current_instance:
        close_dt = datetime.fromisoformat(current_instance["closeUtc"].replace("Z", "+00:00"))
        nat_closed = now > close_dt

    # Threshold check, scoped to the NAT sale only, new hits only (dedup via state).
    hits = []
    for target in TARGETS:
        for lot in all_by_target[target["key"]]:
            if lot["salvage"] == "Salvage":
                continue
            if lot["saleName"] != NAT_SALE_NAME:
                continue
            if target["year"] is not None and lot["year"] != target["year"]:
                continue
            bid = lot["minimumBid"]
            if not bid or bid <= 0:
                continue  # 0/null means bidding hasn't opened for this lot yet
            if bid >= target["threshold"]:
                continue
            stock = lot["stockNumber"]
            if stock in notified:
                continue
            hit = dict(lot)
            hit["threshold"] = target["threshold"]
            hits.append(hit)
            notified[stock] = {"minimumBid": bid, "notified_at": now.isoformat()}

    save_state(state)

    # Upcoming schedule report for Model Y / SEALION 7 across ALL sales (not just NAT).
    def upcoming_for(key: str) -> list[dict]:
        by_sale: dict[str, dict] = {}
        for lot in all_by_target[key]:
            if lot["salvage"] == "Salvage":
                continue
            sid = lot["saleId"]
            if sid is None:
                continue
            entry = by_sale.setdefault(sid, {"saleId": sid, "saleName": lot["saleName"], "closeLocal": lot["closeLocal"], "closeUtc": lot["closeUtc"], "count": 0})
            entry["count"] += 1
        return sorted(by_sale.values(), key=lambda e: e["closeUtc"] or "")

    result = {
        "checked_at": now.isoformat(),
        "nat": {"current_instance": current_instance, "closed": nat_closed},
        "hits": hits,
        "upcoming": {
            "model_y": upcoming_for("model_y"),
            "sealion_7": upcoming_for("sealion_7"),
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
