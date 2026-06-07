"use client";

import { unblacklistCompany } from "@/lib/actions";
import { useTransition } from "react";

export function UnblockButton({ id }: { id: string }) {
  const [isPending, startTransition] = useTransition();

  return (
    <button
      onClick={() => {
        startTransition(() => unblacklistCompany(id));
      }}
      disabled={isPending}
      className="text-xs px-3 py-1 rounded bg-[#27272a] text-[#a1a1aa] hover:bg-[#3f3f46] hover:text-[#fafafa] transition-colors disabled:opacity-50"
    >
      {isPending ? "..." : "Unblock"}
    </button>
  );
}
