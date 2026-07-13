"""Run all cases against a provider; grade at the result level; emit reports.

Outputs:
  reports/<provider-or-model>.json   — machine-readable scorecard
  web/data/cases.json                — gallery data (with --export-web)
  web/data/reports/*.json            — scorecards copied for the gallery
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

import yaml

from . import db_gen
from .grader import EXEC_ERROR, PASS, REFUSED, grade
from .guard import GuardError, execute, guard
from .providers import PROMPT_TEMPLATE, ProviderError, get_provider

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "cases"
REPORTS_DIR = ROOT / "reports"
WEB_DATA = ROOT / "web" / "data"

# Provider errors can quote whatever environment the model ran in — endpoint
# URLs, host addresses, API keys. Reports get copied into tracked web/data/,
# so connection details are scrubbed before anything is written to disk.
_REDACTIONS = [
    (re.compile(r"https?://[^\s\"']+"), "<redacted-url>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<redacted-address>"),
    (re.compile(r"\b(?:sk|key|token)-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
     "<redacted-key>"),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def load_cases() -> list[dict]:
    cases = []
    for path in sorted(CASES_DIR.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            cases.append(yaml.safe_load(f))
    if not cases:
        raise SystemExit("no cases found")
    return cases


def ensure_db() -> Path:
    if not db_gen.DB_PATH.exists():
        db_gen.main()
    return db_gen.DB_PATH


def oracle_rows(case: dict, db: Path) -> list[tuple]:
    _, rows = execute(db, guard(case["oracle"]["sql"]))
    return rows


def run(provider_name: str) -> dict:
    provider = get_provider(provider_name)
    db = ensure_db()
    prompt_hash = hashlib.sha256(
        (PROMPT_TEMPLATE + db_gen.SCHEMA).encode()).hexdigest()[:12]
    results = []
    for case in load_cases():
        entry: dict = {"id": case["id"], "category": case["category"],
                       "title": case["title"]}
        t0 = time.time()
        try:
            sql = provider.generate_sql(case, db_gen.SCHEMA)
            entry["sql"] = sql
            _, rows = execute(db, guard(sql))
            want = oracle_rows(case, db)
            entry["status"] = grade(rows, want, case["oracle"].get("grading", "ordered-set"))
            entry["rows_returned"] = len(rows)
        except (GuardError, ProviderError) as e:
            entry["status"] = REFUSED if isinstance(e, ProviderError) else EXEC_ERROR
            entry["error"] = redact(str(e))
        except Exception as e:  # execution failure on generated SQL
            entry["status"] = EXEC_ERROR
            entry["error"] = redact(f"{type(e).__name__}: {e}")
        entry["latency_ms"] = int((time.time() - t0) * 1000)
        results.append(entry)
        mark = "PASS" if entry["status"] == PASS else entry["status"].upper()
        print(f"  {mark:>12}  {case['id']}")
    passed = sum(1 for r in results if r["status"] == PASS)
    report = {"provider": provider.name, "model": provider.model,
              "prompt_hash": prompt_hash,
              "summary": {"pass": passed, "fail": len(results) - passed,
                          "total": len(results)},
              "cases": results}
    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"{provider.model.replace('/', '_').replace(':', '_')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"{provider.model}: {passed}/{len(results)} pass -> {out.relative_to(ROOT)}")
    return report


def export_web() -> None:
    """Build gallery data: case metadata + live naive/oracle result samples."""
    db = ensure_db()
    payload = []
    for case in load_cases():
        naive_cols, naive_rows = execute(db, guard(case["naive_sql"]))
        oracle_cols, orc_rows = execute(db, guard(case["oracle"]["sql"]))
        payload.append({
            "id": case["id"], "category": case["category"],
            "title": case["title"], "question": case["question"].strip(),
            "ambiguity_resolution": case["ambiguity_resolution"].strip(),
            "hidden_trap": case["hidden_trap"].strip(),
            "naive_sql": case["naive_sql"].strip(),
            "oracle_sql": case["oracle"]["sql"].strip(),
            "grading": case["oracle"].get("grading", "ordered-set"),
            "naive_result": {"columns": naive_cols, "rows": naive_rows[:15]},
            "oracle_result": {"columns": oracle_cols, "rows": orc_rows[:15]},
            "zh": case.get("zh"),
        })
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "cases.json").write_text(
        json.dumps(payload, indent=1, ensure_ascii=False))
    reports_out = WEB_DATA / "reports"
    reports_out.mkdir(exist_ok=True)
    for rp in sorted(REPORTS_DIR.glob("*.json")):
        shutil.copy(rp, reports_out / rp.name)
    # Index the union already in web/data/reports/: freshly generated reports
    # plus the tracked real-model scorecards, which reports/ (gitignored) does
    # not carry on a clean checkout. Building the index only from reports/
    # would silently drop every real model from the gallery on a plain
    # `make eval`.
    index = sorted(p.name for p in reports_out.glob("*.json"))
    (WEB_DATA / "reports_index.json").write_text(json.dumps(index))
    print(f"web data exported -> {WEB_DATA.relative_to(ROOT)} "
          f"({len(payload)} cases, {len(index)} reports)")
    real = [n for n in index if not n.startswith("mock-")]
    if real:
        print(f"note: web/data/reports/ is tracked by git — real-model "
              f"scorecards ({', '.join(real)}) will be committed with it; "
              f"review model names before pushing.")


def main() -> None:
    ap = argparse.ArgumentParser(description="failure-lab runner")
    ap.add_argument("--provider", default="mock-naive",
                    choices=["mock-naive", "mock-oracle", "openai", "cli"])
    ap.add_argument("--export-web", action="store_true",
                    help="rebuild web/data from cases and existing reports")
    args = ap.parse_args()
    if args.export_web:
        export_web()
        return
    run(args.provider)


if __name__ == "__main__":
    main()
