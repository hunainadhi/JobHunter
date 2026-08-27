#!/usr/bin/env python3
"""Resolve every distinct job location string into the alias cache.

Usage:
    python scripts/resolve_locations.py [--dry-run] [--only-new]

Resolution keys on the distinct string, not the job: ~1,650 strings back ~10,800
jobs. Because job_locations is a view over this cache, re-running after a
resolver change updates every job at once — there is no per-job backfill.

    --dry-run   report what would change, write nothing
    --only-new  skip strings already in the cache (use after a normal ingest;
                omit it to re-resolve everything after a resolver change)
"""

import argparse
import csv
import os
import sys
from collections import Counter
from pathlib import Path

from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lambdas" / "ingestion"))

from location_resolver import Gazetteer, resolve  # noqa: E402

RESOLVER_VERSION = 1
PAGE = 1000
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


def fetch_gazetteer(supabase) -> Gazetteer:
    rows: list[dict] = []
    for offset in range(0, 20000, PAGE):
        response = (
            supabase.table("places")
            .select("slug, name, province, latitude, longitude, population")
            .range(offset, offset + PAGE - 1)
            .execute()
        )
        rows.extend(response.data or [])
        if len(response.data or []) < PAGE:
            break
    if not rows:
        sys.exit("places table is empty — run scripts/seed_places.py first.")
    print(f"Gazetteer: {len(rows)} places")
    return Gazetteer.from_rows(rows)


def fetch_distinct_locations(supabase) -> Counter:
    counts: Counter = Counter()
    for offset in range(0, 200000, PAGE):
        response = (
            supabase.table("jobs")
            .select("location")
            .neq("status", "expired")
            .order("id")
            .range(offset, offset + PAGE - 1)
            .execute()
        )
        rows = response.data or []
        for row in rows:
            counts[(row.get("location") or "").strip()] += 1
        if len(rows) < PAGE:
            break
    return counts


def fetch_known_aliases(supabase) -> set[str]:
    known: set[str] = set()
    for offset in range(0, 200000, PAGE):
        response = (
            supabase.table("location_aliases")
            .select("raw_location")
            .range(offset, offset + PAGE - 1)
            .execute()
        )
        rows = response.data or []
        known.update(r["raw_location"] for r in rows)
        if len(rows) < PAGE:
            break
    return known


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-new", action="store_true")
    args = parser.parse_args()

    load_env(ROOT / ".env")
    url = os.environ.get("SUPABASE_URL") or os.environ["NEXT_PUBLIC_SUPABASE_URL"]
    supabase = create_client(url, os.environ["SUPABASE_SERVICE_KEY"])

    gazetteer = fetch_gazetteer(supabase)
    counts = fetch_distinct_locations(supabase)
    print(f"Jobs: {sum(counts.values())} across {len(counts)} distinct location strings")

    targets = set(counts)
    if args.only_new:
        known = fetch_known_aliases(supabase)
        targets -= known
        print(f"--only-new: {len(targets)} strings not yet cached")

    alias_rows: list[dict] = []
    link_rows: list[dict] = []
    by_status: Counter = Counter()
    jobs_by_status: Counter = Counter()
    unresolved: list[tuple[int, str]] = []

    for raw in targets:
        resolution = resolve(raw, gazetteer)
        by_status[resolution.status] += 1
        jobs_by_status[resolution.status] += counts[raw]

        alias_rows.append({
            "raw_location": raw,
            "status": resolution.status,
            "reason": resolution.reason[:500],
            "resolver_version": RESOLVER_VERSION,
        })
        for slug in resolution.slugs:
            link_rows.append({"raw_location": raw, "place_slug": slug})

        if resolution.status in ("unresolved", "foreign"):
            unresolved.append((counts[raw], raw))

    print("\nBy distinct string:")
    for status, n in by_status.most_common():
        print(f"  {status:12s} {n:5d}")
    print("By job:")
    total = sum(jobs_by_status.values()) or 1
    for status, n in jobs_by_status.most_common():
        print(f"  {status:12s} {n:6d}  {n * 100 / total:4.1f}%")

    print("\nLargest strings needing review:")
    for n, raw in sorted(unresolved, reverse=True)[:15]:
        print(f"  {n:5d}  {raw[:70]}")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return

    print(f"\nWriting {len(alias_rows)} aliases, {len(link_rows)} place links...")
    for start in range(0, len(alias_rows), BATCH):
        supabase.table("location_aliases").upsert(
            alias_rows[start:start + BATCH], on_conflict="raw_location"
        ).execute()
    # Links are replaced wholesale for the strings just resolved, so a rule change
    # that drops a place does not leave the stale link behind.
    for start in range(0, len(alias_rows), BATCH):
        chunk = [row["raw_location"] for row in alias_rows[start:start + BATCH]]
        supabase.table("location_alias_places").delete().in_("raw_location", chunk).execute()
    for start in range(0, len(link_rows), BATCH):
        supabase.table("location_alias_places").upsert(
            link_rows[start:start + BATCH], on_conflict="raw_location,place_slug"
        ).execute()

    print("Done.")


if __name__ == "__main__":
    main()
