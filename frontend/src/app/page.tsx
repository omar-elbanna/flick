"use client";

import Link from "next/link";

import { MoodSearch } from "@/components/mood-search";
import { MovieCard } from "@/components/movie-card";
import { OnboardingHint } from "@/components/onboarding-hint";
import { PersonalPicks } from "@/components/personal-picks";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { useTrending } from "@/hooks/use-movies";

export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const { data: trending, isLoading, error } = useTrending();

  if (!isAuthenticated) {
    return (
      <div className="space-y-8 py-16 text-center">
        <h1 className="text-5xl md:text-6xl font-bold leading-tight">
          Find what to watch <span className="text-primary">together</span>.
        </h1>
        <p className="text-lg text-muted-foreground max-w-xl mx-auto">
          Flick learns your taste, blends it with your friends&apos;, and lands on a
          movie everyone&apos;s actually excited about — in under five minutes.
        </p>
        <div className="flex gap-3 justify-center">
          <Link href="/auth/register">
            <Button size="lg">Get started</Button>
          </Link>
          <Link href="/auth/login">
            <Button variant="outline" size="lg">
              Log in
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-12">
      <OnboardingHint />

      <section>
        <h2 className="text-2xl font-semibold mb-1">
          What are you in the mood for?
        </h2>
        <p className="text-sm text-muted-foreground mb-4">
          A mood, genre, studio, or director — the AI picks 20 movies tailored to it.
        </p>
        <MoodSearch />
      </section>

      <section>
        <PersonalPicks />
      </section>

      <section>
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-2xl font-semibold">Trending this week</h2>
          <Link
            href="/groups"
            className="text-sm text-muted-foreground hover:text-primary"
          >
            Watching with friends? →
          </Link>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
            {Array.from({ length: 10 }).map((_, i) => (
              <div
                key={i}
                className="aspect-[2/3] rounded-md bg-muted animate-pulse"
              />
            ))}
          </div>
        ) : error ? (
          <p className="text-destructive">Could not load trending movies.</p>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {trending?.results.slice(0, 20).map((m) => (
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
      </section>
    </div>
  );
}
