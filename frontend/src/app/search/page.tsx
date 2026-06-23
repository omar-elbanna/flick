"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { MovieCard } from "@/components/movie-card";
import { useMovieSearch } from "@/hooks/use-movies";

function SearchResults() {
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const { data, isLoading, error } = useMovieSearch(q);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">
          {q ? <>Results for &ldquo;{q}&rdquo;</> : "Search"}
        </h1>
        {data && (
          <p className="text-sm text-muted-foreground">
            {data.total_results.toLocaleString()} results
          </p>
        )}
      </header>

      {!q && (
        <p className="text-muted-foreground">
          Type a movie title in the search bar above to find it.
        </p>
      )}
      {isLoading && <p className="text-muted-foreground">Searching…</p>}
      {error && <p className="text-destructive">Search failed. Try again.</p>}
      {data && data.results.length === 0 && (
        <p className="text-muted-foreground">No results found.</p>
      )}

      {data && data.results.length > 0 && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {data.results.map((m) => (
            <MovieCard
              key={m.id}
              tmdbId={m.id}
              title={m.title}
              posterPath={m.poster_path}
              releaseDate={m.release_date}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>
      <SearchResults />
    </Suspense>
  );
}
