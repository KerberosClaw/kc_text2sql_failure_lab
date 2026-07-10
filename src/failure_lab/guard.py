"""Minimal, honest guardrails.

Scope (and the honesty part): these checks make SQL *safe to execute*
against the demo SQLite database. They say nothing about whether the
answer is semantically correct — that gap is the entire subject of this
repo. See SECURITY.md for what is and is not covered.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path

ROW_CAP = 10_000
TIMEOUT_S = 5.0

FORBIDDEN = re.compile(
    r"\b(ATTACH|DETACH|PRAGMA|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|"
    r"REPLACE|VACUUM|REINDEX)\b", re.I)


class GuardError(Exception):
    pass


def guard(sql: str) -> str:
    """Validate one SQL string; return it stripped or raise GuardError."""
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        raise GuardError("multiple statements are not allowed")
    if not re.match(r"^\s*(SELECT|WITH)\b", s, re.I):
        raise GuardError("only SELECT queries are allowed")
    m = FORBIDDEN.search(s)
    if m:
        raise GuardError(f"forbidden keyword: {m.group(1).upper()}")
    return s


def execute(db_path: Path, sql: str) -> tuple[list[str], list[tuple]]:
    """Run guarded SQL read-only with a wall-clock interrupt and row cap."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    timer = threading.Timer(TIMEOUT_S, conn.interrupt)
    timer.start()
    try:
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(ROW_CAP + 1)
        if len(rows) > ROW_CAP:
            raise GuardError(f"result exceeds row cap ({ROW_CAP})")
        return columns, [tuple(r) for r in rows]
    finally:
        timer.cancel()
        conn.close()
