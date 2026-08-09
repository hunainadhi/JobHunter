import { supabase } from "@/lib/supabase";
import { JobTable } from "@/components/job-table";
import { HealthBanner } from "@/components/health-banner";

export const dynamic = "force-dynamic";

const SCORING_MODEL = process.env.OPENROUTER_MODEL ?? "qwen/qwen3-30b-a3b";

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

  const scoreFields = "score, matched_skills, rationale, job_id, jobs!inner(id, title, company_name, location, source_url, first_seen_at, posted_at, ats_platform, ats_token)";

  const allScoreRows: any[] = [];
  const PAGE_SIZE = 1000;
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const { data } = await supabase
      .from("scores")
      .select(scoreFields)
      .in("model", [SCORING_MODEL, "MiniMax-M3"])
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
  const seenJobIds = new Set<string>();
  // Prefer the active scorer while preserving historical matches that cannot be
  // rescored because their source descriptions have already been removed.
  scoreRows.sort((a, b) => Number(b.model === SCORING_MODEL) - Number(a.model === SCORING_MODEL));
  for (const row of scoreRows || []) {
    const job = (row as any).jobs;
    if (!job) continue;
    if (seenJobIds.has(job.id)) continue;
    if (blacklistedNames.has(job.company_name.toLowerCase())) continue;
    const titleLower = job.title.toLowerCase();
    if (TITLE_EXCLUDE.some((kw: string) => titleLower.includes(kw))) continue;
    const jobDate = new Date(job.posted_at || job.first_seen_at);
    if (jobDate < cutoffDate) continue;
    if (row.score > 60) {
      seenJobIds.add(job.id);
      filteredJobs.push({
        ...job,
          scores: [{
            score: row.score,
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
