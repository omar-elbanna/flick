"use client";

import { AxiosError } from "axios";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api, apiPaths } from "@/lib/api";
import type { RecommendationsResponse } from "@/types";

const TMDB_IMG = "https://image.tmdb.org/t/p/w342";

function extractError(err: unknown): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data as
      | { detail?: string | { detail?: string; code?: string } }
      | undefined;
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.detail === "object" && data?.detail?.detail) return data.detail.detail;
  }
  return "Could not load picks.";
}

export function PersonalPicks() {
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.post<RecommendationsResponse>(apiPaths.recoPersonal);
      setData(resp.data);
    } catch (err) {
      setError(extractError(err));
    } finally {
      setLoading(false);
    }
  };

  if (!data && !loading && !error) {
    return (
      <div className="rounded-lg border border-dashed border-border p-6 text-center space-y-3">
        <h3 className="text-lg font-semibold">Picks for you</h3>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          The more you rate, the better Flick gets at finding your taste. Rate
          some movies and then ask for personalized picks.
        </p>
        <Button onClick={load}>Get my picks</Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-2xl font-semibold">Picks for you</h2>
        {data?.cached && (
          <span className="text-xs text-muted-foreground">cached · refresh in 15min</span>
        )}
        <Button size="sm" variant="ghost" onClick={load} disabled={loading}>
          {loading ? "Thinking…" : "Refresh"}
        </Button>
      </div>
      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
      {loading && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="aspect-[2/3] rounded-md bg-muted animate-pulse" />
          ))}
        </div>
      )}
      {data && data.recommendations.length > 0 && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {data.recommendations.map((r) => (
            <Card key={r.tmdb_id} className="overflow-hidden">
              <Link
                href={`/movies/${r.tmdb_id}`}
                className="block aspect-[2/3] relative bg-muted hover:opacity-90"
              >
                {r.poster_path ? (
                  <Image
                    src={`${TMDB_IMG}${r.poster_path}`}
                    alt={r.title}
                    fill
                    sizes="(max-width: 768px) 50vw, 200px"
                    className="object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground p-2 text-center">
                    {r.title}
                  </div>
                )}
              </Link>
              <CardContent className="p-3 space-y-1">
                <Link
                  href={`/movies/${r.tmdb_id}`}
                  className="block text-sm font-medium line-clamp-2 hover:text-primary"
                >
                  {r.title}
                </Link>
                <p className="text-xs text-muted-foreground line-clamp-3 italic">
                  {r.reasoning}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
