import { getSupabase } from "./supabase";
import type { JobRow, BoardSearchParams, DateFilter, PlaceOption } from "./types";
import { DEFAULT_RADIUS_KM } from "./types";

const PAGE_SIZE = 30;
const SCORING_MODEL = process.env.OPENROUTER_MODEL ?? "qwen/qwen3-30b-a3b";

async function withRetry<T>(fn: () => Promise<T>, retries = 1, delayMs = 1500): Promise<T> {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (e) {
      if (attempt === retries) throw e;
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  throw new Error("unreachable");
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

export async function fetchJobs(params: BoardSearchParams): Promise<{
  jobs: JobRow[];
  totalCount: number;
}> {
  return withRetry(() => fetchJobsInner(params));
}

/**
 * Single query path for the board.
 *
 * Keyword and semantic search used to be two separate queries — a PostgREST
 * query builder and the match_jobs RPC — which could disagree on filters and
 * pinned different scoring models. Radius search cannot be expressed in the
 * query builder at all (it needs an EXISTS against a view), so both now go
 * through search_jobs.
 */
async function fetchJobsInner(params: BoardSearchParams): Promise<{
  jobs: JobRow[];
  totalCount: number;
}> {
  const page = Math.max(1, parseInt(params.page || "1", 10) || 1);
  const dateFilter = (params.date || "all") as DateFilter;
  const cutoff = getDateCutoff(dateFilter);
  const query = params.q?.trim() || null;
  const place = params.place?.trim() || null;

  let radius = parseInt(params.radius || "", 10);
  if (!Number.isFinite(radius) || radius <= 0) radius = DEFAULT_RADIUS_KM;

  // Embed only when a term was typed. A failure falls back to ILIKE rather than
  // dropping the search entirely.
  let embedding: number[] | null = null;
  if (query && process.env.OPENAI_API_KEY) {
    try {
      embedding = await embedQuery(query);
    } catch (e) {
      console.error("Embedding failed, falling back to keyword match:", e);
    }
  }

  let sortBy: string;
  if (params.sort === "title" || params.sort === "posted_at" || params.sort === "distance") {
    sortBy = params.sort;
  } else if (embedding) {
    sortBy = "similarity";       // no explicit choice + a term → rank by relevance
  } else if (place) {
    sortBy = "distance";         // no explicit choice + a place → nearest first
  } else {
    sortBy = "posted_at";
  }

  const { data, error } = await getSupabase().rpc("search_jobs", {
    query_embedding: embedding,
    match_threshold: 0.3,
    match_count: PAGE_SIZE,
    offset_val: (page - 1) * PAGE_SIZE,
    sort_by: sortBy,
    filter_q: embedding ? null : query,
    filter_location: params.location?.trim() || null,
    filter_place: place,
    filter_radius_km: radius,
    include_remote: params.remote !== "0",
    filter_company: params.company?.trim() || null,
    filter_platform: params.platform || null,
    filter_category: params.category || null,
    filter_level: params.level || null,
    filter_date_cutoff: cutoff,
    scoring_model: SCORING_MODEL,
  });

  if (error) {
    console.error("search_jobs error:", error);
    throw error;
  }

  const rows = (data as Record<string, unknown>[]) || [];
  const jobs: JobRow[] = rows.map((row) => ({
    id: row.id as string,
    title: row.title as string,
    company_name: row.company_name as string,
    location: row.location as string | null,
    is_remote: row.is_remote as boolean,
    apply_url: row.apply_url as string,
    source_url: row.source_url as string | null,
    posted_at: row.posted_at as string | null,
    first_seen_at: row.first_seen_at as string,
    ats_platform: row.ats_platform as string,
    category: row.category as string | null,
    location_status: row.location_status as string | null,
    distance_km: row.distance_km === null ? null : Number(row.distance_km),
  }));

  return { jobs, totalCount: Number(rows[0]?.total_count ?? 0) };
}

/**
 * Places that actually have jobs, for the location autocomplete.
 *
 * Sent to the client once and filtered in memory — a few hundred rows, so
 * typing costs no round-trip, and a suggestion can never lead to an empty page.
 */
export async function fetchPlacesWithJobs(): Promise<PlaceOption[]> {
  try {
    const { data, error } = await getSupabase().rpc("places_with_jobs");
    if (error) throw error;
    return ((data as Record<string, unknown>[]) || []).map((row) => ({
      slug: row.slug as string,
      name: row.name as string,
      province: row.province as string,
      job_count: Number(row.job_count ?? 0),
    }));
  } catch (e) {
    // The board must still render if the gazetteer isn't seeded yet; the
    // location box falls back to plain free text.
    console.error("places_with_jobs unavailable:", e);
    return [];
  }
}

export async function fetchLastScrape(): Promise<string | null> {
  const { data } = await getSupabase()
    .from("scrape_runs")
    .select("completed_at")
    .eq("status", "success")
    .order("completed_at", { ascending: false, nullsFirst: false })
    .limit(1)
    .single();

  return data?.completed_at || null;
}

export async function fetchLandingStats(): Promise<{ totalJobs: number; lastScrape: string | null }> {
  const [{ count }, lastScrape] = await Promise.all([
    getSupabase().from("jobs").select("id", { count: "exact", head: true }).neq("status", "expired"),
    fetchLastScrape(),
  ]);

  return { totalJobs: count || 0, lastScrape };
}

export { PAGE_SIZE };
