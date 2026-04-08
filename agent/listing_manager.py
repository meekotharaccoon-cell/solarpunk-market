#!/usr/bin/env python3
"""
SolarPunk Market — Listing Manager CLI.

Sellers use this to add, list, remove, and inspect listings in the
cooperative marketplace.  Reads/writes data/products.json via the
market_agent module.

Usage:
    python -m agent.listing_manager add
    python -m agent.listing_manager list
    python -m agent.listing_manager remove <id>
    python -m agent.listing_manager stats [seller]

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import argparse
import sys
from collections import defaultdict

from agent.market_agent import (
    CATEGORIES,
    add_product,
    load_products,
    load_transactions,
    save_products,
)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(args: argparse.Namespace) -> None:
    """Interactively or via flags create a new listing."""
    title = args.title or input("Title: ").strip()
    description = args.description or input("Description: ").strip()

    price_raw = args.price or input("Price (USD): ").strip()
    try:
        price = float(price_raw)
    except ValueError:
        print("Error: price must be a number.", file=sys.stderr)
        sys.exit(1)

    category = args.category or input(f"Category {CATEGORIES}: ").strip().lower()
    if category not in CATEGORIES:
        print(f"Error: category must be one of {CATEGORIES}", file=sys.stderr)
        sys.exit(1)

    seller = args.seller or input("Seller name: ").strip()
    payment = args.payment or input("Payment method [paypal]: ").strip() or "paypal"

    product = add_product(title, description, price, category, seller, payment)
    print(f"Created listing #{product['id']}: {product['title']} — ${product['price']:.2f}")


def cmd_list(_args: argparse.Namespace) -> None:
    """Show all active listings."""
    products = load_products()
    active = [p for p in products if p.get("active")]

    if not active:
        print("No active listings.")
        return

    print(f"{'ID':>4}  {'Category':<10} {'Price':>8}  {'Seller':<16} Title")
    print("-" * 70)
    for p in active:
        print(
            f"{p['id']:>4}  {p['category']:<10} ${p['price']:>7.2f}"
            f"  {p['seller']:<16} {p['title']}"
        )
    print(f"\n{len(active)} active listing(s).")


def cmd_remove(args: argparse.Namespace) -> None:
    """Deactivate a listing by ID."""
    products = load_products()
    target_id = int(args.id)
    found = False

    for p in products:
        if p["id"] == target_id:
            if not p.get("active"):
                print(f"Listing #{target_id} is already inactive.")
                return
            p["active"] = False
            found = True
            break

    if not found:
        print(f"Error: listing #{target_id} not found.", file=sys.stderr)
        sys.exit(1)

    save_products(products)
    print(f"Listing #{target_id} deactivated.")


def cmd_stats(args: argparse.Namespace) -> None:
    """Sales stats per seller (optionally filtered)."""
    txns = load_transactions()
    products = {p["id"]: p for p in load_products()}

    seller_stats: dict[str, dict] = defaultdict(
        lambda: {"sales": 0, "revenue": 0.0, "listings": 0}
    )

    # Count listings
    for p in products.values():
        if p.get("active"):
            seller_stats[p["seller"]]["listings"] += 1

    # Tally completed transactions
    for t in txns:
        if t["status"] == "complete":
            seller_stats[t["seller"]]["sales"] += 1
            seller_stats[t["seller"]]["revenue"] += t["amount"]

    if args.seller:
        sellers = {args.seller: seller_stats[args.seller]}
    else:
        sellers = dict(seller_stats)

    if not sellers:
        print("No stats to show.")
        return

    print(f"{'Seller':<20} {'Listings':>8} {'Sales':>6} {'Revenue':>10}")
    print("-" * 50)
    for name, s in sorted(sellers.items()):
        print(f"{name:<20} {s['listings']:>8} {s['sales']:>6} ${s['revenue']:>9.2f}")


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="listing_manager",
        description="SolarPunk Market — seller CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Create a new listing")
    p_add.add_argument("--title", "-t")
    p_add.add_argument("--description", "-d")
    p_add.add_argument("--price", "-p", type=float)
    p_add.add_argument("--category", "-c", choices=CATEGORIES)
    p_add.add_argument("--seller", "-s")
    p_add.add_argument("--payment", default="paypal")

    # list
    sub.add_parser("list", help="Show all active listings")

    # remove
    p_rm = sub.add_parser("remove", help="Deactivate a listing")
    p_rm.add_argument("id", help="Listing ID to deactivate")

    # stats
    p_st = sub.add_parser("stats", help="Sales stats per seller")
    p_st.add_argument("seller", nargs="?", default=None)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "add": cmd_add,
        "list": cmd_list,
        "remove": cmd_remove,
        "stats": cmd_stats,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
