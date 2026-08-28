"""Multi-location ingestion tests.

Covers the two changes that let a job open in several cities reach the board
when Canada isn't the location the ATS happened to list first:

  * ``candidate_locations`` — reading each ATS's side list of extra locations
  * ``filter_canadian``     — keeping such a job and storing the Canadian string
  * ``AshbyGraphQLScraper`` — renaming GraphQL fields to public-API names

Run: python -m pytest tests/test_multi_location.py -q
"""

import csv
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lambdas" / "ingestion"))

# handler.py reads Supabase config and pulls two names out of the vendored
# jobhive layer at import time. Neither is exercised here, and the layer ships
# manylinux wheels that can't load on a dev machine, so both are stubbed.
os.environ.setdefault("SUPABASE_URL", "https://stub.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "stub-key")

_supabase = types.ModuleType("supabase")
_supabase.create_client = lambda *a, **k: None
sys.modules.setdefault("supabase", _supabase)

if "jobhive.exceptions" not in sys.modules:
    _jobhive = types.ModuleType("jobhive")
    _exceptions = types.ModuleType("jobhive.exceptions")

    class CompanyNotFoundError(Exception):
        pass

    class ScraperError(Exception):
        pass

    _exceptions.CompanyNotFoundError = CompanyNotFoundError
    _exceptions.ScraperError = ScraperError
    sys.modules["jobhive"] = _jobhive
    sys.modules["jobhive.exceptions"] = _exceptions

import handler  # noqa: E402
from location_resolver import Gazetteer  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def gazetteer():
    with (ROOT / "data" / "places_ca.csv").open(encoding="utf-8") as handle:
        handler._GAZETTEER = Gazetteer.from_rows(list(csv.DictReader(handle)))
    yield handler._GAZETTEER
    handler._GAZETTEER = None


@pytest.fixture(autouse=True)
def clear_resolution_cache():
    handler._RESOLUTIONS.clear()
    yield
    handler._RESOLUTIONS.clear()


class FakeJob:
    """Stands in for jobhive's pydantic Job — filter_canadian touches
    description, location and raw, and nothing else."""

    def __init__(self, location, raw=None, description="a description"):
        self.location = location
        self.raw = raw
        self.description = description


# --- candidate_locations: one shape per ATS ---------------------------------

def test_ashby_secondary_locations():
    job = FakeJob("San Francisco (hybrid)",
                  {"secondary_locations": ["Toronto (hybrid)"]})
    assert handler.candidate_locations(job) == [
        "San Francisco (hybrid)", "Toronto (hybrid)"
    ]


def test_greenhouse_offices():
    job = FakeJob("New York, NY", {"offices": ["New York", "Toronto, ON, Canada"]})
    assert "Toronto, ON, Canada" in handler.candidate_locations(job)


def test_lever_all_locations():
    job = FakeJob("Marin, California",
                  {"categories": {"allLocations": ["Marin, California",
                                                   "Vancouver, BC"]}})
    assert handler.candidate_locations(job) == [
        "Marin, California", "Vancouver, BC"
    ]


def test_workable_structured_locations():
    job = FakeJob("Austin, TX, United States", {"locations": [
        {"city": "Austin", "region": "TX", "country": "United States"},
        {"city": "Ottawa", "region": "ON", "country": "Canada"},
    ]})
    assert "Ottawa, ON, Canada" in handler.candidate_locations(job)


def test_primary_always_first_and_deduplicated():
    job = FakeJob("Toronto", {"offices": ["Toronto", "Montreal"]})
    assert handler.candidate_locations(job) == ["Toronto", "Montreal"]


@pytest.mark.parametrize("raw", [None, {}, {"offices": []},
                                {"categories": "not-a-dict"},
                                {"secondary_locations": [None, "   "]}])
def test_malformed_raw_degrades_to_primary_only(raw):
    assert handler.candidate_locations(FakeJob("Toronto", raw)) == ["Toronto"]


# --- filter_canadian --------------------------------------------------------

def test_job_kept_via_secondary_location_and_rewritten():
    """The EvenUp case: US primary, Canadian secondary."""
    job = FakeJob("San Francisco (hybrid)",
                  {"secondary_locations": ["Toronto (hybrid)"]})
    stats = {}
    kept = handler.filter_canadian([job], None, stats)

    assert kept == [job]
    # The Canadian string must be what gets stored — job_locations joins on it,
    # so a job saved as "San Francisco (hybrid)" never surfaces on the board.
    assert job.location == "Toronto (hybrid)"
    assert job.raw["primary_location"] == "San Francisco (hybrid)"
    assert stats["jobs_kept_via_secondary"] == 1


def test_canadian_primary_is_left_untouched():
    job = FakeJob("Toronto, ON", {"secondary_locations": ["San Francisco"]})
    stats = {}

    assert handler.filter_canadian([job], None, stats) == [job]
    assert job.location == "Toronto, ON"
    assert "primary_location" not in (job.raw or {})
    assert stats.get("jobs_kept_via_secondary", 0) == 0


def test_job_with_no_canadian_location_is_rejected():
    job = FakeJob("San Francisco, CA", {"offices": ["New York", "Austin"]})
    stats = {}

    assert handler.filter_canadian([job], None, stats) == []
    assert stats["jobs_rejected"] == 1
    # The reason must describe the primary, not the last candidate tried.
    assert len(stats["reject_reasons"]) == 1


def test_job_without_description_is_dropped_before_resolving():
    job = FakeJob("Toronto, ON", None, description=None)
    stats = {}
    assert handler.filter_canadian([job], None, stats) == []
    assert stats.get("jobs_rejected", 0) == 0


# --- Ashby GraphQL field renaming -------------------------------------------

def test_graphql_payload_is_reshaped_to_public_api_names():
    sys.modules.setdefault(
        "jobhive.scrapers", types.ModuleType("jobhive.scrapers")
    )
    if "jobhive.scrapers.ashby" not in sys.modules:
        mod = types.ModuleType("jobhive.scrapers.ashby")

        class AshbyScraper:
            def __init__(self, company_slug, timeout=30.0):
                self.company_slug = company_slug
                self.timeout = timeout

        mod.AshbyScraper = AshbyScraper
        sys.modules["jobhive.scrapers.ashby"] = mod

    from ashby_graphql import AshbyGraphQLScraper

    scraper = AshbyGraphQLScraper(company_slug="evenup")
    item = scraper._to_public_api_shape(
        {
            "id": "abc-123",
            "title": "Software Engineer (New Grad), Data Products",
            "locationName": "San Francisco (hybrid)",
            "workplaceType": "Hybrid",
            "employmentType": "FullTime",
            "compensationTierSummary": "$130K • Offers Equity",
            "secondaryLocations": [{"locationName": "Toronto (hybrid)"}],
        },
        {"departmentName": "Engineering", "publishedDate": "2026-08-26",
         "descriptionHtml": "<p>body</p>"},
    )

    # locationName -> location and secondaryLocations[].locationName ->
    # [].location are what the ingestion handler reads.
    assert item["location"] == "San Francisco (hybrid)"
    assert item["secondaryLocations"] == [{"location": "Toronto (hybrid)"}]
    assert item["descriptionHtml"] == "<p>body</p>"
    assert item["publishedAt"] == "2026-08-26"
    assert item["jobUrl"] == "https://jobs.ashbyhq.com/evenup/abc-123"
    assert item["applyUrl"].endswith("/abc-123/application")
    assert item["compensation"]["compensationTierSummary"] == "$130K • Offers Equity"


def test_graphql_shape_tolerates_missing_detail():
    from ashby_graphql import AshbyGraphQLScraper

    item = AshbyGraphQLScraper(company_slug="evenup")._to_public_api_shape(
        {"id": "x", "title": "Engineer", "locationName": "Toronto"}, {}
    )
    assert item["secondaryLocations"] == []
    assert item["descriptionHtml"] is None
    assert "compensation" not in item
