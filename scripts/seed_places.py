#!/usr/bin/env python3
"""Seed the places table from data/places_ca.csv.

Usage: python scripts/seed_places.py

Idempotent — upserts on slug, so re-running after a gazetteer rebuild updates
rows in place. Requires migration 018 to have been applied.
"""

import csv
import os
import sys
from pathlib import Path

from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
BATCH = 500


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    load_env(ROOT / ".env")
    url = os.environ.get("SUPABASE_URL") or os.environ["NEXT_PUBLIC_SUPABASE_URL"]
    supabase = create_client(url, os.environ["SUPABASE_SERVICE_KEY"])

    csv_path = ROOT / "data" / "places_ca.csv"
    if not csv_path.exists():
        sys.exit(f"Missing {csv_path} — run scripts/build_gazetteer.py first.")

    with csv_path.open(encoding="utf-8") as handle:
        rows = [
            {
                "slug": r["slug"],
                "name": r["name"],
                "province": r["province"],
                "province_name": r["province_name"],
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
                "population": int(r["population"] or 0),
            }
            for r in csv.DictReader(handle)
        ]

    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        supabase.table("places").upsert(chunk, on_conflict="slug").execute()
        print(f"  seeded {min(start + BATCH, len(rows))}/{len(rows)}")

    total = supabase.table("places").select("slug", count="exact", head=True).execute()
    print(f"Done. places table holds {total.count} rows.")


if __name__ == "__main__":
    main()
