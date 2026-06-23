"use client";

import Image from "next/image";
import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";

interface MovieCardProps {
  tmdbId: number;
  title: string;
  posterPath: string | null;
  releaseDate?: string | null;
}

const TMDB_IMG = "https://image.tmdb.org/t/p/w342";

export function MovieCard({ tmdbId, title, posterPath, releaseDate }: MovieCardProps) {
  return (
    <Link href={`/movies/${tmdbId}`} className="block">
      <Card className="overflow-hidden transition-transform hover:scale-[1.02]">
        <div className="aspect-[2/3] relative bg-muted">
          {posterPath ? (
            <Image
              src={`${TMDB_IMG}${posterPath}`}
              alt={title}
              fill
              sizes="(max-width: 768px) 50vw, 200px"
              className="object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-muted-foreground">
              No poster
            </div>
          )}
        </div>
        <CardContent className="p-3">
          <div className="font-medium line-clamp-2">{title}</div>
          {releaseDate && (
            <div className="text-xs text-muted-foreground mt-1">
              {releaseDate.slice(0, 4)}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
