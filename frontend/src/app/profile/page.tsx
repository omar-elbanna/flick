"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { WatchlistTile } from "@/components/watchlist-tile";
import { useAuth } from "@/hooks/use-auth";
import { api, apiPaths } from "@/lib/api";
import type { PaginatedRatings, PaginatedWatchlist } from "@/types";

const TMDB_IMG = "https://image.tmdb.org/t/p/w342";

function Poster({
  posterPath,
  title,
  tmdbId,
}: {
  posterPath: string | null;
  title: string;
  tmdbId: number;
}) {
  return (
    <Link
      href={`/movies/${tmdbId}`}
      className="block aspect-[2/3] relative bg-muted rounded-md overflow-hidden hover:opacity-90 transition-opacity"
    >
      {posterPath ? (
        <Image
          src={`${TMDB_IMG}${posterPath}`}
          alt={title}
          fill
          sizes="(max-width: 768px) 50vw, 200px"
          className="object-cover"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground p-2 text-center">
          {title}
        </div>
      )}
    </Link>
  );
}

function StarRow({ score }: { score: number }) {
  return (
    <div className="flex gap-0.5 text-accent text-sm">
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className={n <= score ? "" : "opacity-25"}>
          ★
        </span>
      ))}
    </div>
  );
}

export default function ProfilePage() {
  const { user, isAuthenticated } = useAuth();
  const [tab, setTab] = useState<"ratings" | "watchlist">("ratings");

  const ratings = useQuery({
    queryKey: ["my-ratings"],
    enabled: isAuthenticated,
    queryFn: async () => {
      const resp = await api.get<PaginatedRatings>(apiPaths.myRatings, {
        params: { page_size: 50 },
      });
      return resp.data;
    },
  });
  const watchlist = useQuery({
    queryKey: ["my-watchlist"],
    enabled: isAuthenticated,
    queryFn: async () => {
      const resp = await api.get<PaginatedWatchlist>(apiPaths.myWatchlist, {
        params: { page_size: 50 },
      });
      return resp.data;
    },
  });

  if (!isAuthenticated) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Please sign in to see your profile.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-4">
        <div className="h-16 w-16 rounded-full bg-primary/20 flex items-center justify-center text-2xl font-bold text-primary">
          {user?.display_name?.[0]?.toUpperCase() ?? "?"}
        </div>
        <div>
          <h1 className="text-3xl font-bold">{user?.display_name}</h1>
          <p className="text-muted-foreground text-sm">{user?.email}</p>
          <div className="flex gap-4 mt-1 text-sm">
            <span>
              <b>{ratings.data?.total ?? 0}</b>{" "}
              <span className="text-muted-foreground">ratings</span>
            </span>
            <span>
              <b>{watchlist.data?.total ?? 0}</b>{" "}
              <span className="text-muted-foreground">on watchlist</span>
            </span>
          </div>
        </div>
      </header>

      <div className="flex gap-2 border-b border-border">
        {(["ratings", "watchlist"] as const).map((t) => (
          <Button
            key={t}
            variant={tab === t ? "default" : "ghost"}
            size="sm"
            onClick={() => setTab(t)}
            className="capitalize"
          >
            {t}
          </Button>
        ))}
      </div>

      {tab === "ratings" ? (
        ratings.isLoading ? (
          <p className="text-muted-foreground py-8 text-center">Loading…</p>
        ) : !ratings.data || ratings.data.items.length === 0 ? (
          <div className="text-center py-12 space-y-3">
            <p className="text-muted-foreground">
              You haven&apos;t rated anything yet.
            </p>
            <Link href="/">
              <Button>Find movies to rate</Button>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {ratings.data.items.map((r) => (
              <Card key={r.id} className="overflow-hidden">
                <Poster posterPath={r.poster_path} title={r.movie_title} tmdbId={r.tmdb_id} />
                <CardContent className="p-3 space-y-1">
                  <Link
                    href={`/movies/${r.tmdb_id}`}
                    className="text-sm font-medium line-clamp-2 hover:text-primary"
                  >
                    {r.movie_title}
                  </Link>
                  <StarRow score={r.score} />
                  {r.review && (
                    <p className="text-xs text-muted-foreground line-clamp-2 italic mt-1">
                      &ldquo;{r.review}&rdquo;
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )
      ) : watchlist.isLoading ? (
        <p className="text-muted-foreground py-8 text-center">Loading…</p>
      ) : !watchlist.data || watchlist.data.items.length === 0 ? (
        <div className="text-center py-12 space-y-3">
          <p className="text-muted-foreground">Your watchlist is empty.</p>
          <Link href="/">
            <Button>Browse movies</Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {watchlist.data.items.map((w) => (
            <WatchlistTile key={w.id} item={w} />
          ))}
        </div>
      )}
    </div>
  );
}
