# Security Model — What the Guardrails Do and Do Not Promise

This is a learning/evaluation project. The guardrails in `failure_lab.guard`
are a **minimal, honest demonstration**, not a product security layer.

## What is covered

| Control | Mechanism |
|---|---|
| Read-only execution | SQLite opened with `mode=ro` (URI) |
| Statement type | `SELECT` / `WITH` only, single statement |
| Dangerous keywords | `ATTACH`, `DETACH`, `PRAGMA`, DML/DDL rejected before execution |
| Runaway queries | wall-clock interrupt (5 s) via `sqlite3.Connection.interrupt` |
| Result flooding | hard row cap (10,000) |

## What is deliberately NOT covered

- **Semantic correctness.** This is the whole point of the repo: every
  failure case ships SQL that passes all of the above checks and still
  returns a wrong answer. Guardrails make SQL *safe to execute*; they say
  nothing about whether it *means the right thing*.
- Production concerns: authentication, multi-tenancy, network exposure,
  prompt-injection handling for untrusted schema/content, resource
  quotas beyond the two limits above, or non-SQLite engines (each engine
  has its own escape hatches — the keyword list here is SQLite-specific).
- Adversarial SQL crafted to exhaust memory inside a single allowed
  statement. The row cap and timeout narrow this; they do not close it.

If you adapt this code for anything real: enforce least privilege at the
database account level first (a read-only role), and treat every model
completion as untrusted input. Keyword filters are the seatbelt, not the
brakes.

## Reporting

This repository processes no user data and runs no service. If you find a
problem anyway, open an issue.
