"use client";

import { AxiosError } from "axios";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, apiPaths } from "@/lib/api";
import type { RecommendationsResponse } from "@/types";

const TMDB_IMG = "https://image.tmdb.org/t/p/w342";

function extractApiError(err: unknown): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data as
      | { detail?: string | { detail?: string; code?: string } }
      | undefined;
    if (data?.detail) {
      if (typeof data.detail === "string") return data.detail;
      if (typeof data.detail === "object" && data.detail.detail) return data.detail.detail;
    }
  }
  return "Something went wrong — try again.";
}

const SUGGESTIONS = [
  "cozy rainy night",
  "high-energy action",
  "thought-provoking drama",
  "laugh-out-loud comedy",
  "feel-good romance",
  "Studio Ghibli",
];

export function MoodSearch() {
  const [mood, setMood] = useState("");
  const [results, setResults] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (text: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.post<RecommendationsResponse>(apiPaths.recoMood, {
        mood: text,
      });
      setResults(resp.data);
    } catch (err: unknown) {
      setError(extractApiError(err));
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (mood.trim()) void submit(mood.trim());
        }}
      >
        <Input
          value={mood}
          onChange={(e) => setMood(e.target.value)}
          placeholder="A mood, genre, studio, or director…"
          maxLength={200}
        />
        <Button type="submit" disabled={loading || mood.trim().length < 2}>
          {loading ? "Thinking…" : "Recommend"}
        </Button>
      </form>

      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => {
              setMood(s);
              void submit(s);
            }}
            className="rounded-full border border-border px-3 py-1 text-xs hover:bg-muted transition-colors"
          >
            {s}
          </button>
        ))}
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

      {!loading && results && results.recommendations.length > 0 && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
          {results.recommendations.map((r) => (
            <Card key={r.tmdb_id} className="overflow-hidden">
              <Link
                href={`/movies/${r.tmdb_id}`}
                className="block aspect-[2/3] relative bg-muted hover:opacity-90 transition-opacity"
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
                  className="block font-medium line-clamp-2 hover:text-primary"
                >
                  {r.title}
                  {r.release_date && (
                    <span className="ml-1 text-xs text-muted-foreground font-normal">
                      ({r.release_date.slice(0, 4)})
                    </span>
                  )}
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
