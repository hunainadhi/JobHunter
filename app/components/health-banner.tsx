import { supabase } from "@/lib/supabase";

type ScrapeRun = {
  ats_platform: string;
  completed_at: string | null;
  status: string;
  started_at: string;
};

function formatTimeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export async function HealthBanner() {
  const platforms = ["greenhouse", "lever", "ashby"];

  const { data: runs } = await supabase
    .from("scrape_runs")
    .select("ats_platform, completed_at, status, started_at")
    .order("started_at", { ascending: false })
    .limit(30);

  const health: Record<
    string,
    { lastSuccess: string | null; recentFailures: number }
  > = {};

  for (const platform of platforms) {
    const platformRuns = (runs || []).filter(
      (r: ScrapeRun) => r.ats_platform === platform
    );
    const lastSuccess = platformRuns.find(
      (r: ScrapeRun) => r.status === "success"
    );

    let consecutiveFailures = 0;
    for (const run of platformRuns) {
      if (run.status === "failure") consecutiveFailures++;
      else break;
    }

    health[platform] = {
      lastSuccess: lastSuccess?.completed_at || null,
      recentFailures: consecutiveFailures,
    };
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {platforms.map((platform) => {
        const h = health[platform];
        let pillColor = "bg-[#27272a] text-[#71717a]";
        let label = "No data";

        if (h?.lastSuccess) {
          label = formatTimeAgo(h.lastSuccess);
          if (h.recentFailures >= 3) {
            pillColor = "bg-red-900/50 text-red-400";
          } else if (h.recentFailures >= 1) {
            pillColor = "bg-yellow-900/50 text-yellow-400";
          } else {
            pillColor = "bg-emerald-900/50 text-emerald-400";
          }
        }

        return (
          <div
            key={platform}
            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs ${pillColor}`}
          >
            <span className="capitalize">{platform}</span>
            <span>{label}</span>
          </div>
        );
      })}
    </div>
  );
}
