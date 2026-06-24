export type JobRow = {
  id: string;
  title: string;
  company_name: string;
  location: string | null;
  is_remote: boolean;
  apply_url: string;
  source_url: string | null;
  posted_at: string | null;
  first_seen_at: string;
  ats_platform: string;
};

export type DateFilter = "24h" | "7d" | "30d" | "all";
export type SortField = "posted_at" | "title";
export type SortOrder = "asc" | "desc";

export type BoardSearchParams = {
  q?: string;
  location?: string;
  company?: string;
  date?: string;
  sort?: string;
  order?: string;
  page?: string;
};
