#!/usr/bin/env python3
"""List non-sensitive application-ledger state for verification."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env: dict[str, str] = {}
    for raw in (ROOT / "app" / ".env.local").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit("Missing Supabase server configuration.")

    query = urllib.parse.urlencode({
        "select": "company_name,job_title,status,failure_reason,next_action,next_action_at,created_at",
        "order": "created_at.desc",
        "limit": "20",
    })
    request = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/application_ledger?{query}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        rows = json.loads(response.read())
    for row in rows:
        print(
            f"{row['status']} | {row['company_name']} | {row['job_title']} | "
            f"next: {row['next_action_at'] or 'none'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
