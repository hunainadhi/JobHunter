import { supabase } from "@/lib/supabase";
import { JobTable } from "@/components/job-table";
import { HealthBanner } from "@/components/health-banner";

export const dynamic = "force-dynamic";

type JobRow = {
  id: string;
  title: string;
  company_name: string;
  location: string | null;
  apply_url: string;
  first_seen_at: string;
  ats_platform: string;
  ats_token: string;
  scores: {
    score: number;
    role_fit_score: number | null;
    seniority_fit_score: number | null;
    stack_overlap_score: number | null;
    keyword_score: number | null;
    matched_skills: string[] | null;
    rationale: string | null;
  }[];
};

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const params = await searchParams;
  const page = Math.max(1, parseInt(params.page || "1", 10));
  const pageSize = 25;
  const offset = (page - 1) * pageSize;

  const { data: blacklist } = await supabase
    .from("blacklisted_companies")
    .select("company_name");
  const blacklistedNames = new Set(
    (blacklist || []).map((b) => b.company_name.toLowerCase())
  );

  const { data: jobs } = await supabase
    .from("jobs")
    .select(
      "id, title, company_name, location, apply_url, first_seen_at, ats_platform, ats_token, scores(score, role_fit_score, seniority_fit_score, stack_overlap_score, keyword_score, matched_skills, rationale)"
    )
    .in("status", ["matched", "scored"])
    .order("first_seen_at", { ascending: false });

  const filteredJobs = ((jobs as JobRow[] | null) || []).filter((j) => {
    if (blacklistedNames.has(j.company_name.toLowerCase())) return false;
    const s = j.scores?.[0];
    if (!s) return false;
    const computedScore =
      (s.role_fit_score || 0) +
      (s.seniority_fit_score || 0) +
      (s.stack_overlap_score || 0) +
      (s.keyword_score || 0);
    return s.score >= 70 || computedScore >= 70;
  });

  const totalCount = filteredJobs.length;
  const paginatedJobs = filteredJobs.slice(offset, offset + pageSize);

  const totalPages = Math.ceil(totalCount / pageSize);

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold tracking-widest uppercase text-[#fafafa]">
            JobHunter
          </h1>
          <a
            href="/blacklist"
            className="text-sm text-[#71717a] hover:text-[#fafafa] transition-colors"
          >
            Blacklist
          </a>
        </div>

        <HealthBanner />

        <div className="mt-4 mb-4 text-sm text-[#71717a]">
          {totalCount} matches found
        </div>

        <JobTable jobs={paginatedJobs} />

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-4 mt-6">
            {page > 1 && (
              <a
                href={`/?page=${page - 1}`}
                className="px-4 py-2 text-sm rounded border border-[#27272a] bg-[#18181b] text-[#fafafa] hover:bg-[#27272a] transition-colors"
              >
                Previous
              </a>
            )}
            <span className="text-sm text-[#71717a]">
              Page {page} of {totalPages}
            </span>
            {page < totalPages && (
              <a
                href={`/?page=${page + 1}`}
                className="px-4 py-2 text-sm rounded border border-[#27272a] bg-[#18181b] text-[#fafafa] hover:bg-[#27272a] transition-colors"
              >
                Next
              </a>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
