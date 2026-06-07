"use client";

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

function ScoreBadge({ score }: { score: number }) {
  let color = "text-[#71717a]";
  if (score >= 90) color = "text-emerald-400";
  else if (score >= 80) color = "text-blue-400";
  else if (score >= 70) color = "text-[#a1a1aa]";

  return <span className={`font-mono font-bold ${color}`}>{score}</span>;
}

export function JobTable({ jobs }: { jobs: Job[] }) {
  if (jobs.length === 0) {
    return (
      <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-8 text-center">
        <p className="text-[#71717a]">No matched jobs yet. Run the pipeline to see results.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[#27272a] overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="border-[#27272a] bg-[#18181b] hover:bg-[#18181b]">
            <TableHead className="text-[#a1a1aa]">Title</TableHead>
            <TableHead className="text-[#a1a1aa]">Company</TableHead>
            <TableHead className="text-[#a1a1aa] text-center">MiniMax</TableHead>
            <TableHead className="text-[#a1a1aa] text-center">Computed</TableHead>
            <TableHead className="text-[#a1a1aa]">Location</TableHead>
            <TableHead className="text-[#a1a1aa] text-right">Apply</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((job) => {
            const s = job.scores?.[0];
            const score = s?.score ?? 0;
            const computedScore =
              (s?.role_fit_score || 0) +
              (s?.seniority_fit_score || 0) +
              (s?.stack_overlap_score || 0) +
              (s?.keyword_score || 0);
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
                  <ScoreBadge score={score} />
                </TableCell>
                <TableCell className="text-center">
                  <ScoreBadge score={computedScore} />
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
  );
}
