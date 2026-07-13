"""The lab's own exam: traps must exist in the data, and the grader must
tell mock-naive (all red) from mock-oracle (all green)."""
import sqlite3

import pytest

from failure_lab import db_gen, runner
from failure_lab.guard import GuardError, guard


@pytest.fixture(scope="session")
def db():
    db_gen.main()
    conn = sqlite3.connect(db_gen.DB_PATH)
    yield conn
    conn.close()


def q1(db, sql):
    return db.execute(sql).fetchone()[0]


# --- trap preconditions (one per case family) ---------------------------

def test_null_bucket_precondition(db):
    null_orders = q1(db, "SELECT COUNT(*) FROM orders o JOIN customers c "
                         "ON c.customer_id=o.customer_id WHERE c.company_name IS NULL")
    top_company = q1(db, "SELECT COUNT(*) FROM orders o JOIN customers c "
                         "ON c.customer_id=o.customer_id GROUP BY c.company_name "
                         "HAVING c.company_name IS NOT NULL ORDER BY 1 DESC LIMIT 1")
    max_individual = q1(db, "SELECT MAX(n) FROM (SELECT COUNT(*) n FROM orders o "
                            "JOIN customers c ON c.customer_id=o.customer_id "
                            "WHERE c.company_name IS NULL GROUP BY o.customer_id)")
    assert null_orders > top_company, "NULL bucket must outrank every company"
    assert max_individual < 14, "no single individual may reach the top 10"


def test_fanout_precondition(db):
    multi = q1(db, "SELECT COUNT(*) FROM (SELECT order_id FROM order_items "
                   "GROUP BY order_id HAVING COUNT(*) > 1)")
    assert multi > 50, "need plenty of multi-item orders for fan-out"


def test_growth_divergence(db):
    rows = db.execute(
        "SELECT c.name, "
        " COUNT(DISTINCT CASE WHEN o.order_date LIKE '2024-%' THEN o.order_id END),"
        " COUNT(DISTINCT CASE WHEN o.order_date LIKE '2025-%' THEN o.order_id END) "
        "FROM categories c JOIN products p ON p.category_id=c.category_id "
        "JOIN order_items oi ON oi.product_id=p.product_id "
        "JOIN orders o ON o.order_id=oi.order_id GROUP BY c.name").fetchall()
    abs_winner = max(rows, key=lambda r: r[2] - r[1])[0]
    pct_winner = max(rows, key=lambda r: (r[2] - r[1]) / r[1])[0]
    assert abs_winner == "electronics" and pct_winner == "garden"
    assert abs_winner != pct_winner


def test_ties_precondition(db):
    units = [r[0] for r in db.execute(
        "SELECT SUM(oi.quantity) u FROM products p "
        "JOIN order_items oi ON oi.product_id=p.product_id "
        "JOIN orders o ON o.order_id=oi.order_id "
        "WHERE p.category_id=(SELECT category_id FROM categories WHERE name='toys') "
        "AND o.order_date LIKE '2025-%' GROUP BY p.name ORDER BY u DESC").fetchall()]
    assert units[2] == units[3], "rank 3 must be an exact tie"
    assert units[1] > units[2], "the tie must sit exactly at the boundary"


def test_empty_and_missing_period(db):
    dec_books = q1(db, "SELECT COUNT(*) FROM orders o "
                       "JOIN order_items oi ON oi.order_id=o.order_id "
                       "JOIN products p ON p.product_id=oi.product_id "
                       "WHERE p.category_id=(SELECT category_id FROM categories WHERE name='books') "
                       "AND o.order_date LIKE '2025-12-%'")
    feb_garden = q1(db, "SELECT COUNT(*) FROM orders o "
                        "JOIN order_items oi ON oi.order_id=o.order_id "
                        "JOIN products p ON p.product_id=oi.product_id "
                        "WHERE p.category_id=(SELECT category_id FROM categories WHERE name='garden') "
                        "AND o.order_date LIKE '2025-02-%'")
    garden_months = q1(db, "SELECT COUNT(DISTINCT substr(o.order_date,1,7)) FROM orders o "
                           "JOIN order_items oi ON oi.order_id=o.order_id "
                           "JOIN products p ON p.product_id=oi.product_id "
                           "WHERE p.category_id=(SELECT category_id FROM categories WHERE name='garden') "
                           "AND o.order_date LIKE '2025-%'")
    assert dec_books == 0 and feb_garden == 0 and garden_months == 11


def test_entity_type_invariants(db):
    by_null = q1(db, "SELECT COUNT(*) FROM customers WHERE company_name IS NULL")
    by_type = q1(db, "SELECT COUNT(*) FROM customers WHERE entity_type IN (7,8)")
    ghost = q1(db, "SELECT COUNT(*) FROM customers WHERE entity_type IN (1,2)")
    assert by_null == by_type, "two definitions of individual must coincide"
    assert ghost == 0, "codes 1/2 must not exist (enum_code_guess)"


def test_scope_predicate_precondition(db):
    totals_cte = ("WITH ot AS (SELECT o.order_id, SUM(oi.quantity*p.price) t "
                  "FROM orders o JOIN order_items oi ON oi.order_id=o.order_id "
                  "JOIN products p ON p.product_id=oi.product_id "
                  "WHERE o.order_date LIKE '2025-%' GROUP BY o.order_id) ")
    all_2025 = q1(db, "SELECT COUNT(*) FROM orders WHERE order_date LIKE '2025-%'")
    high_value = q1(db, totals_cte + "SELECT COUNT(*) FROM ot WHERE t > 500")
    premium = q1(db, "SELECT COUNT(DISTINCT o.order_id) FROM orders o "
                     "JOIN order_items oi ON oi.order_id=o.order_id "
                     "WHERE o.order_date LIKE '2025-%' AND oi.product_id IN (8,12,24)")
    # No order total lands in the OPEN gap (360, 900): regular orders top out
    # at 360, premium orders start at 900, so the > 500 threshold is robust to
    # any value in between. (Orders sit at exactly 900 when a premium item is
    # bought alone at qty 1 — still comfortably high-value.)
    gap = q1(db, totals_cte + "SELECT COUNT(*) FROM ot WHERE t > 360 AND t < 900")
    assert all_2025 == 399
    # 47 = the 46 premium-tier orders + the one outsized top_n_ties host order,
    # which is legitimately high-value too. The naive "count all 2025" answer
    # (399) dwarfs it by ~8x, which is the whole tell.
    assert high_value == 47, "high-value orders must be a clear minority of 2025"
    assert premium == 46, "the premium tier drives all but the ties host order"
    assert high_value * 5 < all_2025, "naive (all orders) must dwarf the filtered answer"
    assert gap == 0, "clean gap: no order total between regular-max and premium-min"


# --- the grader's entrance exam ------------------------------------------

def test_mock_naive_all_fail(db):
    report = runner.run("mock-naive")
    assert report["summary"]["fail"] == report["summary"]["total"]


def test_mock_oracle_all_pass(db):
    report = runner.run("mock-oracle")
    assert report["summary"]["pass"] == report["summary"]["total"]


# --- guard basics ----------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "DROP TABLE orders", "SELECT 1; SELECT 2",
    "PRAGMA schema_version", "ATTACH DATABASE 'x' AS y",
    "INSERT INTO orders VALUES (1,1,'2025-01-01')",
])
def test_guard_rejects(bad):
    with pytest.raises(GuardError):
        guard(bad)


def test_guard_allows_select_and_cte():
    guard("SELECT 1")
    guard("WITH t AS (SELECT 1 AS x) SELECT x FROM t")


# --- report hygiene ---------------------------------------------------------

def test_error_redaction_scrubs_connection_details():
    msg = ("HTTPError: POST https://10.0.0.7:8443/v1/chat failed "
           "(key sk-abc12345678, upstream 192.168.1.5:11434)")
    scrubbed = runner.redact(msg)
    assert "10.0.0.7" not in scrubbed
    assert "sk-abc12345678" not in scrubbed
    assert "192.168.1.5" not in scrubbed
    assert "HTTPError" in scrubbed  # error type survives for debugging
