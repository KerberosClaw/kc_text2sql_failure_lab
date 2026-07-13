"""Deterministic demo database generator.

Every trap the cases rely on is *engineered into the data* here, and each
trap block is labelled with the case id that depends on it. Rebuilding with
`make db` produces a byte-identical database on any machine (fixed seed,
constructive allocation — randomness only decorates names and dates).

Trap map
--------
null_bucket_ranking : individuals carry company_name=NULL; their combined
                      order count beats every company, but no single
                      individual reaches the top 10.
join_fanout_count   : ~1/3 of orders contain 2-3 items of the *same*
                      category, so COUNT(order_id) over an item join
                      inflates while COUNT(DISTINCT order_id) does not.
growth_definition   : electronics grows most in absolute orders
                      (+18, +15%), garden grows most in percentage
                      (+15, +125%). Absolute winner != percentage winner.
top_n_ties          : two toy products tie exactly at rank 3 by units
                      sold in 2025.
empty_vs_zero       : books has zero orders in December 2025 (every other
                      category has at least one).
missing_period      : garden has zero orders in February 2025 but orders
                      in all other months of 2025.
entity_type_ignored : corporate and nonprofit rows also carry a contact
                      person in full_name, so "full_name IS NOT NULL" is
                      a wrong definition of "individual customer" — the
                      fake-individual leaderboard is topped by companies.
enum_code_guess     : entity_type codes are 3/5/7/8 (documented in the
                      DDL comment); codes 1 and 2 do not exist. Guessing
                      `entity_type = 1` returns zero rows that look like
                      "no data". entity_type IN (7,8) coincides exactly
                      with company_name IS NULL (cross-check invariant).
scope_predicate_drop: a small premium tier of products (PREMIUM_PIDS) is
                      priced far above the rest (900 vs <=30), so an order's
                      *total* value (sum of quantity*price) crosses the
                      high-value line (> 500) whenever it contains a premium
                      item. 47 of the 399 orders in 2025 clear the line: 46
                      from this premium tier, plus the single outsized
                      top_n_ties host order (hundreds of toy units), which is
                      high-value in its own right. There is no order-total
                      column, so the scope filter has to be derived — a weak
                      model drops it and counts all 399 instead.
"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "demo.db"
SEED = 20260710

SCHEMA = """
CREATE TABLE categories (
  category_id INTEGER PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE  -- lowercase: electronics, furniture, groceries, toys, books, garden
);
CREATE TABLE products (
  product_id  INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,
  category_id INTEGER NOT NULL REFERENCES categories(category_id),
  price       REAL NOT NULL
);
CREATE TABLE customers (
  customer_id  INTEGER PRIMARY KEY,
  full_name    TEXT NOT NULL,    -- contact person; populated for ALL rows, including companies
  company_name TEXT,             -- NULL for individual buyers (trap: null_bucket_ranking)
  entity_type  INTEGER NOT NULL  -- 3=corporation, 5=nonprofit organization, 7=individual, 8=individual (legacy import)
);
CREATE TABLE orders (
  order_id    INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
  order_date  TEXT NOT NULL      -- ISO YYYY-MM-DD
);
CREATE TABLE order_items (
  item_id    INTEGER PRIMARY KEY,
  order_id   INTEGER NOT NULL REFERENCES orders(order_id),
  product_id INTEGER NOT NULL REFERENCES products(product_id),
  quantity   INTEGER NOT NULL
);
"""

CATEGORIES = ["electronics", "furniture", "groceries", "toys", "books", "garden"]

# Distinct orders containing the category, per year.  (growth_definition,
# empty_vs_zero and missing_period are all encoded in these numbers plus
# the month rules below.)
CATEGORY_ORDERS = {
    #               2024  2025
    "electronics": (120, 138),   # +18 absolute winner (+15%)
    "furniture":   (60,  63),
    "groceries":   (90,  96),
    "toys":        (45,  42),
    "books":       (36,  33),    # zero in Dec 2025 (empty_vs_zero)
    "garden":      (12,  27),    # +15, +125% percentage winner; zero in Feb 2025
}

FIRST = ["Ada", "Ben", "Cleo", "Dmitri", "Erika", "Farid", "Grace", "Henry",
         "Iris", "Jonas", "Kira", "Liam", "Mona", "Nils", "Opal", "Priya",
         "Quinn", "Rosa", "Sven", "Tara"]
LAST = ["Alder", "Brook", "Cho", "Duarte", "Egner", "Fujii", "Grant",
        "Hansen", "Ivanov", "Jensen", "Kaur", "Lindt", "Moreau", "Novak",
        "Okafor", "Petit", "Quist", "Ricci", "Sato", "Tan"]
COMPANY_WORDS = ["Acme", "Borealis", "Cobalt", "Deltoid", "Evergreen",
                 "Fathom", "Gadgetron", "Harbor", "Ionize", "Juniper",
                 "Krypton", "Lumen", "Meridian", "Nimbus", "Orchid",
                 "Pylon", "Quartz", "Rustic", "Solstice", "Tundra"]
COMPANY_SUFFIX = ["Ltd", "Inc", "GmbH", "Co", "Group"]
PRODUCT_WORDS = {
    "electronics": ["Volt", "Pixel", "Nano", "Quantum", "Echo"],
    "furniture":   ["Oak", "Nordic", "Loft", "Curve", "Slate"],
    "groceries":   ["Farm", "Daily", "Golden", "Pure", "Morning"],
    "toys":        ["Zoom", "Blocky", "Dino", "Puzzle", "Rocket"],
    "books":       ["Atlas", "Fable", "Prism", "Chapter", "Margin"],
    "garden":      ["Bloom", "Sprout", "Terra", "Fern", "Rake"],
}

# scope_predicate_drop: a handful of products sit in a premium price tier far
# above every other product. Products are numbered 1..30 in the category order
# above (5 per category), so these ids are Loft Furniture / Daily Groceries /
# Chapter Books — one premium item in each of three categories. An order's
# total value clears HIGH_VALUE_THRESHOLD *only* if it contains one of them, so
# "high-value" is a derived predicate with no clean column to filter on. Kept
# out of the categories that carry other traps (electronics/garden growth,
# toys ties) so nothing entangles. Regular prices stay in [4, 30] so an
# ordinary order (<=3 items, qty<=4) tops out at 360, well under the 500 line;
# the only non-premium order that clears it is the top_n_ties host, padded
# with hundreds of toy units. Everything else is either <=360 or >=900, so the
# 500 threshold sits in a clean gap.
PREMIUM_PIDS = {8, 12, 24}
PREMIUM_PRICE = 900.0
HIGH_VALUE_THRESHOLD = 500       # any value in (360, 900) is equivalent


def _month_weights(category: str, year: int) -> list[int]:
    """12 relative weights; trap months get weight 0."""
    w = [3, 2, 3, 3, 2, 3, 3, 2, 3, 3, 2, 3]
    if category == "garden" and year == 2025:
        w[1] = 0          # missing_period: no February
    if category == "books" and year == 2025:
        w[11] = 0         # empty_vs_zero: no December
    return w


def _spread(total: int, weights: list[int]) -> list[int]:
    """Deterministically spread `total` across 12 months following weights,
    guaranteeing every non-zero-weight month gets at least one."""
    alive = [i for i, w in enumerate(weights) if w > 0]
    counts = [0] * 12
    for i in alive:
        counts[i] = 1
    rest = total - len(alive)
    wsum = sum(weights[i] for i in alive)
    acc = 0
    for pos, i in enumerate(alive):
        share = rest * weights[i] // wsum if pos < len(alive) - 1 else rest - acc
        counts[i] += share
        acc += share
    return counts


def build(conn: sqlite3.Connection) -> None:
    rng = random.Random(SEED)
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    # --- categories & products (5 per category) ---
    for cid, name in enumerate(CATEGORIES, start=1):
        cur.execute("INSERT INTO categories VALUES (?, ?)", (cid, name))
    pid = 0
    products_by_cat: dict[str, list[int]] = {c: [] for c in CATEGORIES}
    for cid, cat in enumerate(CATEGORIES, start=1):
        for word in PRODUCT_WORDS[cat]:
            pid += 1
            # Draw for every product so the RNG stream is unchanged; premium
            # products then override the draw (scope_predicate_drop).
            regular = round(rng.uniform(4, 30), 2)
            price = PREMIUM_PRICE if pid in PREMIUM_PIDS else regular
            cur.execute("INSERT INTO products VALUES (?, ?, ?, ?)",
                        (pid, f"{word} {cat.title()}", cid, price))
            products_by_cat[cat].append(pid)

    # --- customers -------------------------------------------------------
    # 13 top corporations + 2 nonprofit organizations with 30..14 orders each
    # (top-10 cutoff = 21), 25 small companies with 4..8, and 120
    # individuals: 5 "power buyers" (9..5 orders, distinct counts so the
    # true individual top-5 has no ties) plus 115 casual buyers (<=3).
    # Individuals sum to 294 orders -> the naive NULL bucket outranks
    # every company (trap: null_bucket_ranking).  Companies/nonprofit
    # rows carry a contact person in full_name (trap: entity_type_ignored).
    customer_rows = []           # (customer_id, full_name, company_name, entity_type)
    order_budget: list[tuple[int, int]] = []   # (customer_id, n_orders)
    cust_id = 0
    top_counts = [30, 28, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14]
    NONPROFIT = {3: "Rivermouth Community Foundation", 8: "Harborlight Charitable Trust"}  # ranks 4 & 9
    for i, n in enumerate(top_counts):
        cust_id += 1
        person = f"{FIRST[i % 20]} {LAST[(i * 3) % 20]}"
        if i in NONPROFIT:
            customer_rows.append((cust_id, person, NONPROFIT[i], 5))
        else:
            company = f"{COMPANY_WORDS[i]} {COMPANY_SUFFIX[i % 5]}"
            customer_rows.append((cust_id, person, company, 3))
        order_budget.append((cust_id, n))
    for i in range(25):
        cust_id += 1
        company = f"{COMPANY_WORDS[(i + 7) % 20]} {COMPANY_SUFFIX[(i + 2) % 5]} {i + 1}"
        person = f"{FIRST[(i + 5) % 20]} {LAST[(i * 7 + 1) % 20]}"
        customer_rows.append((cust_id, person, company, 3))
        order_budget.append((cust_id, 4 + (i % 5)))          # 4..8 -> 150 total
    individual_counts = [9, 8, 7, 6, 5] + [3] * 29 + [2] * 86   # 294 total, max 9
    for i, n in enumerate(individual_counts):
        cust_id += 1
        person = f"{FIRST[(i * 11 + 3) % 20]} {LAST[(i * 13 + 5) % 20]} {i + 1}"
        etype = 7 if i < 90 else 8                           # two individual variants
        customer_rows.append((cust_id, person, None, etype))
        order_budget.append((cust_id, n))
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", customer_rows)

    total_orders = sum(n for _, n in order_budget)
    assert total_orders == sum(a + b for a, b in CATEGORY_ORDERS.values()), \
        f"order budget {total_orders} != category demand"

    # --- orders ----------------------------------------------------------
    # Build (year, month, category) slots from category demand, then deal
    # them round-robin to customers so counts land exactly as budgeted.
    slots: list[tuple[int, int, str]] = []
    for cat, (n24, n25) in CATEGORY_ORDERS.items():
        for year, total in ((2024, n24), (2025, n25)):
            for month, cnt in enumerate(_spread(total, _month_weights(cat, year)), start=1):
                slots.extend([(year, month, cat)] * cnt)
    rng.shuffle(slots)

    deal: list[int] = []
    for cid_, n in order_budget:
        deal.extend([cid_] * n)
    rng.shuffle(deal)

    order_id = 0
    item_id = 0
    units_2025: dict[int, int] = {}
    for (year, month, cat), customer in zip(slots, deal):
        order_id += 1
        day = rng.randint(1, 28)
        cur.execute("INSERT INTO orders VALUES (?, ?, ?)",
                    (order_id, customer, f"{year}-{month:02d}-{day:02d}"))
        # items: all from the order's category; ~1/3 of orders get 2-3
        # items (same category) -> join_fanout_count fodder.
        n_items = 1 if rng.random() < 0.67 else rng.randint(2, 3)
        picks = rng.sample(products_by_cat[cat], k=min(n_items, len(products_by_cat[cat])))
        for p in picks:
            item_id += 1
            qty = rng.randint(1, 4)
            cur.execute("INSERT INTO order_items VALUES (?, ?, ?, ?)",
                        (item_id, order_id, p, qty))
            if year == 2025:
                units_2025[p] = units_2025.get(p, 0) + qty

    # --- top_n_ties: force an exact tie at rank 3 among toy products ------
    # Take the four best-selling toy products of 2025 and pin their unit
    # totals to 260 / 250 / 210 / 210 by appending adjustment items to the
    # last toy order of 2025.
    toys = sorted(products_by_cat["toys"], key=lambda p: -units_2025.get(p, 0))[:4]
    targets = [260, 250, 210, 210]
    cur.execute(
        "SELECT o.order_id FROM orders o JOIN order_items oi ON oi.order_id=o.order_id "
        "JOIN products p ON p.product_id=oi.product_id "
        "WHERE p.category_id=(SELECT category_id FROM categories WHERE name='toys') "
        "AND o.order_date LIKE '2025-%' ORDER BY o.order_date DESC LIMIT 1")
    host_order = cur.fetchone()[0]
    for prod, target in zip(toys, targets):
        gap = target - units_2025.get(prod, 0)
        assert gap > 0, "tie targets must sit above organic volume"
        item_id += 1
        cur.execute("INSERT INTO order_items VALUES (?, ?, ?, ?)",
                    (item_id, host_order, prod, gap))

    conn.commit()


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    try:
        build(conn)
        n = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        print(f"demo.db rebuilt at {DB_PATH} ({n} orders)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
