import { supabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";

type ScrapeRun = {
  ats_platform: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  companies_scraped: number;
  jobs_found: number;
  jobs_new: number;
};

type ScoreRow = {
  model: string;
  score: number;
  scored_at: string;
};

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const mins = Math.floor(ms / 60000);
  const secs = Math.floor((ms % 60000) / 1000);
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export default async function StatsPage() {
  // Fetch all scrape runs
  const { data: allRuns } = await supabase
    .from("scrape_runs")
    .select("ats_platform, started_at, completed_at, status, companies_scraped, jobs_found, jobs_new")
    .order("started_at", { ascending: false })
    .limit(500);

  // Fetch all scores with timestamps
  const allScores: ScoreRow[] = [];
  const PAGE_SIZE = 1000;
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const { data } = await supabase
      .from("scores")
      .select("model, score, scored_at")
      .range(offset, offset + PAGE_SIZE - 1);
    if (!data || data.length === 0) break;
    allScores.push(...data);
    if (data.length < PAGE_SIZE) break;
  }

  // Job status counts
  const [
    { count: newCount },
    { count: scoredCount },
    { count: matchedCount },
  ] = await Promise.all([
    supabase.from("jobs").select("id", { count: "exact", head: true }).eq("status", "new"),
    supabase.from("jobs").select("id", { count: "exact", head: true }).eq("status", "scored"),
    supabase.from("jobs").select("id", { count: "exact", head: true }).eq("status", "matched"),
  ]);
  const totalJobs = (newCount || 0) + (scoredCount || 0) + (matchedCount || 0);

  // Aggregate ingestion stats
  const runs = allRuns || [];
  const totalCompaniesScraped = runs.reduce((s, r) => s + (r.companies_scraped || 0), 0);
  const totalJobsFound = runs.reduce((s, r) => s + (r.jobs_found || 0), 0);
  const totalJobsNew = runs.reduce((s, r) => s + (r.jobs_new || 0), 0);
  const successRuns = runs.filter((r) => r.status === "success").length;
  const failedRuns = runs.filter((r) => r.status === "failure").length;

  // Per-platform stats
  const platforms = [...new Set(runs.map((r) => r.ats_platform))].sort();
  const platformStats = platforms.map((p) => {
    const pRuns = runs.filter((r) => r.ats_platform === p);
    const lastRun = pRuns[0];
    return {
      platform: p,
      totalRuns: pRuns.length,
      totalFound: pRuns.reduce((s, r) => s + (r.jobs_found || 0), 0),
      totalNew: pRuns.reduce((s, r) => s + (r.jobs_new || 0), 0),
      lastRun,
      lastDuration:
        lastRun?.completed_at
          ? formatDuration(lastRun.started_at, lastRun.completed_at)
          : "—",
    };
  });

  // Scoring stats
  const minimaxScores = allScores.filter((s) => s.model === "MiniMax-M3");
  const keywordFiltered = allScores.filter((s) => s.model === "keyword-filter");
  const matchCount = minimaxScores.filter((s) => s.score >= 60).length;
  const avgScore =
    minimaxScores.length > 0
      ? Math.round(minimaxScores.reduce((s, r) => s + r.score, 0) / minimaxScores.length)
      : 0;

  // Score distribution
  const buckets = [
    { label: "90-100", min: 90, max: 101 },
    { label: "80-89", min: 80, max: 90 },
    { label: "70-79", min: 70, max: 80 },
    { label: "60-69", min: 60, max: 70 },
    { label: "40-59", min: 40, max: 60 },
    { label: "20-39", min: 20, max: 40 },
    { label: "0-19", min: 0, max: 20 },
  ];
  const distribution = buckets.map((b) => ({
    ...b,
    count: minimaxScores.filter((s) => s.score >= b.min && s.score < b.max).length,
  }));
  const maxBucket = Math.max(...distribution.map((d) => d.count), 1);

  // Cost estimates (Lambda GB-seconds)
  // Ingestion: 12 workers × ~15 min × 256MB = ~720 GB-sec per run
  // Scoring: ~2 invocations × ~3 min × 256MB = ~23 GB-sec per run
  const ingestionRuns = new Set(runs.map((r) => r.started_at.slice(0, 10))).size;
  const estIngestionGBSec = ingestionRuns * 720;
  const estScoringGBSec = ingestionRuns * 90;
  const estTotalGBSec = estIngestionGBSec + estScoringGBSec;
  const freeTierLimit = 400000;
  const freeTierPct = ((estTotalGBSec / freeTierLimit) * 100).toFixed(1);

  // MiniMax token estimate (~1500 tokens per job scored)
  const estTokens = minimaxScores.length * 1500;

  // Daily breakdown (last 7 days)
  const today = new Date();
  const dailyStats = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    const dayRuns = runs.filter((r) => r.started_at.startsWith(dateStr));
    const dayScores = minimaxScores.filter((s) => s.scored_at?.startsWith(dateStr));
    const dayMatches = dayScores.filter((s) => s.score >= 60).length;
    dailyStats.push({
      date: dateStr,
      jobsNew: dayRuns.reduce((s, r) => s + (r.jobs_new || 0), 0),
      scored: dayScores.length,
      matches: dayMatches,
    });
  }

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold tracking-widest uppercase text-[#fafafa]">
            Pipeline Stats
          </h1>
          <a
            href="/"
            className="text-sm text-[#71717a] hover:text-[#fafafa] transition-colors"
          >
            &larr; Back
          </a>
        </div>

        {/* Overview cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total Jobs", value: totalJobs.toLocaleString() },
            { label: "Matched (>=60)", value: matchedCount?.toLocaleString() || "0" },
            { label: "MiniMax Scored", value: minimaxScores.length.toLocaleString() },
            { label: "Keyword Filtered", value: keywordFiltered.length.toLocaleString() },
            { label: "Avg MiniMax Score", value: `${avgScore}/100` },
            { label: "Scrape Runs", value: runs.length.toString() },
            { label: "Companies Scraped", value: totalCompaniesScraped.toLocaleString() },
            { label: "Est. Tokens Used", value: estTokens > 1000000 ? `${(estTokens / 1000000).toFixed(1)}M` : `${(estTokens / 1000).toFixed(0)}K` },
          ].map((card) => (
            <div
              key={card.label}
              className="rounded-lg border border-[#27272a] bg-[#18181b] p-4"
            >
              <div className="text-xs text-[#71717a] mb-1">{card.label}</div>
              <div className="text-xl font-bold text-[#fafafa]">{card.value}</div>
            </div>
          ))}
        </div>

        {/* Cost estimate */}
        <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-6 mb-8">
          <h2 className="text-sm font-semibold text-[#fafafa] mb-4 uppercase tracking-wider">
            Lambda Cost Estimate
          </h2>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <div className="text-xs text-[#71717a]">Ingestion</div>
              <div className="text-lg font-bold text-[#fafafa]">
                {estIngestionGBSec.toLocaleString()} GB-sec
              </div>
            </div>
            <div>
              <div className="text-xs text-[#71717a]">Scoring</div>
              <div className="text-lg font-bold text-[#fafafa]">
                {estScoringGBSec.toLocaleString()} GB-sec
              </div>
            </div>
            <div>
              <div className="text-xs text-[#71717a]">Total</div>
              <div className="text-lg font-bold text-[#fafafa]">
                {estTotalGBSec.toLocaleString()} GB-sec
              </div>
            </div>
          </div>
          <div className="w-full bg-[#27272a] rounded-full h-3 mb-2">
            <div
              className="bg-emerald-500 h-3 rounded-full transition-all"
              style={{ width: `${Math.min(parseFloat(freeTierPct), 100)}%` }}
            />
          </div>
          <div className="text-xs text-[#71717a]">
            {freeTierPct}% of Lambda free tier ({freeTierLimit.toLocaleString()} GB-sec/month)
          </div>
        </div>

        {/* Daily breakdown */}
        <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-6 mb-8">
          <h2 className="text-sm font-semibold text-[#fafafa] mb-4 uppercase tracking-wider">
            Daily Breakdown (Last 7 Days)
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[#71717a] text-xs uppercase">
                <th className="text-left py-2">Date</th>
                <th className="text-right py-2">New Jobs</th>
                <th className="text-right py-2">Scored</th>
                <th className="text-right py-2">Matches</th>
              </tr>
            </thead>
            <tbody>
              {dailyStats.map((d) => (
                <tr key={d.date} className="border-t border-[#27272a]">
                  <td className="py-2 text-[#fafafa]">{d.date}</td>
                  <td className="py-2 text-right text-[#a1a1aa]">{d.jobsNew}</td>
                  <td className="py-2 text-right text-[#a1a1aa]">{d.scored}</td>
                  <td className="py-2 text-right text-emerald-400">{d.matches}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Score distribution */}
        <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-6 mb-8">
          <h2 className="text-sm font-semibold text-[#fafafa] mb-4 uppercase tracking-wider">
            Score Distribution (MiniMax)
          </h2>
          <div className="space-y-2">
            {distribution.map((d) => (
              <div key={d.label} className="flex items-center gap-3">
                <div className="w-12 text-xs text-[#71717a] text-right">{d.label}</div>
                <div className="flex-1 bg-[#27272a] rounded h-5 overflow-hidden">
                  <div
                    className={`h-full rounded ${d.min >= 60 ? "bg-emerald-600" : d.min >= 40 ? "bg-yellow-600" : "bg-red-900"}`}
                    style={{ width: `${(d.count / maxBucket) * 100}%` }}
                  />
                </div>
                <div className="w-10 text-xs text-[#a1a1aa] text-right">{d.count}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Platform breakdown */}
        <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-6 mb-8">
          <h2 className="text-sm font-semibold text-[#fafafa] mb-4 uppercase tracking-wider">
            Platform Breakdown
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[#71717a] text-xs uppercase">
                <th className="text-left py-2">Platform</th>
                <th className="text-right py-2">Runs</th>
                <th className="text-right py-2">Jobs Found</th>
                <th className="text-right py-2">Jobs New</th>
                <th className="text-right py-2">Last Duration</th>
                <th className="text-right py-2">Last Status</th>
              </tr>
            </thead>
            <tbody>
              {platformStats.map((p) => (
                <tr key={p.platform} className="border-t border-[#27272a]">
                  <td className="py-2 text-[#fafafa] capitalize">{p.platform}</td>
                  <td className="py-2 text-right text-[#a1a1aa]">{p.totalRuns}</td>
                  <td className="py-2 text-right text-[#a1a1aa]">{p.totalFound.toLocaleString()}</td>
                  <td className="py-2 text-right text-[#a1a1aa]">{p.totalNew.toLocaleString()}</td>
                  <td className="py-2 text-right text-[#a1a1aa]">{p.lastDuration}</td>
                  <td className="py-2 text-right">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-xs ${
                        p.lastRun?.status === "success"
                          ? "bg-emerald-900/50 text-emerald-400"
                          : p.lastRun?.status === "partial_failure"
                            ? "bg-yellow-900/50 text-yellow-400"
                            : "bg-red-900/50 text-red-400"
                      }`}
                    >
                      {p.lastRun?.status || "—"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Recent runs */}
        <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-6">
          <h2 className="text-sm font-semibold text-[#fafafa] mb-4 uppercase tracking-wider">
            Recent Scrape Runs
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[#71717a] text-xs uppercase">
                <th className="text-left py-2">Platform</th>
                <th className="text-left py-2">Started</th>
                <th className="text-right py-2">Duration</th>
                <th className="text-right py-2">Found</th>
                <th className="text-right py-2">New</th>
                <th className="text-right py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 20).map((r, i) => (
                <tr key={i} className="border-t border-[#27272a]">
                  <td className="py-2 text-[#fafafa] capitalize">{r.ats_platform}</td>
                  <td className="py-2 text-[#a1a1aa]">{formatDate(r.started_at)}</td>
                  <td className="py-2 text-right text-[#a1a1aa]">
                    {r.completed_at ? formatDuration(r.started_at, r.completed_at) : "—"}
                  </td>
                  <td className="py-2 text-right text-[#a1a1aa]">{r.jobs_found}</td>
                  <td className="py-2 text-right text-[#a1a1aa]">{r.jobs_new}</td>
                  <td className="py-2 text-right">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-xs ${
                        r.status === "success"
                          ? "bg-emerald-900/50 text-emerald-400"
                          : r.status === "partial_failure"
                            ? "bg-yellow-900/50 text-yellow-400"
                            : "bg-red-900/50 text-red-400"
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
