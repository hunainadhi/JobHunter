import Link from "next/link";
import { Search, RefreshCw, Filter } from "lucide-react";
import { fetchLandingStats } from "@/lib/queries";
import { PLATFORMS } from "@/lib/types";

export const dynamic = "force-dynamic";

function formatLastScrape(iso: string | null): string {
  if (!iso) return "recently";
  const date = new Date(iso);
  const now = new Date();
  const diffMins = Math.floor((now.getTime() - date.getTime()) / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}

const steps = [
  {
    icon: RefreshCw,
    title: "Scrape every ATS, daily",
    body:
      "A scheduled pipeline crawls Greenhouse, Lever, Ashby, Workable, SmartRecruiters, and 8 more applicant-tracking platforms directly — no third-party job board, no stale syndication. New and updated postings are fetched every day.",
  },
  {
    icon: Search,
    title: "Every posting gets a vector embedding",
    body:
      "Each job's title, company, and location is converted into a vector embedding and stored in Postgres with pgvector. That's what powers the search bar: search “AI infra engineer” and get postings that match the meaning, not just the exact words.",
  },
  {
    icon: Filter,
    title: "Filtered down to what's real",
    body:
      "Postings are checked against Canadian locations and remote eligibility, deduplicated against companies you've blocked, and automatically expired once a listing goes quiet — so the board stays a list of jobs you can actually apply to.",
  },
];

export default async function LandingPage() {
  const { totalJobs, lastScrape } = await fetchLandingStats();

  return (
    <main>
      {/* Hero */}
      <section style={{ padding: "80px 24px 64px" }}>
        <div style={{ maxWidth: 780, margin: "0 auto", textAlign: "center" }}>
          <h1
            style={{
              fontSize: 48,
              fontWeight: 700,
              color: "var(--text-heading)",
              lineHeight: 1.1,
              letterSpacing: "-0.02em",
              marginBottom: 20,
            }}
          >
            One board. Every ATS.
            <br />
            Searched by meaning, not keywords.
          </h1>
          <p
            style={{
              fontSize: 18,
              color: "var(--text-body)",
              lineHeight: 1.7,
              maxWidth: 620,
              margin: "0 auto 32px",
            }}
          >
            JobHunter scrapes company career pages across Greenhouse, Lever, Ashby, and 9 other
            applicant-tracking systems every day, then embeds every posting as a vector so you can
            search job listings the way you'd describe them to a person.
          </p>
          <div className="flex items-center justify-center" style={{ gap: 12, marginBottom: 40 }}>
            <Link
              href="/jobs"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "14px 28px",
                fontSize: 16,
                fontWeight: 500,
                borderRadius: 8,
                background: "var(--bg-brand)",
                color: "var(--text-white)",
                textDecoration: "none",
                boxShadow:
                  "var(--shadow-xs), inset var(--color-1-400) 0 6px 0px -5px, var(--color-1-700) 0 4px 10px -5px",
              }}
            >
              Browse {totalJobs.toLocaleString()} open positions
            </Link>
          </div>

          {/* Live stat strip */}
          <div
            className="flex flex-wrap items-center justify-center"
            style={{ gap: "8px 32px", fontSize: 14, color: "var(--text-body-subtle)" }}
          >
            <span>
              <strong style={{ color: "var(--text-heading)", fontWeight: 600 }}>
                {totalJobs.toLocaleString()}
              </strong>{" "}
              live postings
            </span>
            <span aria-hidden style={{ color: "var(--border-default-strong)" }}>
              &middot;
            </span>
            <span>
              <strong style={{ color: "var(--text-heading)", fontWeight: 600 }}>
                {PLATFORMS.length}
              </strong>{" "}
              ATS sources
            </span>
            <span aria-hidden style={{ color: "var(--border-default-strong)" }}>
              &middot;
            </span>
            <span>Last scraped {formatLastScrape(lastScrape)}</span>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section style={{ padding: "40px 24px 80px", background: "var(--bg-neutral-secondary-soft)" }}>
        <div style={{ maxWidth: 1000, margin: "0 auto" }}>
          <h2
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: "var(--text-fg-brand)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              textAlign: "center",
              marginBottom: 12,
            }}
          >
            How it works
          </h2>
          <p
            style={{
              fontSize: 26,
              fontWeight: 600,
              color: "var(--text-heading)",
              textAlign: "center",
              marginBottom: 48,
            }}
          >
            No aggregator in the middle. Company pages, scraped directly.
          </p>

          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 24 }}>
            {steps.map((step) => (
              <div
                key={step.title}
                style={{
                  background: "var(--bg-neutral-primary-soft)",
                  border: "1px solid var(--border-default)",
                  borderRadius: 12,
                  padding: 28,
                  boxShadow: "var(--shadow-xs)",
                }}
              >
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 40,
                    height: 40,
                    borderRadius: 10,
                    background: "var(--bg-brand-softer)",
                    marginBottom: 16,
                  }}
                >
                  <step.icon size={20} color="var(--text-fg-brand)" />
                </div>
                <h3
                  style={{
                    fontSize: 17,
                    fontWeight: 600,
                    color: "var(--text-heading)",
                    marginBottom: 8,
                  }}
                >
                  {step.title}
                </h3>
                <p style={{ fontSize: 15, color: "var(--text-body)", lineHeight: 1.65 }}>
                  {step.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Sources */}
      <section style={{ padding: "80px 24px" }}>
        <div style={{ maxWidth: 780, margin: "0 auto", textAlign: "center" }}>
          <h2
            style={{
              fontSize: 26,
              fontWeight: 600,
              color: "var(--text-heading)",
              marginBottom: 12,
            }}
          >
            Scraped directly from {PLATFORMS.length} applicant-tracking systems
          </h2>
          <p style={{ fontSize: 16, color: "var(--text-body)", marginBottom: 32 }}>
            If a company posts through one of these, JobHunter sees it — usually the same day.
          </p>
          <div className="flex flex-wrap items-center justify-center" style={{ gap: 10 }}>
            {PLATFORMS.map((p) => (
              <span
                key={p.value}
                style={{
                  padding: "8px 16px",
                  fontSize: 14,
                  fontWeight: 500,
                  borderRadius: 8,
                  background: "var(--bg-neutral-secondary-medium)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-heading)",
                }}
              >
                {p.label}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section
        style={{
          padding: "64px 24px 96px",
          borderTop: "1px solid var(--border-default)",
        }}
      >
        <div style={{ maxWidth: 620, margin: "0 auto", textAlign: "center" }}>
          <h2
            style={{
              fontSize: 26,
              fontWeight: 600,
              color: "var(--text-heading)",
              marginBottom: 12,
            }}
          >
            Try a search that wouldn't work anywhere else
          </h2>
          <p style={{ fontSize: 16, color: "var(--text-body)", marginBottom: 28 }}>
            Type something like &ldquo;early-stage AI infra role&rdquo; instead of guessing exact
            keywords — the embeddings do the matching.
          </p>
          <Link
            href="/jobs"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "14px 28px",
              fontSize: 16,
              fontWeight: 500,
              borderRadius: 8,
              background: "var(--bg-brand)",
              color: "var(--text-white)",
              textDecoration: "none",
              boxShadow: "var(--shadow-xs)",
            }}
          >
            Open the job board
          </Link>
        </div>
      </section>
    </main>
  );
}
