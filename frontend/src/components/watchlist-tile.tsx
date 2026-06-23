"use client";

import { useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { api, apiPaths } from "@/lib/api";
import type { WatchlistItemResponse } from "@/types";

const TMDB_IMG = "https://image.tmdb.org/t/p/w342";

export function WatchlistTile({ item }: { item: WatchlistItemResponse }) {
  const qc = useQueryClient();
  const [watched, setWatched] = useState(item.watched);
  const [score, setScore] = useState<number>(0);
  const [showRater, setShowRater] = useState(false);
  const [busy, setBusy] = useState(false);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const toggleWatched = async (next: boolean) => {
    setBusy(true);
    setWatched(next);
    try {
      await api.patch(apiPaths.watchlistItem(item.id), { watched: next });
      if (next) setShowRater(true);
      void qc.invalidateQueries({ queryKey: ["my-watchlist"] });
    } catch {
      setWatched(!next);
    } finally {
      setBusy(false);
    }
  };

  const saveRating = async (n: number) => {
    setBusy(true);
    setScore(n);
    try {
      await api.post(apiPaths.rate, { tmdb_id: item.tmdb_id, score: n });
      setSavedMsg(`Rated ${n}/5 ✓`);
      void qc.invalidateQueries({ queryKey: ["my-ratings"] });
      void qc.invalidateQueries({ queryKey: ["my-ratings-count"] });
      setTimeout(() => setShowRater(false), 1200);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirm(`Remove "${item.movie_title}" from your watchlist?`)) return;
    setBusy(true);
    try {
      await api.delete(apiPaths.watchlistItem(item.id));
      void qc.invalidateQueries({ queryKey: ["my-watchlist"] });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="overflow-hidden group relative">
      <button
        onClick={remove}
        disabled={busy}
        title="Remove from watchlist"
        className="absolute top-2 right-2 z-10 h-7 w-7 rounded-full bg-black/70 text-white text-sm opacity-0 group-hover:opacity-100 transition-opacity hover:bg-destructive"
      >
        ✕
      </button>
      <Link
        href={`/movies/${item.tmdb_id}`}
        className="block aspect-[2/3] relative bg-muted hover:opacity-90"
      >
        {item.poster_path ? (
          <Image
            src={`${TMDB_IMG}${item.poster_path}`}
            alt={item.movie_title}
            fill
            sizes="(max-width: 768px) 50vw, 200px"
            className="object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground p-2 text-center">
            {item.movie_title}
          </div>
        )}
        {watched && (
          <div className="absolute top-2 left-2 bg-primary text-primary-foreground text-xs px-2 py-1 rounded-full font-medium">
            Watched ✓
          </div>
        )}
      </Link>
      <CardContent className="p-3 space-y-2">
        <Link
          href={`/movies/${item.tmdb_id}`}
          className="block text-sm font-medium line-clamp-2 hover:text-primary"
        >
          {item.movie_title}
        </Link>
        <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={watched}
            onChange={(e) => toggleWatched(e.target.checked)}
            disabled={busy}
            className="accent-primary"
          />
          Watched
        </label>
        {showRater && (
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Rate it:</p>
            <div className="flex gap-0.5">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  disabled={busy}
                  onClick={() => saveRating(n)}
                  className={`text-xl transition-colors ${
                    score >= n
                      ? "text-accent"
                      : "text-muted-foreground hover:text-accent"
                  }`}
                  aria-label={`Rate ${n}`}
                >
                  ★
                </button>
              ))}
            </div>
            {savedMsg && (
              <p className="text-xs text-primary">{savedMsg}</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
