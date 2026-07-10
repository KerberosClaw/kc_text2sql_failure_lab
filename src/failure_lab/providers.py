"""SQL providers.

Two mocks and one real interface:

  mock-naive   : answers every case with its recorded naive_sql — the
                 model whose only job is to be wrong.
  mock-oracle  : answers with the oracle SQL — never misses.
  openai       : any OpenAI-compatible chat-completions endpoint
                 (cloud APIs and local Ollama /v1 alike), configured via
                 FLAB_BASE_URL / FLAB_API_KEY / FLAB_MODEL /
                 FLAB_REASONING_EFFORT (optional).

The two mocks are the grader's entrance exam: a grader that cannot tell
them apart has no business scoring a real model.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request


class ProviderError(Exception):
    pass


class MockNaive:
    name = "mock-naive"
    model = "mock-naive"

    def generate_sql(self, case: dict, schema_ddl: str) -> str:
        return case["naive_sql"]


class MockOracle:
    name = "mock-oracle"
    model = "mock-oracle"

    def generate_sql(self, case: dict, schema_ddl: str) -> str:
        return case["oracle"]["sql"]


PROMPT_TEMPLATE = """You translate natural-language questions into SQLite SQL.

Database schema (SQLite DDL — read the column comments, they document
value domains):

{ddl}

Rules:
- Output exactly one SQLite SELECT statement inside a ```sql fence.
- No prose, no explanation.

Question: {question}

Clarification (binding): {clarification}
"""


class OpenAICompat:
    name = "openai"

    def __init__(self) -> None:
        self.base_url = os.environ.get("FLAB_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.environ.get("FLAB_API_KEY", "")
        self.model = os.environ.get("FLAB_MODEL", "")
        self.reasoning = os.environ.get("FLAB_REASONING_EFFORT", "")
        if not self.model:
            raise ProviderError("FLAB_MODEL is required for the openai provider")

    def generate_sql(self, case: dict, schema_ddl: str) -> str:
        prompt = PROMPT_TEMPLATE.format(
            ddl=schema_ddl, question=case["question"].strip(),
            clarification=case["ambiguity_resolution"].strip())
        body: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_completion_tokens": 4000,
        }
        if self.reasoning:
            body["reasoning_effort"] = self.reasoning
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=180) as r:
            text = json.load(r)["choices"][0]["message"]["content"]
        m = re.search(r"```sql\s*(.+?)```", text, re.S | re.I)
        sql = (m.group(1) if m else text).strip()
        if not sql:
            raise ProviderError("empty completion")
        return sql


def get_provider(name: str):
    return {"mock-naive": MockNaive, "mock-oracle": MockOracle,
            "openai": OpenAICompat}[name]()
