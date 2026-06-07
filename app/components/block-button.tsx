"use client";

import { blacklistCompany } from "@/lib/actions";
import { useTransition } from "react";

export function BlockButton({
  companyName,
  atsToken,
}: {
  companyName: string;
  atsToken: string;
}) {
  const [isPending, startTransition] = useTransition();

  return (
    <button
      onClick={() => {
        startTransition(() => blacklistCompany(companyName, atsToken));
      }}
      disabled={isPending}
      className="opacity-0 group-hover:opacity-100 text-xs px-2 py-0.5 rounded bg-red-900/50 text-red-400 hover:bg-red-900 transition-all disabled:opacity-50"
    >
      {isPending ? "..." : "Block"}
    </button>
  );
}
