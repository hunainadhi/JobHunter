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
  category?: string | null;
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
  category?: string;
  level?: string;
  platform?: string;
};

export const CATEGORIES = [
  "Software & Engineering",
  "Data & Analytics",
  "Design & Creative",
  "Product & Project Management",
  "Business & Operations",
  "Sales & Marketing",
  "Finance & Accounting",
  "Healthcare",
  "Human Resources",
  "Skilled Trades & Labor",
  "Education & Research",
  "Other",
] as const;

export const PLATFORMS = [
  { value: "greenhouse", label: "Greenhouse" },
  { value: "lever", label: "Lever" },
  { value: "ashby", label: "Ashby" },
  { value: "smartrecruiters", label: "SmartRecruiters" },
  { value: "workable", label: "Workable" },
  { value: "rippling", label: "Rippling" },
  { value: "ycombinator", label: "YC" },
  { value: "themuse", label: "The Muse" },
  { value: "weworkremotely", label: "WWR" },
  { value: "icims", label: "iCIMS" },
  { value: "pinpoint", label: "Pinpoint" },
  { value: "teamtailor", label: "Teamtailor" },
  { value: "breezy", label: "Breezy" },
] as const;

export const LEVELS = [
  { value: "intern", label: "Intern / Co-op" },
  { value: "entry", label: "Entry / Junior" },
  { value: "mid", label: "Mid-level" },
  { value: "senior", label: "Senior+" },
] as const;
