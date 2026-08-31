"""Tests for the scoring Lambda's timeout and truncation handling.

The scoring run hit its 900s Lambda ceiling every day for five days straight.
Two things went wrong each time: the in-flight claims were never released (778
jobs leaked into 'scoring'), and the self-chain that continues the day's work
was never reached. A third fault discarded whole batches whenever the model's
JSON came back truncated.

Run: python -m pytest tests/test_scoring_resilience.py -q
"""

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# handler.py reads its config and builds a Supabase client at import time.
os.environ.setdefault("SUPABASE_URL", "https://stub.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "stub-key")
os.environ.setdefault("OPENROUTER_API_KEY", "stub-key")

for name, attrs in (
    ("boto3", {"client": lambda *a, **k: None}),
    ("httpx", {"Client": object, "post": lambda *a, **k: None}),
    ("supabase", {"create_client": lambda *a, **k: None}),
):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        for attr, value in attrs.items():
            setattr(mod, attr, value)
        sys.modules[name] = mod

# Loaded by path under a distinct name: the ingestion Lambda also has a
# handler.py, and a plain `import handler` resolves to whichever test module
# ran first.
_spec = importlib.util.spec_from_file_location(
    "scoring_handler", ROOT / "lambdas" / "scoring" / "handler.py"
)
handler = importlib.util.module_from_spec(_spec)
sys.modules["scoring_handler"] = handler
_spec.loader.exec_module(handler)


# --- salvaging a truncated response -----------------------------------------

def test_salvage_recovers_objects_from_a_truncated_array():
    """The exact shape that was failing: array cut off mid-object."""
    truncated = """[
      {"job_id": "a", "score": 80, "rationale": "good fit"},
      {"job_id": "b", "score": 40, "rationale": "weak overlap"},
      {"job_id": "c", "score": 65, "rationale": "partial ratio
    """
    salvaged = handler.salvage_json_objects(truncated)

    assert [o["job_id"] for o in salvaged] == ["a", "b"]
    assert salvaged[0]["score"] == 80


def test_salvage_ignores_braces_inside_strings():
    text = '[{"job_id": "a", "rationale": "uses {braces} and \\"quotes\\" inline"}]'
    salvaged = handler.salvage_json_objects(text)

    assert len(salvaged) == 1
    assert salvaged[0]["rationale"] == 'uses {braces} and "quotes" inline'


def test_salvage_handles_nested_objects():
    text = '[{"job_id": "a", "meta": {"nested": {"deep": 1}}, "score": 70}, {"job_id": "b"'
    salvaged = handler.salvage_json_objects(text)

    assert len(salvaged) == 1
    assert salvaged[0]["meta"]["nested"]["deep"] == 1


@pytest.mark.parametrize("text", ["", "not json at all", "[", "{{{{"])
def test_salvage_returns_empty_rather_than_raising(text):
    assert handler.salvage_json_objects(text) == []


def test_salvage_of_a_complete_array_is_lossless():
    payload = [{"job_id": str(i), "score": i} for i in range(5)]
    salvaged = handler.salvage_json_objects(json.dumps(payload))

    assert salvaged == payload


# --- the deadline guard -----------------------------------------------------

class FakeTable:
    def __init__(self, recorder):
        self._rec = recorder

    def update(self, payload):
        self._rec.append(payload)
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[], count=0)


class FakeSupabase:
    """Enough of the client for score_round: claims a fixed set, records writes."""

    def __init__(self, claim):
        self._claim = claim
        self.updates: list = []
        self.rpc_calls: list = []

    def rpc(self, name, params=None):
        self.rpc_calls.append((name, params))
        data = self._claim if name == "claim_jobs_for_scoring" else 0
        return types.SimpleNamespace(execute=lambda: types.SimpleNamespace(data=data))

    def table(self, name):
        return FakeTable(self.updates)


def test_round_stops_before_a_batch_it_cannot_finish(monkeypatch):
    """With no time left, no batch is attempted and the claim is handed back."""
    jobs = [{"id": f"job-{i}", "title": "T", "company_name": "C",
             "location": "Toronto", "description": "d"} for i in range(20)]
    supabase = FakeSupabase(jobs)

    called = []
    monkeypatch.setattr(handler, "score_batch", lambda b: called.append(b) or [])
    monkeypatch.setattr(handler.time, "monotonic", lambda: 1000.0)

    # Deadline already inside the reserve window.
    stats = handler.score_round(supabase, set(), deadline=1000.0)

    assert called == [], "no batch should be attempted with no time left"
    assert stats["ran_out_of_time"] is True
    # The claimed jobs must be released back to 'new', which is what the hard
    # timeout used to skip.
    assert {"status": "new"} in supabase.updates


def test_round_runs_batches_when_time_allows(monkeypatch):
    jobs = [{"id": f"job-{i}", "title": "T", "company_name": "C",
             "location": "Toronto", "description": "d"} for i in range(10)]
    supabase = FakeSupabase(jobs)

    called = []
    monkeypatch.setattr(handler, "score_batch", lambda b: called.append(b) or [])
    monkeypatch.setattr(handler, "generate_embeddings", lambda b: {})
    monkeypatch.setattr(handler.time, "monotonic", lambda: 0.0)

    stats = handler.score_round(supabase, set(), deadline=10_000.0)

    assert len(called) == 10 // handler.BATCH_SIZE
    assert stats["ran_out_of_time"] is False


def test_last_batch_finishes_before_the_lambda_wall_clock():
    """The safety property the old guard lacked.

    The last batch can start as late as (budget - reserve), so that instant
    plus a batch's duration must still land before the 900s ceiling, leaving
    room to release claims and fire the self-chain. Previously the check ran
    only between rounds of 100 jobs, which take 400-550s, against a 60s margin.
    """
    LAMBDA_TIMEOUT = 900
    OBSERVED_BATCH_SECONDS = 60  # a 10-job batch; BATCH_SIZE is now 5

    latest_batch_start = handler.MAX_RUNTIME_SECONDS - handler.BATCH_TIME_RESERVE_SECONDS
    assert latest_batch_start + OBSERVED_BATCH_SECONDS < LAMBDA_TIMEOUT
    # The reserve must cover a batch plus the post-loop bookkeeping.
    assert handler.BATCH_TIME_RESERVE_SECONDS > OBSERVED_BATCH_SECONDS
