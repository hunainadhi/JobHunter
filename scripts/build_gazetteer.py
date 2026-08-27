#!/usr/bin/env python3
"""Build the Canadian gazetteer CSV from the GeoNames country dump.

Usage:
    python scripts/build_gazetteer.py [--dump path/to/CA.txt] [--out data/places_ca.csv]

Downloads https://download.geonames.org/export/dump/CA.zip when no dump is given.
The output CSV is committed so the build is reproducible without the 35MB dump.

GeoNames data is licensed CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/);
the board must carry an attribution line.
"""

import argparse
import csv
import io
import re
import sys
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

DUMP_URL = "https://download.geonames.org/export/dump/CA.zip"

# GeoNames admin1 code -> (province abbreviation, province name)
ADMIN1 = {
    "01": ("AB", "Alberta"),
    "02": ("BC", "British Columbia"),
    "03": ("MB", "Manitoba"),
    "04": ("NB", "New Brunswick"),
    "05": ("NL", "Newfoundland and Labrador"),
    "07": ("NS", "Nova Scotia"),
    "08": ("ON", "Ontario"),
    "09": ("PE", "Prince Edward Island"),
    "10": ("QC", "Quebec"),
    "11": ("SK", "Saskatchewan"),
    "12": ("YT", "Yukon"),
    "13": ("NT", "Northwest Territories"),
    "14": ("NU", "Nunavut"),
}

# Populated places at or above this population are kept.
MIN_POPULATION = 1000

# PPLX is "section of a populated place" — Kitchener-Waterloo neighbourhoods like
# Central, Columbia and City Commercial Core. They pollute the gazetteer with
# generic one-word names that would hijack matching, and a job posted in one of
# them is really posted in its parent city. Real municipalities that look like
# neighbourhoods (Westmount QC, Etobicoke, Burnaby) carry other codes and survive.
# A large PPLX is a real borough though — Saint-Hubert QC has 82,548 people and
# 25 job postings — so only the small ones are dropped. The KW neighbourhoods
# that motivated this top out at 13,635, well under the threshold.
EXCLUDED_FEATURE_CODES = {"PPLX"}
MIN_SECTION_POPULATION = 20_000

# North York (636k) and Scarborough (600k) exist in GeoNames only as ADM3
# administrative areas, not as populated places — a plain feature-class-P filter
# silently drops two of the largest sources of Toronto-area postings. Admin areas
# this large are municipalities in practice, so they are folded in.
ADMIN_FEATURE_CODES = {"ADM2", "ADM3"}
MIN_ADMIN_POPULATION = 50_000

# Column indexes in the GeoNames dump (tab-separated, no header).
COL_NAME, COL_ASCII, COL_ALT = 1, 2, 3
COL_LAT, COL_LNG = 4, 5
COL_FCLASS, COL_FCODE = 6, 7
COL_ADMIN1 = 10
COL_POP = 14


def fold(text: str) -> str:
    """Lowercase and strip accents so 'Montréal' and 'Montreal' compare equal."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def slugify(name: str, province: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")
    return f"{base}-{province.lower()}"


def download_dump(target: Path) -> Path:
    print(f"Downloading {DUMP_URL} ...", file=sys.stderr)
    with urllib.request.urlopen(DUMP_URL, timeout=180) as response:
        payload = response.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extract("CA.txt", target)
    return target / "CA.txt"


def parse_dump(dump_path: Path) -> list[dict]:
    """Return one record per (name, province), keeping the most populous."""
    best: dict[tuple[str, str], dict] = {}

    with dump_path.open(encoding="utf-8") as handle:
        for line in handle:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 15:
                continue

            province = ADMIN1.get(cols[COL_ADMIN1])
            if not province:
                continue
            abbrev, province_name = province

            try:
                population = int(cols[COL_POP] or 0)
            except ValueError:
                continue

            fclass, fcode = cols[COL_FCLASS], cols[COL_FCODE]
            if fclass == "P":
                if fcode in EXCLUDED_FEATURE_CODES and population < MIN_SECTION_POPULATION:
                    continue
                if population < MIN_POPULATION:
                    continue
            elif fclass == "A" and fcode in ADMIN_FEATURE_CODES:
                if population < MIN_ADMIN_POPULATION:
                    continue
            else:
                continue

            name = cols[COL_NAME].strip()
            if not name:
                continue

            try:
                lat, lng = float(cols[COL_LAT]), float(cols[COL_LNG])
            except ValueError:
                continue

            key = (fold(name), abbrev)
            existing = best.get(key)
            # Prefer the populated place over the admin area at equal population,
            # since its coordinate is the town centre rather than a polygon centroid.
            if existing and (
                existing["population"] > population
                or (existing["population"] == population and existing["feature_class"] == "P")
            ):
                continue

            best[key] = {
                "slug": slugify(name, abbrev),
                "name": name,
                "ascii_name": cols[COL_ASCII].strip() or name,
                "province": abbrev,
                "province_name": province_name,
                "latitude": round(lat, 5),
                "longitude": round(lng, 5),
                "population": population,
                "feature_class": fclass,
                "feature_code": fcode,
            }

    records = sorted(best.values(), key=lambda r: (-r["population"], r["slug"]))

    # Slugs collide when two same-named places share a province (rare, but real).
    seen: dict[str, int] = {}
    for record in records:
        slug = record["slug"]
        if slug in seen:
            seen[slug] += 1
            record["slug"] = f"{slug}-{seen[slug]}"
        else:
            seen[slug] = 1

    return records


FIELDS = ["slug", "name", "ascii_name", "province", "province_name",
          "latitude", "longitude", "population", "feature_class", "feature_code"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", type=Path, default=None)
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data" / "places_ca.csv")
    args = parser.parse_args()

    dump_path = args.dump
    if dump_path is None:
        dump_path = download_dump(args.out.parent)
    if not dump_path.exists():
        sys.exit(f"Dump not found: {dump_path}")

    records = parse_dump(dump_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)

    by_province: dict[str, int] = {}
    for record in records:
        by_province[record["province"]] = by_province.get(record["province"], 0) + 1

    print(f"Wrote {len(records)} places to {args.out}")
    for province, count in sorted(by_province.items(), key=lambda kv: -kv[1]):
        print(f"  {province}: {count}")


if __name__ == "__main__":
    main()
