"use client";

import { useTransition } from "react";
import { queueJobForApplication } from "@/lib/actions";

export function QueueApplicationButton({ jobId }: { jobId: string }) {
  const [isPending, startTransition] = useTransition();

  return (
    <button
      onClick={() => startTransition(() => queueJobForApplication(jobId))}
      disabled={isPending}
      className="mr-2 inline-flex items-center px-3 py-1.5 text-sm rounded border border-teal-700 text-teal-300 hover:bg-teal-900/30 transition-colors disabled:opacity-50"
    >
      {isPending ? "Queueing..." : "Queue"}
    </button>
  );
}
