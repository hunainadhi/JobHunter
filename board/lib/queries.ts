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

async function embedQuery(text: string): Promise<number[]> {
  const res = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${process.env.OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ model: "text-embedding-3-small", input: [text], dimensions: 256 }),
  });
  if (!res.ok) throw new Error(`Embedding API error: ${res.status}`);
  const data = await res.json();
  return data.data[0].embedding;
}

async function fetchJobsSemantic(
  params: BoardSearchParams,
  cutoff: string | null,
  sortField: string
): Promise<{ jobs: JobRow[]; totalCount: number }> {
  const page = Math.max(1, parseInt(params.page || "1", 10) || 1);
  const embedding = await embedQuery(params.q!.trim());

  const rpcParams: Record<string, any> = {
    query_embedding: embedding,
    match_threshold: 0.3,
    match_count: PAGE_SIZE,
    offset_val: (page - 1) * PAGE_SIZE,
    filter_location: params.location?.trim() || null,
    filter_company: params.company?.trim() || null,
    filter_platform: params.platform || null,
    filter_category: params.category || null,
    filter_level: params.level || null,
    filter_date_cutoff: cutoff,
  };

  const [{ data, error }, { data: countData, error: countError }] =
    await Promise.all([
      supabase.rpc("match_jobs", rpcParams),
      supabase.rpc("count_matched_jobs", {
        query_embedding: embedding,
        match_threshold: 0.3,
        filter_location: rpcParams.filter_location,
        filter_company: rpcParams.filter_company,
        filter_platform: rpcParams.filter_platform,
        filter_category: rpcParams.filter_category,
        filter_level: rpcParams.filter_level,
        filter_date_cutoff: cutoff,
      }),
    ]);

  if (error) {
    console.error("Semantic search error:", error);
    return { jobs: [], totalCount: 0 };
  }

  const jobs: JobRow[] = ((data as any[]) || []).map((row) => ({
    id: row.id,
    title: row.title,
    company_name: row.company_name,
    location: row.location,
    is_remote: row.is_remote,
    apply_url: row.apply_url,
    source_url: row.source_url,
    posted_at: row.posted_at,
    first_seen_at: row.first_seen_at,
    ats_platform: row.ats_platform,
    category: row.category,
  }));

  if (sortField === "posted_at") {
    jobs.sort((a, b) => {
      const dateA = a.posted_at || a.first_seen_at || "";
      const dateB = b.posted_at || b.first_seen_at || "";
      return dateB.localeCompare(dateA);
    });
  } else if (sortField === "title") {
    jobs.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
  }

  return { jobs, totalCount: countData ?? 0 };
}

export async function fetchJobs(params: BoardSearchParams): Promise<{
  jobs: JobRow[];
  totalCount: number;
}> {
  const page = Math.max(1, parseInt(params.page || "1", 10) || 1);
  const sortField = params.sort === "title" ? "title" : "posted_at";
  const sortAsc = params.sort === "title" ? true : false;
  const dateFilter = (params.date || "all") as DateFilter;
  const cutoff = getDateCutoff(dateFilter);

  if (params.q?.trim() && process.env.OPENAI_API_KEY) {
    try {
      return await fetchJobsSemantic(params, cutoff, sortField);
    } catch (e) {
      console.error("Semantic search failed, falling back to ILIKE:", e);
    }
  }

  const needsScores = !!params.category || !!params.level;

  let query;
  if (needsScores) {
    query = supabase
      .from("jobs")
      .select(
        `${JOB_COLUMNS}, scores!inner(category, level)`,
        { count: "exact" }
      )
      .neq("status", "expired");

    if (params.category) {
      query = query.eq("scores.category", params.category);
    }
    if (params.level) {
      query = query.eq("scores.level", params.level);
    }
  } else {
    query = supabase
      .from("jobs")
      .select(JOB_COLUMNS, { count: "exact" })
      .neq("status", "expired");
  }

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

  if (params.platform) {
    query = query.eq("ats_platform", params.platform);
  }

  if (cutoff) {
    query = query.or(
      `posted_at.gte.${cutoff},and(posted_at.is.null,first_seen_at.gte.${cutoff})`
    );
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

  let jobs: JobRow[];
  if (needsScores) {
    jobs = ((data as any[]) || []).map((row) => {
      const { scores, ...jobFields } = row as any;
      return { ...jobFields, category: scores?.category } as JobRow;
    });
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
