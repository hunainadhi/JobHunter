"""Ashby scraper that falls back to the board's own API when the public one 404s.

Ashby's public posting API (``api.ashbyhq.com/posting-api/job-board/{slug}``)
is opt-in. Boards that never switched it on return 404 there while still
serving every posting through the endpoint ``jobs.ashbyhq.com`` calls to render
itself. Upstream's ``AshbyScraper`` only knows the public API, so those
companies looked permanently dead and got written into ``dead_companies`` after
three runs — EvenUp was hiring in Toronto the whole time.

This subclass lives here rather than as a patch to the vendored jobhive layer
because deploy.sh rebuilds that layer from a pinned git commit on every deploy,
which would silently drop the patch.

The GraphQL payload is reshaped into the public API's field names so upstream's
``_parse_job`` stays the single place that builds a ``Job``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from jobhive.exceptions import CompanyNotFoundError, ScraperError
from jobhive.scrapers.ashby import AshbyScraper

GRAPHQL_URL = "https://jobs.ashbyhq.com/api/non-user-graphql"
JOB_URL_TEMPLATE = "https://jobs.ashbyhq.com/{slug}/{posting_id}"
APPLY_URL_TEMPLATE = "https://jobs.ashbyhq.com/{slug}/{posting_id}/application"

# The board query is the only one that exposes secondaryLocations, and the
# detail query is the only one that exposes descriptionHtml — neither is a
# superset of the other, so a full Job needs both.
_BOARD_QUERY = """
query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
  jobBoard: jobBoardWithTeams(
    organizationHostedJobsPageName: $organizationHostedJobsPageName
  ) {
    jobPostings {
      id
      title
      locationName
      workplaceType
      employmentType
      compensationTierSummary
      secondaryLocations { locationName }
    }
  }
}
"""

_POSTING_QUERY = """
query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) {
  jobPosting(
    organizationHostedJobsPageName: $organizationHostedJobsPageName
    jobPostingId: $jobPostingId
  ) {
    id
    departmentName
    publishedDate
    descriptionHtml
  }
}
"""

# Ashby serves the board unauthenticated but rate-limits aggressively; 6 in
# flight clears a 36-posting board well inside the Lambda's per-company budget
# without tripping it.
DETAIL_CONCURRENCY = 6


class AshbyGraphQLScraper(AshbyScraper):
    """``AshbyScraper`` plus a GraphQL fallback for private-API boards."""

    async def _fetch_async(self) -> list:
        try:
            return await super()._fetch_async()
        except CompanyNotFoundError:
            # Only a 404 lands here. Real transport/5xx failures stay
            # ScraperError and propagate, so a flaky run is never mistaken for
            # a board that needs the fallback.
            pass

        payload = await self._fetch_graphql_board()
        return [self._parse_job(item) for item in payload["jobs"]]

    async def _fetch_graphql_board(self) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=True
        ) as client:
            board = await self._post_graphql(
                client,
                "ApiJobBoardWithTeams",
                _BOARD_QUERY,
                {"organizationHostedJobsPageName": self.company_slug},
            )
            job_board = board.get("jobBoard")
            if job_board is None:
                # Null board is the genuine "no such org" signal; an existing
                # board with no open roles returns an empty list instead, and
                # must not be recorded as dead.
                raise CompanyNotFoundError(
                    f"Ashby board not found: {self.company_slug}"
                )

            postings = job_board.get("jobPostings") or []
            if not postings:
                return {"jobs": []}

            details = await self._fetch_details(
                client, [p["id"] for p in postings if p.get("id")]
            )

        return {
            "jobs": [
                self._to_public_api_shape(p, details.get(p["id"]) or {})
                for p in postings
                if p.get("id") and p.get("title")
            ]
        }

    async def _fetch_details(
        self, client: httpx.AsyncClient, posting_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Fetch per-posting descriptions concurrently, tolerating stragglers."""
        semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

        async def one(posting_id: str) -> tuple[str, dict[str, Any]]:
            async with semaphore:
                try:
                    data = await self._post_graphql(
                        client,
                        "ApiJobPosting",
                        _POSTING_QUERY,
                        {
                            "organizationHostedJobsPageName": self.company_slug,
                            "jobPostingId": posting_id,
                        },
                    )
                except (ScraperError, httpx.HTTPError):
                    # A posting pulled mid-scrape shouldn't sink the company.
                    # It arrives with no description and the ingestion handler
                    # drops it there.
                    return posting_id, {}
                return posting_id, data.get("jobPosting") or {}

        results = await asyncio.gather(*(one(pid) for pid in posting_ids))
        return dict(results)

    async def _post_graphql(
        self,
        client: httpx.AsyncClient,
        operation: str,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        response = await client.post(
            f"{GRAPHQL_URL}?op={operation}",
            json={
                "operationName": operation,
                "query": query,
                "variables": variables,
            },
            headers={"Content-Type": "application/json"},
        )
        if response.status_code != 200:
            raise ScraperError(
                f"Ashby GraphQL {operation} returned {response.status_code} "
                f"for {self.company_slug}"
            )
        body = response.json()
        if body.get("errors"):
            raise ScraperError(
                f"Ashby GraphQL {operation} errored for {self.company_slug}: "
                f"{body['errors'][0].get('message', 'unknown')}"
            )
        return body.get("data") or {}

    def _to_public_api_shape(
        self, posting: dict[str, Any], detail: dict[str, Any]
    ) -> dict[str, Any]:
        """Rename GraphQL fields to their public-API equivalents.

        ``locationName`` -> ``location`` and ``secondaryLocations[].locationName``
        -> ``secondaryLocations[].location`` are the two that matter: the
        ingestion handler reads both when deciding whether a job is Canadian.
        """
        posting_id = posting["id"]
        secondary = [
            {"location": loc["locationName"]}
            for loc in posting.get("secondaryLocations") or []
            if isinstance(loc, dict) and loc.get("locationName")
        ]

        item: dict[str, Any] = {
            "id": posting_id,
            "title": posting["title"],
            "location": posting.get("locationName"),
            "secondaryLocations": secondary,
            "workplaceType": posting.get("workplaceType"),
            "employmentType": posting.get("employmentType"),
            "department": detail.get("departmentName"),
            "descriptionHtml": detail.get("descriptionHtml"),
            "publishedAt": detail.get("publishedDate"),
            "jobUrl": JOB_URL_TEMPLATE.format(
                slug=self.company_slug, posting_id=posting_id
            ),
            "applyUrl": APPLY_URL_TEMPLATE.format(
                slug=self.company_slug, posting_id=posting_id
            ),
        }

        # Only the free-text tier summary survives this endpoint; there are no
        # structured min/max components, so _parse_comp yields None and
        # salary_summary carries whatever the board displays.
        if posting.get("compensationTierSummary"):
            item["compensation"] = {
                "compensationTierSummary": posting["compensationTierSummary"]
            }

        return item
