"use client";

import type { JobRow } from "@/lib/types";
import { ExternalLink } from "lucide-react";

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function formatRelativeDate(dateStr: string | null, fallback: string): string {
  const date = new Date(dateStr || fallback);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  const month = MONTH_NAMES[date.getMonth()];
  const day = date.getDate();
  const prefix = `${month} ${day}`;

  if (diffDays < 0) return `${prefix}`;
  if (diffDays === 0) return `${prefix} (Today)`;
  if (diffDays === 1) return `${prefix} (Yesterday)`;
  if (diffDays < 7) return `${prefix} (${diffDays}d ago)`;
  if (diffDays < 30) return `${prefix} (${Math.floor(diffDays / 7)}w ago)`;
  if (diffDays < 365) return `${prefix} (${Math.floor(diffDays / 30)}mo ago)`;
  return `${prefix} (${Math.floor(diffDays / 365)}y ago)`;
}

function formatPlatform(platform: string): string {
  const map: Record<string, string> = {
    greenhouse: "Greenhouse",
    lever: "Lever",
    ashby: "Ashby",
    smartrecruiters: "SmartRecruiters",
    workable: "Workable",
    rippling: "Rippling",
    ycombinator: "YC",
    themuse: "The Muse",
    weworkremotely: "WWR",
  };
  return map[platform] || platform;
}

export function JobBoardTable({ jobs }: { jobs: JobRow[] }) {
  if (jobs.length === 0) {
    return (
      <div
        style={{
          background: "var(--bg-neutral-primary-soft)",
          border: "1px solid var(--border-default)",
          borderRadius: 8,
          boxShadow: "var(--shadow-xs)",
          padding: "64px 24px",
          textAlign: "center",
        }}
      >
        <p style={{ fontSize: 16, color: "var(--text-heading)", fontWeight: 600, marginBottom: 8 }}>
          No jobs match your filters
        </p>
        <p style={{ fontSize: 14, color: "var(--text-body-subtle)" }}>
          Try broadening your search or changing the date range.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        background: "var(--bg-neutral-primary-soft)",
        border: "1px solid var(--border-default)",
        borderRadius: 8,
        boxShadow: "var(--shadow-xs)",
        overflowX: "auto",
      }}
    >
      <table style={{ width: "100%", textAlign: "left", fontSize: 14, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--bg-neutral-secondary-soft)" }}>
            <th style={thStyle}>Apply</th>
            <th style={thStyle}>Title</th>
            <th style={thStyle}>Company</th>
            <th style={thStyle}>Location</th>
            <th style={thStyle}>Posted</th>
            <th style={thStyle}>Source</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job, i) => (
            <tr
              key={job.id}
              style={{
                borderBottom: i < jobs.length - 1 ? "1px solid var(--border-default)" : "none",
                transition: "background 150ms",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-neutral-secondary-soft)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              <td style={tdStyle}>
                <a
                  href={job.apply_url || job.source_url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "8px 12px",
                    fontSize: 14,
                    fontWeight: 500,
                    borderRadius: 8,
                    background: "var(--bg-brand)",
                    color: "var(--text-white)",
                    border: "1px solid transparent",
                    boxShadow: "var(--shadow-xs), inset var(--color-1-400) 0 6px 0px -5px, var(--color-1-700) 0 4px 10px -5px",
                    textDecoration: "none",
                    whiteSpace: "nowrap",
                    transition: "background 200ms",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "var(--bg-brand-strong)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "var(--bg-brand)";
                  }}
                >
                  Apply
                  <ExternalLink size={14} />
                </a>
              </td>
              <td style={tdStyle}>
                <span style={{ color: "var(--text-heading)", fontWeight: 500 }}>
                  {job.title}
                </span>
              </td>
              <td style={tdStyle}>
                <span style={{ color: "var(--text-body)" }}>{job.company_name}</span>
              </td>
              <td style={tdStyle}>
                <span style={{ color: "var(--text-body)" }}>
                  {job.location || "—"}
                </span>
                {job.is_remote && (
                  <span
                    style={{
                      display: "inline-block",
                      marginLeft: job.location ? 6 : 0,
                      fontSize: 12,
                      fontWeight: 500,
                      padding: "2px 6px",
                      borderRadius: 8,
                      background: "var(--bg-success-soft)",
                      border: "1px solid var(--border-success-subtle)",
                      color: "var(--text-fg-success-strong)",
                    }}
                  >
                    Remote
                  </span>
                )}
              </td>
              <td style={tdStyle}>
                <span style={{ color: "var(--text-body-subtle)", whiteSpace: "nowrap" }}>
                  {formatRelativeDate(job.posted_at, job.first_seen_at)}
                </span>
              </td>
              <td style={tdStyle}>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    padding: "2px 6px",
                    borderRadius: 8,
                    background: "var(--bg-neutral-secondary-medium)",
                    border: "1px solid var(--border-default)",
                    color: "var(--text-heading)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {formatPlatform(job.ats_platform)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: "12px 24px",
  fontSize: 14,
  fontWeight: 500,
  color: "var(--text-body)",
  borderBottom: "1px solid var(--border-default)",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "16px 24px",
};
