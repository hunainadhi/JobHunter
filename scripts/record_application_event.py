#!/usr/bin/env python3
"""Write a private JobHunter application-ledger record and append an event."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "app" / ".env.local"


def environment() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def request_json(url: str, key: str, payload: object, method: str = "POST") -> object:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method=method,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--apply-url", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--score", required=True, type=int)
    parser.add_argument("--status", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--reasons", default="[]")
    parser.add_argument("--fields", default="{}")
    parser.add_argument("--materials", default="{}")
    parser.add_argument("--responses", default="{}")
    parser.add_argument("--failure-reason")
    parser.add_argument("--next-action")
    parser.add_argument("--next-action-at")
    args = parser.parse_args()

    env = environment()
    base_url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    secret = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SERVICE_KEY")
    if not base_url or not secret:
        raise SystemExit("Missing Supabase server configuration.")

    payload = {
        "job_id": args.job_id,
        "company_name": args.company,
        "job_title": args.title,
        "apply_url": args.apply_url,
        "source_url": args.source_url,
        "match_score": args.score,
        "status": args.status,
        "policy_reasons": json.loads(args.reasons),
        "application_fields": json.loads(args.fields),
        "submitted_materials": json.loads(args.materials),
        "submitted_responses": json.loads(args.responses),
        "failure_reason": args.failure_reason,
        "next_action": args.next_action,
        "next_action_at": args.next_action_at,
    }
    application_url = base_url.rstrip("/") + "/rest/v1/application_ledger?on_conflict=job_id"
    rows = request_json(application_url, secret, payload)
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise RuntimeError("Unexpected application-ledger response.")
    application_id = rows[0]["id"]
    event_url = base_url.rstrip("/") + "/rest/v1/application_events"
    request_json(
        event_url,
        secret,
        {
            "application_id": application_id,
            "event_type": args.event,
            "details": {
                "status": args.status,
                "reasons": payload["policy_reasons"],
                "failure_reason": args.failure_reason,
            },
        },
    )
    print(f"Ledger record saved: {args.company} | {args.title} | {args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
