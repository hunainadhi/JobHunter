import { Suspense } from "react";
import { fetchJobs, fetchLastScrape, PAGE_SIZE } from "@/lib/queries";
import type { BoardSearchParams } from "@/lib/types";
import { SearchFilters } from "@/components/search-filters";
import { JobBoardTable } from "@/components/job-board-table";
import { Pagination } from "@/components/pagination";

export const dynamic = "force-dynamic";

function formatLastScrape(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export default async function BoardPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const raw = await searchParams;

  const params: BoardSearchParams = {
    q: typeof raw.q === "string" ? raw.q : undefined,
    location: typeof raw.location === "string" ? raw.location : undefined,
    company: typeof raw.company === "string" ? raw.company : undefined,
    date: typeof raw.date === "string" ? raw.date : undefined,
    sort: typeof raw.sort === "string" ? raw.sort : undefined,
    order: typeof raw.order === "string" ? raw.order : undefined,
    page: typeof raw.page === "string" ? raw.page : undefined,
  };

  const [{ jobs, totalCount }, lastScrape] = await Promise.all([
    fetchJobs(params),
    fetchLastScrape(),
  ]);
  const currentPage = Math.max(1, parseInt(params.page || "1", 10) || 1);
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  const cleanParams: Record<string, string> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v) cleanParams[k] = v;
  }
  delete cleanParams.page;

  return (
    <main style={{ minHeight: "100dvh", padding: "48px 24px" }}>
      <div style={{ maxWidth: 1152, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 48 }}>
          <h1
            style={{
              fontSize: 32,
              fontWeight: 600,
              color: "var(--text-heading)",
              lineHeight: 1,
              marginBottom: 16,
            }}
          >
            Job Board
          </h1>
          <p style={{ fontSize: 16, color: "var(--text-body)", lineHeight: 1.7 }}>
            Browse {totalCount.toLocaleString()} open positions across Canada
          </p>
          {lastScrape && (
            <p style={{ fontSize: 14, color: "var(--text-body-subtle)", marginTop: 8 }}>
              Last updated {formatLastScrape(lastScrape)}
            </p>
          )}
        </div>

        {/* Filters */}
        <Suspense>
          <SearchFilters />
        </Suspense>

        {/* Table */}
        <JobBoardTable jobs={jobs} />

        {/* Pagination */}
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          searchParams={cleanParams}
        />
      </div>
    </main>
  );
}
