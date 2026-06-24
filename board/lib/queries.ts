import { supabase } from "./supabase";
import type { JobRow, BoardSearchParams, DateFilter } from "./types";

const PAGE_SIZE = 30;

const COLUMNS = "id, title, company_name, location, is_remote, apply_url, source_url, posted_at, first_seen_at, ats_platform";

function escapeIlike(value: string): string {
  return value.replace(/%/g, "\\%").replace(/_/g, "\\_");
}

function getDateCutoff(filter: DateFilter): string | null {
  const now = new Date();
  switch (filter) {
    case "24h":
      now.setDate(now.getDate() - 1);
      return now.toISOString();
    case "7d":
      now.setDate(now.getDate() - 7);
      return now.toISOString();
    case "30d":
      now.setDate(now.getDate() - 30);
      return now.toISOString();
    default:
      return null;
  }
}

export async function fetchJobs(params: BoardSearchParams): Promise<{
  jobs: JobRow[];
  totalCount: number;
}> {
  const page = Math.max(1, parseInt(params.page || "1", 10) || 1);
  const sortField = params.sort === "title" ? "title" : "posted_at";
  const sortAsc = params.sort === "title" ? true : false;
  const dateFilter = (params.date || "all") as DateFilter;

  let query = supabase
    .from("jobs")
    .select(COLUMNS, { count: "exact" });

  if (params.q) {
    const escaped = escapeIlike(params.q.trim());
    query = query.or(`title.ilike.%${escaped}%,company_name.ilike.%${escaped}%`);
  }

  if (params.location) {
    const escaped = escapeIlike(params.location.trim());
    const locationLower = params.location.trim().toLowerCase();
    if (locationLower === "remote") {
      query = query.or(`location.ilike.%${escaped}%,is_remote.eq.true`);
    } else {
      query = query.ilike("location", `%${escaped}%`);
    }
  }

  if (params.company) {
    const escaped = escapeIlike(params.company.trim());
    query = query.ilike("company_name", `%${escaped}%`);
  }

  const cutoff = getDateCutoff(dateFilter);
  if (cutoff) {
    query = query.or(`posted_at.gte.${cutoff},and(posted_at.is.null,first_seen_at.gte.${cutoff})`);
  }

  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  query = query
    .order(sortField, { ascending: sortAsc, nullsFirst: false })
    .range(from, to);

  const { data, count, error } = await query;

  if (error) {
    console.error("Supabase query error:", error);
    return { jobs: [], totalCount: 0 };
  }

  return {
    jobs: (data as JobRow[]) || [],
    totalCount: count || 0,
  };
}

export { PAGE_SIZE };
