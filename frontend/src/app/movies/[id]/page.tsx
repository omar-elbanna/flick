"use client";

import { useQuery } from "@tanstack/react-query";
import { AxiosError } from "axios";
import Image from "next/image";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { MovieCard } from "@/components/movie-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { WhereToWatch } from "@/components/where-to-watch";
import { useMovieDetail } from "@/hooks/use-movies";
import { api, apiPaths } from "@/lib/api";
import type { MovieSearchResponse, PaginatedRatings, PaginatedWatchlist } from "@/types";

const TMDB_IMG = "https://image.tmdb.org/t/p/original";

function extractError(err: unknown): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data as
      | { detail?: string | { detail?: string; code?: string } }
      | undefined;
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.detail === "object" && data?.detail?.detail) return data.detail.detail;
  }
  return "Something went wrong.";
}

export default function MovieDetailPage() {
  const params = useParams<{ id: string }>();
  const tmdbId = Number(params.id);
  const { data, isLoading, error } = useMovieDetail(tmdbId);

  const similar = useQuery({
    queryKey: ["similar", tmdbId],
    enabled: Number.isFinite(tmdbId),
    queryFn: async () => {
      const resp = await api.get<MovieSearchResponse>(apiPaths.recoSimilar(tmdbId));
      return resp.data;
    },
  });

  const myRating = useQuery({
    queryKey: ["my-ratings-lookup"],
    queryFn: async () => {
      const resp = await api.get<PaginatedRatings>(apiPaths.myRatings, {
        params: { page_size: 100 },
      });
      return resp.data;
    },
  });

  const myWatchlist = useQuery({
    queryKey: ["my-watchlist-lookup"],
    queryFn: async () => {
      const resp = await api.get<PaginatedWatchlist>(apiPaths.myWatchlist, {
        params: { page_size: 100 },
      });
      return resp.data;
    },
  });

  const existingRating = myRating.data?.items.find((r) => r.tmdb_id === tmdbId);
  const onWatchlist = myWatchlist.data?.items.some((w) => w.tmdb_id === tmdbId);

  const [score, setScore] = useState<number>(0);
  const [review, setReview] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (existingRating && score === 0) {
      setScore(existingRating.score);
      setReview(existingRating.review ?? "");
    }
  }, [existingRating, score]);

  const rate = async () => {
    if (score === 0) {
      setMsg({ kind: "err", text: "Pick a star rating first." });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await api.post(apiPaths.rate, {
        tmdb_id: tmdbId,
        score,
        review: review || null,
      });
      setMsg({ kind: "ok", text: existingRating ? "Rating updated ✓" : "Rating saved ✓" });
      void myRating.refetch();
    } catch (err) {
      setMsg({ kind: "err", text: extractError(err) });
    } finally {
      setBusy(false);
    }
  };

  const addToWatchlist = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api.post(apiPaths.watchlist, { tmdb_id: tmdbId });
      setMsg({ kind: "ok", text: "Added to watchlist ✓" });
      void myWatchlist.refetch();
    } catch (err) {
      setMsg({ kind: "err", text: extractError(err) });
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) {
    return (
      <div className="grid gap-6 md:grid-cols-[300px_1fr]">
        <div className="aspect-[2/3] bg-muted rounded-md animate-pulse" />
        <div className="space-y-3">
          <div className="h-8 w-2/3 bg-muted rounded animate-pulse" />
          <div className="h-4 w-1/3 bg-muted rounded animate-pulse" />
          <div className="h-24 w-full bg-muted rounded animate-pulse" />
        </div>
      </div>
    );
  }
  if (error || !data) return <div className="text-destructive">Could not load movie.</div>;

  return (
    <div className="space-y-10">
      <div className="grid gap-6 md:grid-cols-[300px_1fr]">
        <div className="aspect-[2/3] relative rounded-md overflow-hidden bg-muted">
          {data.poster_path ? (
            <Image
              src={`${TMDB_IMG}${data.poster_path}`}
              alt={data.title}
              fill
              sizes="300px"
              className="object-cover"
              priority
            />
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              No poster
            </div>
          )}
        </div>
        <div className="space-y-4">
          <div>
            <h1 className="text-3xl font-bold">{data.title}</h1>
            <div className="text-sm text-muted-foreground mt-1">
              {data.release_date?.slice(0, 4) ?? "—"} ·{" "}
              {data.runtime_minutes ? `${data.runtime_minutes} min` : "—"} ·{" "}
              ⭐ {data.tmdb_rating ?? "—"}
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {data.genres.map((g) => (
                <span
                  key={g.id}
                  className="rounded-full bg-muted px-2 py-0.5 text-xs"
                >
                  {g.name}
                </span>
              ))}
            </div>
          </div>
          <p className="text-sm leading-relaxed">{data.overview}</p>

          <WhereToWatch tmdbId={tmdbId} />

          <Card>
            <CardContent className="space-y-3 py-4">
              <div>
                <div className="text-sm font-medium mb-2">
                  {existingRating ? "Your rating" : "Rate this movie"}
                </div>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      onClick={() => setScore(n)}
                      className={`h-10 w-10 rounded-md text-2xl transition-colors ${
                        score >= n
                          ? "bg-accent text-background"
                          : "bg-muted text-muted-foreground hover:text-foreground"
                      }`}
                      aria-label={`Rate ${n}`}
                    >
                      ★
                    </button>
                  ))}
                </div>
              </div>
              <textarea
                className="w-full rounded-md border border-border bg-card p-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="Quick review (optional, max 500 chars)"
                maxLength={500}
                value={review}
                onChange={(e) => setReview(e.target.value)}
                rows={3}
              />
              <div className="flex flex-wrap gap-2">
                <Button onClick={rate} disabled={busy}>
                  {existingRating ? "Update rating" : "Save rating"}
                </Button>
                <Button
                  variant="outline"
                  onClick={addToWatchlist}
                  disabled={busy || onWatchlist}
                >
                  {onWatchlist ? "On your watchlist ✓" : "Add to watchlist"}
                </Button>
              </div>
              {msg && (
                <p
                  className={`text-sm ${
                    msg.kind === "ok" ? "text-primary" : "text-destructive"
                  }`}
                >
                  {msg.text}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {similar.data && similar.data.results.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold mb-3">More like this</h2>
          <p className="text-xs text-muted-foreground mb-3">
            Ranked by similarity. Curated from TMDB&apos;s viewer-behavior data.
          </p>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {similar.data.results.map((m) => (
              <MovieCard
                key={m.id}
                tmdbId={m.id}
                title={m.title}
                posterPath={m.poster_path}
                releaseDate={m.release_date}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
