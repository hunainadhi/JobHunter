"use client";

import { useState, useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { BlockButton } from "./block-button";

type Job = {
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

type SortKey = "score" | "posted";

function ScoreBadge({ score }: { score: number }) {
  let color = "text-[#71717a]";
  if (score >= 90) color = "text-emerald-400";
  else if (score >= 80) color = "text-blue-400";
  else if (score >= 70) color = "text-[#a1a1aa]";

  return <span className={`font-mono font-bold ${color}`}>{score}</span>;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-CA", { month: "short", day: "numeric" });
}

export function JobTable({ jobs }: { jobs: Job[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const sortedJobs = useMemo(() => {
    const sorted = [...jobs];
    sorted.sort((a, b) => {
      if (sortKey === "score") {
        return (b.scores?.[0]?.score ?? 0) - (a.scores?.[0]?.score ?? 0);
      } else {
        const dateA = a.posted_at || a.first_seen_at || "";
        const dateB = b.posted_at || b.first_seen_at || "";
        return dateB.localeCompare(dateA);
      }
    });
    return sorted;
  }, [jobs, sortKey]);

  const totalPages = Math.ceil(sortedJobs.length / pageSize);
  const paginatedJobs = sortedJobs.slice((page - 1) * pageSize, page * pageSize);

  if (jobs.length === 0) {
    return (
      <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-8 text-center">
        <p className="text-[#71717a]">No matched jobs yet. Run the pipeline to see results.</p>
      </div>
    );
  }

  function SortButton({ label, value }: { label: string; value: SortKey }) {
    const active = sortKey === value;
    return (
      <button
        onClick={() => { setSortKey(value); setPage(1); }}
        className={`px-3 py-1 text-xs rounded border transition-colors ${
          active
            ? "border-teal-600 bg-teal-600/20 text-teal-400"
            : "border-[#27272a] bg-[#18181b] text-[#71717a] hover:text-[#a1a1aa]"
        }`}
      >
        {label}
      </button>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-[#71717a]">Sort by:</span>
        <SortButton label="Match score" value="score" />
        <SortButton label="Date Posted" value="posted" />
      </div>

      <div className="rounded-lg border border-[#27272a] overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-[#27272a] bg-[#18181b] hover:bg-[#18181b]">
              <TableHead className="text-[#a1a1aa] min-w-[200px]">Title</TableHead>
              <TableHead className="text-[#a1a1aa]">Company</TableHead>
              <TableHead className="text-[#a1a1aa] text-center w-24">Match</TableHead>
              <TableHead className="text-[#a1a1aa] w-16">Posted</TableHead>
              <TableHead className="text-[#a1a1aa]">Location</TableHead>
              <TableHead className="text-[#a1a1aa] text-right w-20">Apply</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedJobs.map((job) => {
              const s = job.scores?.[0];
              const rationale = s?.rationale;

              return (
                <TableRow
                  key={job.id}
                  className="border-[#27272a] bg-[#09090b] hover:bg-[#18181b]"
                >
                  <TableCell>
                    <div className="font-medium text-[#fafafa]">{job.title}</div>
                    {rationale && (
                      <div className="text-xs text-[#71717a] mt-1 max-w-md truncate">
                        {rationale}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2 group">
                      <span className="text-[#fafafa]">{job.company_name}</span>
                      <BlockButton
                        companyName={job.company_name}
                        atsToken={job.ats_token}
                      />
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    <ScoreBadge score={s?.score ?? 0} />
                    <span className="text-xs text-[#71717a]">/100</span>
                  </TableCell>
                  <TableCell className="text-[#a1a1aa] whitespace-nowrap">
                    {formatDate(job.posted_at)}
                  </TableCell>
                  <TableCell className="text-[#a1a1aa]">
                    {job.location || "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <a
                      href={job.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded bg-teal-600 text-white hover:bg-teal-500 transition-colors"
                    >
                      Apply →
                    </a>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 mt-6">
          {page > 1 && (
            <button
              onClick={() => setPage(page - 1)}
              className="px-4 py-2 text-sm rounded border border-[#27272a] bg-[#18181b] text-[#fafafa] hover:bg-[#27272a] transition-colors"
            >
              Previous
            </button>
          )}
          <span className="text-sm text-[#71717a]">
            Page {page} of {totalPages}
          </span>
          {page < totalPages && (
            <button
              onClick={() => setPage(page + 1)}
              className="px-4 py-2 text-sm rounded border border-[#27272a] bg-[#18181b] text-[#fafafa] hover:bg-[#27272a] transition-colors"
            >
              Next
            </button>
          )}
        </div>
      )}
    </div>
  );
}
