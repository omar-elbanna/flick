"use client";

import Image from "next/image";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { SessionCandidate, VoteChoice, WSTallyEntry } from "@/types";

const TMDB_IMG = "https://image.tmdb.org/t/p/w342";

interface VoteCardProps {
  candidate: SessionCandidate;
  tally: WSTallyEntry | undefined;
  myVote: VoteChoice | undefined;
  onVote: (vote: VoteChoice) => void;
  disabled?: boolean;
}

export function VoteCard({
  candidate,
  tally,
  myVote,
  onVote,
  disabled,
}: VoteCardProps) {
  return (
    <Card>
      <div className="aspect-[2/3] relative bg-muted">
        {candidate.poster_path ? (
          <Image
            src={`${TMDB_IMG}${candidate.poster_path}`}
            alt={candidate.title}
            fill
            sizes="200px"
            className="object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            No poster
          </div>
        )}
      </div>
      <CardContent className="space-y-3">
        <div>
          <div className="font-semibold">{candidate.title}</div>
          <p className="text-xs text-muted-foreground line-clamp-3 mt-1">
            {candidate.reasoning}
          </p>
        </div>
        <div className="flex gap-2">
          {(["yes", "maybe", "no"] as const).map((v) => (
            <Button
              key={v}
              size="sm"
              variant={myVote === v ? "default" : "outline"}
              onClick={() => onVote(v)}
              disabled={disabled}
              className="flex-1"
            >
              {v}
              {tally && (
                <span className="ml-1 text-xs opacity-70">{tally[v] ?? 0}</span>
              )}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
