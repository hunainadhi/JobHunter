"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@supabase/supabase-js";

// Blacklist writes require the service-role key: anon write policies were
// removed (migration 013) so browser-held anon keys can't modify the blacklist.
// This only runs server-side ("use server"), so the key never reaches the client.
function getAdminClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_KEY!
  );
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
