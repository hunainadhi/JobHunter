"""Resolver tests, seeded from real strings in the production jobs table.

Run: python -m pytest tests/test_location_resolver.py -q
"""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lambdas" / "ingestion"))

from location_resolver import (  # noqa: E402
    STATUS_COUNTRYWIDE,
    STATUS_FOREIGN,
    STATUS_RESOLVED,
    STATUS_UNRESOLVED,
    Gazetteer,
    resolve,
)


@pytest.fixture(scope="module")
def gazetteer() -> Gazetteer:
    with (ROOT / "data" / "places_ca.csv").open(encoding="utf-8") as handle:
        return Gazetteer.from_rows(list(csv.DictReader(handle)))


def status_of(raw, gazetteer):
    return resolve(raw, gazetteer).status


def slugs_of(raw, gazetteer):
    return resolve(raw, gazetteer).slugs


# --- every way production writes Toronto ------------------------------------

@pytest.mark.parametrize("raw", [
    "Toronto, ON, ca",
    "Toronto, Ontario, Canada",
    "Toronto",
    "Toronto, Ontario",
    "Toronto, Canada",
    "Toronto, ON",
    "Toronto, ON, CA",
    "Toronto, Ontario, ca",
    "TORONTO, ON, CA",
    "Toronto (Hybrid)",
    "Toronto Office",
    "Toronto - Remote",
])
def test_toronto_variants_all_collapse(raw, gazetteer):
    assert slugs_of(raw, gazetteer) == ["toronto-on"]


# --- the abbreviation collisions that leaked into production ----------------

@pytest.mark.parametrize("raw", [
    "Košice, Košický kraj, sk",     # sk = Slovakia, not Saskatchewan
    "Levice, Nitriansky kraj, sk",
    "Ontario, CA, US",              # Ontario, California
    "Ontario, OH, US",
    "Vancouver, WA, US",            # Washington, not British Columbia
    "VANCOUVER, WA, US",
    "Vancouver, Washington, United States",
    "Darwin, NT, au",               # nt = Australia's Northern Territory
    "Richmond Hill, Georgia, United States",
    "New Brunswick, New Jersey, United States",
    "New Brunswick, NJ, us",
    "London, England",
    "Paris, France",
])
def test_foreign_locations_are_rejected(raw, gazetteer):
    assert status_of(raw, gazetteer) == STATUS_FOREIGN


@pytest.mark.parametrize("raw,slug", [
    ("Saskatoon, SK", "saskatoon-sk"),
    ("Regina, SK", "regina-sk"),
    ("Yorkton, SK, ca", "yorkton-sk"),
    ("Yellowknife, NT", "yellowknife-nt"),
])
def test_province_abbrevs_still_work(raw, slug, gazetteer):
    """The collision fix must not break the provinces themselves."""
    assert slugs_of(raw, gazetteer) == [slug]


# --- accents, case, punctuation ---------------------------------------------

@pytest.mark.parametrize("raw", ["Montréal, QC, ca", "Montreal, QC, ca",
                                 "Montreal, Quebec, Canada", "Montréal",
                                 "MONTREAL, QC, CA"])
def test_montreal_accent_folding(raw, gazetteer):
    assert slugs_of(raw, gazetteer) == ["montreal-qc"]


def test_quebec_city_alias(gazetteer):
    assert slugs_of("Québec, QC, ca", gazetteer) == ["quebec-qc"]
    assert slugs_of("Quebec City, QC", gazetteer) == ["quebec-qc"]


# --- countrywide and remote --------------------------------------------------

@pytest.mark.parametrize("raw", [
    "Canada",
    "Remote - Canada",
    "Remote Canada",
    "Remote, Canada",
    "Remote (Canada)",
    "Canada - Remote",
    "Anywhere in Canada",
])
def test_countrywide_has_no_places(raw, gazetteer):
    resolution = resolve(raw, gazetteer)
    assert resolution.status == STATUS_COUNTRYWIDE
    assert resolution.slugs == []
    assert resolution.is_canadian


def test_bare_remote_is_not_assumed_canadian(gazetteer):
    assert status_of("Remote", gazetteer) == STATUS_UNRESOLVED


# --- multi-location ----------------------------------------------------------

def test_multi_location_keeps_every_canadian_place(gazetteer):
    slugs = slugs_of("Kitchener-Waterloo, ON; Toronto, ON", gazetteer)
    assert set(slugs) == {"kitchener-on", "waterloo-on", "toronto-on"}


def test_one_canadian_segment_rescues_a_foreign_list(gazetteer):
    raw = "US-NYC; US-San Francisco; US-Seattle; US-Remote; Canada-Toronto"
    assert "toronto-on" in slugs_of(raw, gazetteer)


def test_pipe_separated_multi_location(gazetteer):
    raw = "Vancouver | CA-ON-Toronto | CA-ON-Mississauga | CA-AB-Edmonton, BC, CA"
    slugs = set(slugs_of(raw, gazetteer))
    assert {"toronto-on", "mississauga-on"} <= slugs


def test_wholly_foreign_list_is_rejected(gazetteer):
    raw = ("Bethesda, Maryland, United States; Vancouver, Washington, United States; "
           "Waltham, Massachusetts, United States")
    assert status_of(raw, gazetteer) == STATUS_FOREIGN


# --- aliases and metro names -------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Greater Toronto, ON, CA", {"toronto-on"}),
    ("Greater Toronto Area, ON, CA", {"toronto-on"}),
    ("Kitchener-Waterloo, ON", {"kitchener-on", "waterloo-on"}),
])
def test_metro_aliases(raw, expected, gazetteer):
    assert set(slugs_of(raw, gazetteer)) == expected


# --- ambiguous bare city names -----------------------------------------------

def test_bare_ambiguous_city_is_not_claimed_for_canada(gazetteer):
    assert status_of("London", gazetteer) == STATUS_UNRESOLVED
    assert status_of("Cambridge", gazetteer) == STATUS_UNRESOLVED


def test_ambiguous_city_with_province_resolves(gazetteer):
    assert slugs_of("London, ON, ca", gazetteer) == ["london-on"]
    assert slugs_of("Cambridge, Ontario", gazetteer) == ["cambridge-on"]
    assert slugs_of("Waterloo, ON", gazetteer) == ["waterloo-on"]


def test_unambiguous_bare_cities_still_resolve(gazetteer):
    assert slugs_of("Edmonton", gazetteer) == ["edmonton-ab"]
    assert slugs_of("Mississauga", gazetteer) == ["mississauga-on"]


# --- junk --------------------------------------------------------------------

def test_junk_with_canadian_markers_is_unresolved_not_foreign(gazetteer):
    """Canadian intent is clear; the city just isn't real. Keep it reviewable."""
    assert status_of("UNAVAILABLE, ON, CA", gazetteer) == STATUS_UNRESOLVED


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_empty_input(raw, gazetteer):
    assert status_of(raw, gazetteer) == STATUS_UNRESOLVED


def test_street_address_falls_back_to_its_city(gazetteer):
    assert slugs_of("Victoria Ave, Niagara Falls, ON, CA", gazetteer) == ["niagara-falls-on"]


# --- Toronto boroughs, which only exist as admin areas in GeoNames -----------

@pytest.mark.parametrize("raw,slug", [
    ("North York, ON, CA", "north-york-on"),
    ("Scarborough, ON, CA", "scarborough-on"),
    ("Etobicoke, ON, CA", "etobicoke-on"),
])
def test_toronto_boroughs_resolve(raw, slug, gazetteer):
    assert slugs_of(raw, gazetteer) == [slug]
