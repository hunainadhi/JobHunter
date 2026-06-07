"use server";

import { revalidatePath } from "next/cache";
import { supabase } from "./supabase";

export async function blacklistCompany(companyName: string, atsToken: string) {
  await supabase.from("blacklisted_companies").upsert(
    { company_name: companyName, ats_token: atsToken },
    { onConflict: "company_name" }
  );
  revalidatePath("/");
}

export async function unblacklistCompany(id: string) {
  await supabase.from("blacklisted_companies").delete().eq("id", id);
  revalidatePath("/blacklist");
  revalidatePath("/");
}
