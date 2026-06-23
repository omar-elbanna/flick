"use client";

import { useQuery } from "@tanstack/react-query";

import { api, apiPaths } from "@/lib/api";
import type { PaginatedRatings } from "@/types";

export function OnboardingHint() {
  const { data, isLoading } = useQuery({
    queryKey: ["my-ratings-count"],
    queryFn: async () => {
      const resp = await api.get<PaginatedRatings>(apiPaths.myRatings, {
        params: { page_size: 1 },
      });
      return resp.data;
    },
  });

  if (isLoading || !data) return null;
  const total = data.total;
  if (total >= 5) return null;

  const remaining = Math.max(0, 5 - total);
  return (
    <div className="rounded-lg border border-primary/40 bg-primary/5 p-4 space-y-2">
      <div className="flex items-center gap-2 text-sm font-semibold text-primary">
        <span>🎬</span>
        <span>Welcome to Flick</span>
      </div>
      <p className="text-sm">
        {total === 0
          ? "Rate a few movies you've seen — Flick learns your taste from there."
          : `Just ${remaining} more rating${remaining === 1 ? "" : "s"} until group sessions unlock.`}
      </p>
      <ul className="text-xs text-muted-foreground space-y-0.5 list-disc list-inside">
        <li>Click any poster below to open it and rate 1–5 stars.</li>
        <li>Try the search bar above for specific titles.</li>
        <li>Personal picks &amp; group voting unlock at 5 ratings.</li>
      </ul>
    </div>
  );
}
