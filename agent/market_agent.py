#!/usr/bin/env python3
"""
SolarPunk Market Agent — cooperative marketplace engine.

Maintains product catalog, tracks transactions, generates featured
listings, connects to Gumroad for digital delivery, and produces
daily market reports.  No platform cut.  Direct creator-to-buyer.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None  # graceful degradation when offline

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRODUCTS_FILE = DATA / "products.json"
TRANSACTIONS_FILE = DATA / "transactions.json"
REPORT_FILE = DATA / "daily_report.md"

CATEGORIES = ["art", "music", "writing", "code", "services", "crafts"]


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> list:
    if path.exists() and path.stat().st_size > 0:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_json(path: Path, data: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def load_products() -> list[dict]:
    return _load_json(PRODUCTS_FILE)


def save_products(products: list[dict]) -> None:
    _save_json(PRODUCTS_FILE, products)


def add_product(title: str, description: str, price: float,
                category: str, seller: str,
                payment_method: str = "paypal") -> dict:
    if category not in CATEGORIES:
        raise ValueError(f"Category must be one of {CATEGORIES}")
    products = load_products()
    product = {
        "id": len(products) + 1,
        "title": title,
        "description": description,
        "price": round(price, 2),
        "category": category,
        "seller": seller,
        "payment_method": payment_method,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    products.append(product)
    save_products(products)
    return product


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def load_transactions() -> list[dict]:
    return _load_json(TRANSACTIONS_FILE)


def save_transactions(txns: list[dict]) -> None:
    _save_json(TRANSACTIONS_FILE, txns)


def record_transaction(buyer: str, seller: str, product_id: int,
                       amount: float, status: str = "pending") -> dict:
    txns = load_transactions()
    txn = {
        "id": len(txns) + 1,
        "buyer": buyer,
        "seller": seller,
        "product_id": product_id,
        "amount": round(amount, 2),
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    txns.append(txn)
    save_transactions(txns)
    return txn


# ---------------------------------------------------------------------------
# Featured listings — recency + category diversity
# ---------------------------------------------------------------------------

def featured_listings(limit: int = 6) -> list[dict]:
    products = [p for p in load_products() if p.get("active")]
    if not products:
        return []

    # Sort by created_at descending (most recent first)
    products.sort(key=lambda p: p.get("created_at", ""), reverse=True)

    featured: list[dict] = []
    seen_categories: set[str] = set()

    # First pass: one from each category (most recent per category)
    for p in products:
        cat = p["category"]
        if cat not in seen_categories:
            featured.append(p)
            seen_categories.add(cat)
        if len(featured) >= limit:
            break

    # Second pass: fill remaining slots with most recent unseen items
    if len(featured) < limit:
        featured_ids = {p["id"] for p in featured}
        for p in products:
            if p["id"] not in featured_ids:
                featured.append(p)
            if len(featured) >= limit:
                break

    return featured[:limit]


# ---------------------------------------------------------------------------
# Gumroad integration (digital product delivery)
# ---------------------------------------------------------------------------

def gumroad_fetch_products() -> list[dict]:
    """Pull product list from Gumroad API using env credentials."""
    gumroad_id = os.getenv("GUMROAD_ID")
    gumroad_secret = os.getenv("GUMROAD_SECRET")

    if not gumroad_id or not gumroad_secret:
        print("[gumroad] GUMROAD_ID / GUMROAD_SECRET not set — skipping.")
        return []
    if requests is None:
        print("[gumroad] `requests` not installed — skipping API call.")
        return []

    try:
        resp = requests.get(
            "https://api.gumroad.com/v2/products",
            params={"access_token": gumroad_secret},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("products", [])
    except Exception as exc:
        print(f"[gumroad] API error: {exc}")
        return []


# ---------------------------------------------------------------------------
# Daily report
# ---------------------------------------------------------------------------

def generate_report() -> str:
    products = load_products()
    txns = load_transactions()
    active = [p for p in products if p.get("active")]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    by_cat: dict[str, int] = defaultdict(int)
    for p in active:
        by_cat[p["category"]] += 1

    total_volume = sum(t["amount"] for t in txns if t["status"] == "complete")
    pending = [t for t in txns if t["status"] == "pending"]

    lines = [
        f"# SolarPunk Market — Daily Report ({today})",
        "",
        f"**Active listings:** {len(active)}  ",
        f"**Total products (all-time):** {len(products)}  ",
        f"**Transactions recorded:** {len(txns)}  ",
        f"**Completed volume:** ${total_volume:,.2f}  ",
        f"**Pending transactions:** {len(pending)}  ",
        "",
        "## Listings by category",
        "",
    ]
    for cat in CATEGORIES:
        lines.append(f"- **{cat}**: {by_cat.get(cat, 0)}")

    lines += ["", "## Featured today", ""]
    for p in featured_listings(6):
        lines.append(
            f"- [{p['title']}] by {p['seller']} — ${p['price']:.2f} ({p['category']})"
        )

    gumroad_products = gumroad_fetch_products()
    if gumroad_products:
        lines += ["", "## Gumroad sync", ""]
        for gp in gumroad_products[:5]:
            lines.append(
                f"- {gp.get('name', '?')} — ${gp.get('price', 0) / 100:.2f}"
            )

    report = "\n".join(lines) + "\n"
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run() -> None:
    print("=== SolarPunk Market Agent ===")
    print(f"Data dir : {DATA}")
    print(f"Products : {len(load_products())}")
    print(f"Txns     : {len(load_transactions())}")
    print()

    report = generate_report()
    print(report)
    print(f"[agent] Report written to {REPORT_FILE}")


if __name__ == "__main__":
    run()
