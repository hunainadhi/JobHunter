import Link from "next/link";
import { createClient } from "@supabase/supabase-js";
import { getSupabaseWriteConfig } from "@/lib/supabase-config";

export const dynamic = "force-dynamic";

type Application = {
  id: string;
  company_name: string;
  job_title: string;
  match_score: number | null;
  status: string;
  policy_reasons: string[];
  submitted_at: string | null;
  submission_confirmation: string | null;
  next_action: string | null;
  next_action_at: string | null;
  created_at: string;
};

function adminClient() {
  const { url, key } = getSupabaseWriteConfig();
  return createClient(url, key);
}

function formatDate(value: string | null) {
  if (!value) return "Not submitted";
  return new Intl.DateTimeFormat("en-CA", { dateStyle: "medium" }).format(new Date(value));
}

function statusLabel(status: string) {
  return status.replaceAll("_", " ");
}

export default async function ApplicationsPage() {
  const { data, error } = await adminClient()
    .from("application_ledger")
    .select("id, company_name, job_title, match_score, status, policy_reasons, submitted_at, submission_confirmation, next_action, next_action_at, created_at")
    .order("created_at", { ascending: false });

  if (error) throw new Error(`Could not load applications: ${error.message}`);
  const applications = (data ?? []) as Application[];

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link href="/" className="text-sm text-[#71717a] hover:text-[#fafafa]">← JobHunter</Link>
            <h1 className="mt-2 text-2xl font-bold tracking-widest uppercase text-[#fafafa]">Application Ledger</h1>
          </div>
          <div className="text-sm text-[#71717a]">{applications.length} tracked</div>
        </div>

        <p className="mb-5 text-sm text-[#a1a1aa]">
          Queue a job from the main dashboard to record its policy decision. Submitted evidence and next actions stay here.
        </p>

        {applications.length === 0 ? (
          <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-8 text-center text-[#71717a]">
            No applications are tracked yet. Queue a scored job from JobHunter.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-[#27272a]">
            <table className="w-full text-sm">
              <thead className="bg-[#18181b] text-left text-[#a1a1aa]">
                <tr>
                  <th className="p-3">Role</th>
                  <th className="p-3">Match</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Evidence</th>
                  <th className="p-3">Next action</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((application) => (
                  <tr key={application.id} className="border-t border-[#27272a] text-[#fafafa]">
                    <td className="p-3">
                      <div className="font-medium">{application.job_title}</div>
                      <div className="mt-1 text-xs text-[#71717a]">{application.company_name}</div>
                    </td>
                    <td className="p-3 font-mono">{application.match_score ?? "?"}/100</td>
                    <td className="p-3">
                      <div className="capitalize text-teal-300">{statusLabel(application.status)}</div>
                      {application.policy_reasons.length > 0 && (
                        <div className="mt-1 max-w-xs text-xs text-[#a1a1aa]">{application.policy_reasons.join(" ")}</div>
                      )}
                    </td>
                    <td className="p-3 text-[#a1a1aa]">
                      <div>{formatDate(application.submitted_at)}</div>
                      {application.submission_confirmation && <div className="mt-1 text-xs">{application.submission_confirmation}</div>}
                    </td>
                    <td className="p-3 text-[#a1a1aa]">{application.next_action ?? "None"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
