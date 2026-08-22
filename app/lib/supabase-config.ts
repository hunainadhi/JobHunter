type SupabaseConfig = {
  url: string;
  key: string;
};

function firstConfigured(...names: string[]): string | undefined {
  return names.map((name) => process.env[name]).find((value) => Boolean(value));
}

export function getSupabaseReadConfig(): SupabaseConfig {
  const url = firstConfigured("NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_URL");
  const key = firstConfigured("NEXT_PUBLIC_SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY");

  if (!url || !key) {
    throw new Error(
      "Missing Supabase read configuration. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY, or SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY."
    );
  }

  return { url, key };
}

export function getSupabaseWriteConfig(): SupabaseConfig {
  const { url } = getSupabaseReadConfig();
  const key = firstConfigured("SUPABASE_SERVICE_KEY", "SUPABASE_SECRET_KEY");

  if (!key) {
    throw new Error(
      "Missing Supabase write configuration. Set SUPABASE_SERVICE_KEY or SUPABASE_SECRET_KEY."
    );
  }

  return { url, key };
}
