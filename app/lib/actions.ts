"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@supabase/supabase-js";
import { getSupabaseWriteConfig } from "./supabase-config";
import { decideApplication, ledgerRecord } from "./application-policy.mjs";

// Writes use a server-only Supabase secret key. The key is never sent to the browser.
function getAdminClient() {
  const { url, key } = getSupabaseWriteConfig();
  return createClient(url, key);
}

export async function blacklistCompany(companyName: string, atsToken: string) {
  const { error } = await getAdminClient()
    .from("blacklisted_companies")
    .upsert(
      { company_name: companyName, ats_token: atsToken },
      { onConflict: "company_name" }
    );
  if (error) throw new Error(`Failed to blacklist company: ${error.message}`);
  revalidatePath("/");
}

export async function unblacklistCompany(id: string) {
  const { error } = await getAdminClient()
    .from("blacklisted_companies")
    .delete()
    .eq("id", id);
  if (error) throw new Error(`Failed to unblacklist company: ${error.message}`);
  revalidatePath("/blacklist");
  revalidatePath("/");
}

export async function queueJobForApplication(jobId: string) {
  const supabase = getAdminClient();
  const { data: job, error: jobError } = await supabase
    .from("jobs")
    .select("id, title, company_name, apply_url, source_url")
    .eq("id", jobId)
    .single();
  if (jobError || !job) throw new Error("Job could not be loaded for application.");

  const [{ data: scoreRow }, { count: companyApplicationCount }, { count: applicationsToday }] = await Promise.all([
    supabase
      .from("scores")
      .select("score")
      .eq("job_id", jobId)
      .order("scored_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("application_ledger")
      .select("id", { count: "exact", head: true })
      .eq("company_name", job.company_name),
    supabase
      .from("application_ledger")
      .select("id", { count: "exact", head: true })
      .gte("submitted_at", new Date(new Date().setHours(0, 0, 0, 0)).toISOString()),
  ]);

  const policyDecision = decideApplication({
    score: scoreRow?.score ?? 0,
    title: job.title,
    companyApplicationCount: companyApplicationCount ?? 0,
    applicationsToday: applicationsToday ?? 0,
  });
  const record = ledgerRecord({ ...job, score: scoreRow?.score ?? 0 }, policyDecision);

  const { data: application, error: ledgerError } = await supabase
    .from("application_ledger")
    .upsert(record, { onConflict: "job_id" })
    .select("id")
    .single();
  if (ledgerError || !application) {
    throw new Error(`Could not add job to application ledger: ${ledgerError?.message ?? "unknown error"}`);
  }

  const { error: eventError } = await supabase.from("application_events").insert({
    application_id: application.id,
    event_type: "policy_evaluated",
    details: { decision: policyDecision.decision, reasons: policyDecision.reasons },
  });
  if (eventError) throw new Error(`Could not write application event: ${eventError.message}`);

  revalidatePath("/");
  revalidatePath("/applications");
}
