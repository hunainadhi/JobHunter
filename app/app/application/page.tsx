import Link from "next/link";
import { createClient } from "@supabase/supabase-js";
import { getSupabaseWriteConfig } from "@/lib/supabase-config";

export const dynamic = "force-dynamic";

type PackageFields = {
  common_answers?: Record<string, string>;
  links?: Record<string, string>;
  form_checklist?: string[];
};

type ApplicationPackage = {
  id: string;
  company_name: string;
  job_title: string;
  apply_url: string;
  source_url: string | null;
  match_score: number | null;
  status: string;
  policy_reasons: string[];
  application_fields: PackageFields;
  submitted_materials: Record<string, string>;
  next_action: string | null;
  created_at: string;
};

function adminClient() {
  const { url, key } = getSupabaseWriteConfig();
  return createClient(url, key);
}

function label(key: string) {
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-CA", { dateStyle: "medium" }).format(new Date(value));
}

export default async function ApplicationPackagesPage() {
  const { data, error } = await adminClient()
    .from("application_ledger")
    .select("id, company_name, job_title, apply_url, source_url, match_score, status, policy_reasons, application_fields, submitted_materials, next_action, created_at")
    .eq("status", "ready_to_apply")
    .order("match_score", { ascending: false })
    .order("created_at", { ascending: false });

  if (error) throw new Error(`Could not load application packages: ${error.message}`);
  const packages = (data ?? []) as ApplicationPackage[];

  return (
    <main className="min-h-screen p-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <Link href="/" className="text-sm text-[#71717a] hover:text-[#fafafa]">← JobHunter</Link>
            <h1 className="mt-2 text-2xl font-bold tracking-widest uppercase text-[#fafafa]">Application Packages</h1>
            <p className="mt-2 text-sm text-[#a1a1aa]">
              Use one package per live application. Each contains the supported baseline answers and a final form checklist.
            </p>
          </div>
          <Link href="/applications" className="text-sm text-teal-300 hover:text-teal-200">View ledger</Link>
        </div>

        {packages.length === 0 ? (
          <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-8 text-center text-[#71717a]">
            No ready application packages yet. The next daily JobHunter run will add new 70+ matches here.
          </div>
        ) : (
          <div className="grid gap-5 lg:grid-cols-2">
            {packages.map((application) => {
              const fields = application.application_fields ?? {};
              return (
                <article key={application.id} className="rounded-lg border border-[#27272a] bg-[#18181b] p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-lg font-semibold text-[#fafafa]">{application.job_title}</h2>
                      <p className="mt-1 text-sm text-[#a1a1aa]">{application.company_name} · Added {formatDate(application.created_at)}</p>
                    </div>
                    <div className="rounded bg-teal-400/10 px-2 py-1 font-mono text-sm text-teal-300">
                      {application.match_score ?? "?"}/100
                    </div>
                  </div>

                  <div className="mt-5 flex flex-wrap gap-3">
                    <a href={application.apply_url} target="_blank" rel="noreferrer" className="rounded bg-teal-400 px-3 py-2 text-sm font-medium text-[#09090b] hover:bg-teal-300">
                      Open application
                    </a>
                    {application.source_url && (
                      <a href={application.source_url} target="_blank" rel="noreferrer" className="rounded border border-[#3f3f46] px-3 py-2 text-sm text-[#d4d4d8] hover:border-[#71717a]">
                        Job details
                      </a>
                    )}
                  </div>

                  <section className="mt-5">
                    <h3 className="text-sm font-medium text-[#fafafa]">Supported answers</h3>
                    <dl className="mt-2 space-y-2 text-sm">
                      {Object.entries(fields.common_answers ?? {}).map(([key, value]) => (
                        <div key={key}>
                          <dt className="text-xs uppercase tracking-wide text-[#71717a]">{label(key)}</dt>
                          <dd className="mt-0.5 text-[#d4d4d8]">{value}</dd>
                        </div>
                      ))}
                    </dl>
                  </section>

                  <section className="mt-5">
                    <h3 className="text-sm font-medium text-[#fafafa]">Links and materials</h3>
                    <ul className="mt-2 space-y-1 text-sm text-[#d4d4d8]">
                      {Object.entries(application.submitted_materials ?? {}).map(([key, value]) => <li key={key}>{label(key)}: {value}</li>)}
                      {Object.entries(fields.links ?? {}).map(([key, value]) => <li key={key}>{label(key)}: {value}</li>)}
                    </ul>
                  </section>

                  <section className="mt-5">
                    <h3 className="text-sm font-medium text-[#fafafa]">Before submitting</h3>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[#d4d4d8]">
                      {(fields.form_checklist ?? []).map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </section>

                  {application.policy_reasons.length > 0 && (
                    <p className="mt-5 border-t border-[#27272a] pt-4 text-xs text-[#71717a]">{application.policy_reasons.join(" ")}</p>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
