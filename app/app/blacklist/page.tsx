import { supabase } from "@/lib/supabase";
import { UnblockButton } from "@/components/unblock-button";

export const dynamic = "force-dynamic";

export default async function BlacklistPage() {
  const { data: companies } = await supabase
    .from("blacklisted_companies")
    .select("id, company_name, ats_token, created_at")
    .order("created_at", { ascending: false });

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold tracking-widest uppercase text-[#fafafa]">
            Blacklist
          </h1>
          <a
            href="/"
            className="text-sm text-[#71717a] hover:text-[#fafafa] transition-colors"
          >
            ← Back
          </a>
        </div>

        {!companies || companies.length === 0 ? (
          <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-8 text-center">
            <p className="text-[#71717a]">No blacklisted companies.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {companies.map((company) => (
              <div
                key={company.id}
                className="flex items-center justify-between px-4 py-3 rounded-lg border border-[#27272a] bg-[#18181b]"
              >
                <div>
                  <span className="text-[#fafafa]">{company.company_name}</span>
                  {company.ats_token && (
                    <span className="ml-2 text-xs text-[#71717a]">
                      ({company.ats_token})
                    </span>
                  )}
                </div>
                <UnblockButton id={company.id} />
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
