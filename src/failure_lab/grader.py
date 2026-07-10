"""Result-level grading.

We never compare SQL strings — many correct SQLs exist for one question,
but only one correct answer. Rows are normalized (float tolerance, string
casing left intact) and compared according to the case's grading mode:

  ordered-set : row order matters (rankings, time series)
  set         : row order ignored
  scalar      : single value
"""
from __future__ import annotations

FLOAT_TOL = 1e-6

PASS = "pass"
WRONG_RESULT = "wrong-result"
EXEC_ERROR = "exec-error"
REFUSED = "refused"


def _norm_cell(v):
    if isinstance(v, float):
        if v == int(v):
            return int(v)
        return round(v, 6)
    return v


def _norm_rows(rows: list[tuple]) -> list[tuple]:
    return [tuple(_norm_cell(c) for c in row) for row in rows]


def grade(model_rows: list[tuple], oracle_rows: list[tuple], grading: str) -> str:
    """Return PASS or WRONG_RESULT."""
    got, want = _norm_rows(model_rows), _norm_rows(oracle_rows)
    if grading == "scalar":
        got_v = got[0][0] if got and got[0] else None
        want_v = want[0][0] if want and want[0] else None
        if isinstance(got_v, (int, float)) and isinstance(want_v, (int, float)):
            ok = abs(got_v - want_v) <= FLOAT_TOL
        else:
            ok = got_v == want_v
        return PASS if ok else WRONG_RESULT
    if grading == "set":
        return PASS if sorted(map(repr, got)) == sorted(map(repr, want)) else WRONG_RESULT
    # ordered-set (default)
    return PASS if got == want else WRONG_RESULT
