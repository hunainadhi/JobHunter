#!/usr/bin/env python3
"""Verify application-ledger environment variables and migration without printing secrets."""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
REQUIRED_KEY_SETS = (
    ("NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY"),
    ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY"),
)


def load_environment() -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    found: list[str] = []
    for path in (APP_DIR / ".env.local", APP_DIR / ".env"):
        if not path.exists():
            continue
        found.append(path.name)
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values, found


def main() -> int:
    values, files = load_environment()
    print(f"Environment files found: {', '.join(files) if files else 'none'}")
    matched_keys = next(
        (key_set for key_set in REQUIRED_KEY_SETS if all(values.get(key) for key in key_set)),
        None,
    )
    print(
        "Required key set:",
        "legacy names" if matched_keys == REQUIRED_KEY_SETS[0] else "current Supabase names" if matched_keys else "incomplete",
    )
    if not matched_keys:
        print("Expected either:", " + ".join(REQUIRED_KEY_SETS[0]), "or", " + ".join(REQUIRED_KEY_SETS[1]))
        return 1

    url_name, _, write_key_name = matched_keys
    url = values[url_name].rstrip("/")
    url += "/rest/v1/application_ledger?select=id&limit=1"
    service_key = values[write_key_name]
    request = urllib.request.Request(
        url,
        headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(f"Application ledger API: {response.status}. Migration appears applied.")
            return 0
    except urllib.error.HTTPError as error:
        print(f"Application ledger API: {error.code}. Migration may not be applied.")
        return 2
    except OSError as error:
        print(f"Application ledger API connection failed: {type(error).__name__}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
