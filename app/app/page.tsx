import { supabase } from "@/lib/supabase";
import { JobTable } from "@/components/job-table";
import { HealthBanner } from "@/components/health-banner";

export const dynamic = "force-dynamic";

type JobRow = {
  id: string;
  title: string;
  company_name: string;
  location: string | null;
  source_url: string;
  first_seen_at: string;
  posted_at: string | null;
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

export default async function Home() {

  const { data: blacklist } = await supabase
    .from("blacklisted_companies")
    .select("company_name");
  const blacklistedNames = new Set(
    (blacklist || []).map((b) => b.company_name.toLowerCase())
  );

  const jobFields = "id, title, company_name, location, source_url, first_seen_at, posted_at, ats_platform, ats_token, scores(score, role_fit_score, seniority_fit_score, stack_overlap_score, keyword_score, matched_skills, rationale)";

  const [{ data: matchedJobs }, { data: scoredJobs }] = await Promise.all([
    supabase
      .from("jobs")
      .select(jobFields)
      .eq("status", "matched")
      .order("first_seen_at", { ascending: false })
      .limit(5000),
    supabase
      .from("jobs")
      .select(jobFields)
      .eq("status", "scored")
      .order("first_seen_at", { ascending: false })
      .limit(5000),
  ]);

  const jobs = [...(matchedJobs || []), ...(scoredJobs || [])];

  const TITLE_EXCLUDE = ["intern", "internship", "co-op", "coop", "co op"];

  const filteredJobs = ((jobs as JobRow[] | null) || []).filter((j) => {
    if (blacklistedNames.has(j.company_name.toLowerCase())) return false;
    const titleLower = j.title.toLowerCase();
    if (TITLE_EXCLUDE.some((kw) => titleLower.includes(kw))) return false;
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

        <JobTable jobs={filteredJobs} />
      </div>
    </main>
  );
}
