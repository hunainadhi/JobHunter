import { supabase } from "./supabase";
import type { JobRow, BoardSearchParams, DateFilter } from "./types";

const PAGE_SIZE = 30;

const JOB_COLUMNS = "id, title, company_name, location, is_remote, apply_url, source_url, posted_at, first_seen_at, ats_platform";

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

  const needsScores = !!params.category || !!params.level;

  let query;
  if (needsScores) {
    query = supabase
      .from("scores")
      .select(
        `category, level, jobs!inner(${JOB_COLUMNS})`,
        { count: "exact" }
      );

    if (params.category) {
      query = query.eq("category", params.category);
    }
    if (params.level) {
      query = query.eq("level", params.level);
    }
  } else {
    query = supabase
      .from("jobs")
      .select(JOB_COLUMNS, { count: "exact" });
  }

  const prefix = needsScores ? "jobs." : "";

  if (params.q) {
    const escaped = escapeIlike(params.q.trim());
    query = query.or(`${prefix}title.ilike.%${escaped}%,${prefix}company_name.ilike.%${escaped}%`);
  }

  if (params.location) {
    const escaped = escapeIlike(params.location.trim());
    const locationLower = params.location.trim().toLowerCase();
    if (locationLower === "remote") {
      query = query.or(`${prefix}location.ilike.%${escaped}%,${prefix}is_remote.eq.true`);
    } else {
      query = query.ilike(`${prefix}location`, `%${escaped}%`);
    }
  }

  if (params.company) {
    const escaped = escapeIlike(params.company.trim());
    query = query.ilike(`${prefix}company_name`, `%${escaped}%`);
  }

  if (params.platform) {
    query = query.eq(`${prefix}ats_platform`, params.platform);
  }

  const cutoff = getDateCutoff(dateFilter);
  if (cutoff) {
    query = query.or(
      `${prefix}posted_at.gte.${cutoff},and(${prefix}posted_at.is.null,${prefix}first_seen_at.gte.${cutoff})`
    );
  }

  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  if (needsScores) {
    query = query
      .order("posted_at", { referencedTable: "jobs", ascending: sortAsc, nullsFirst: false })
      .range(from, to);
  } else {
    query = query
      .order(sortField, { ascending: sortAsc, nullsFirst: false })
      .range(from, to);
  }

  const { data, count, error } = await query;

  if (error) {
    console.error("Supabase query error:", error);
    return { jobs: [], totalCount: 0 };
  }

  let jobs: JobRow[];
  if (needsScores) {
    jobs = ((data as any[]) || []).map((row) => ({
      ...row.jobs,
      category: row.category,
    }));
  } else {
    jobs = (data as JobRow[]) || [];
  }

  return {
    jobs,
    totalCount: count || 0,
  };
}

export async function fetchLastScrape(): Promise<string | null> {
  const { data } = await supabase
    .from("scrape_runs")
    .select("completed_at")
    .eq("status", "success")
    .order("completed_at", { ascending: false, nullsFirst: false })
    .limit(1)
    .single();

  return data?.completed_at || null;
}

export { PAGE_SIZE };
