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

  const scoreFields = "score, role_fit_score, seniority_fit_score, stack_overlap_score, keyword_score, matched_skills, rationale, job_id, jobs!inner(id, title, company_name, location, source_url, first_seen_at, posted_at, ats_platform, ats_token)";

  const allScoreRows: any[] = [];
  const PAGE_SIZE = 1000;
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const { data } = await supabase
      .from("scores")
      .select(scoreFields)
      .eq("model", "MiniMax-M3")
      .gt("score", 60)
      .range(offset, offset + PAGE_SIZE - 1);
    if (!data || data.length === 0) break;
    allScoreRows.push(...data);
    if (data.length < PAGE_SIZE) break;
  }
  const scoreRows = allScoreRows;

  const TITLE_EXCLUDE = ["intern", "internship", "co-op", "coop", "co op"];
  const cutoffDate = new Date();
  cutoffDate.setMonth(cutoffDate.getMonth() - 2);

  const filteredJobs: JobRow[] = [];
  for (const row of scoreRows || []) {
    const job = (row as any).jobs;
    if (!job) continue;
    if (blacklistedNames.has(job.company_name.toLowerCase())) continue;
    const titleLower = job.title.toLowerCase();
    if (TITLE_EXCLUDE.some((kw: string) => titleLower.includes(kw))) continue;
    const jobDate = new Date(job.posted_at || job.first_seen_at);
    if (jobDate < cutoffDate) continue;
    if (row.score > 60) {
      filteredJobs.push({
        ...job,
        scores: [{
          score: row.score,
          role_fit_score: row.role_fit_score,
          seniority_fit_score: row.seniority_fit_score,
          stack_overlap_score: row.stack_overlap_score,
          keyword_score: row.keyword_score,
          matched_skills: row.matched_skills,
          rationale: row.rationale,
        }],
      });
    }
  }

  const totalCount = filteredJobs.length;

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold tracking-widest uppercase text-[#fafafa]">
            JobHunter
          </h1>
          <div className="flex items-center gap-4">
            <a
              href="/stats"
              className="text-sm text-[#71717a] hover:text-[#fafafa] transition-colors"
            >
              Stats
            </a>
            <a
              href="/blacklist"
              className="text-sm text-[#71717a] hover:text-[#fafafa] transition-colors"
            >
              Blacklist
            </a>
          </div>
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
