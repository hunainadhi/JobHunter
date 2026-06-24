import { Suspense } from "react";
import { fetchJobs, PAGE_SIZE } from "@/lib/queries";
import type { BoardSearchParams } from "@/lib/types";
import { SearchFilters } from "@/components/search-filters";
import { JobBoardTable } from "@/components/job-board-table";
import { Pagination } from "@/components/pagination";

export const dynamic = "force-dynamic";

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

  const { jobs, totalCount } = await fetchJobs(params);
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
            Browse {totalCount.toLocaleString()} open tech positions across Canada
          </p>
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
