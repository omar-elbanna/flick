"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { VoteCard } from "@/components/vote-card";
import { useWebSocket } from "@/hooks/use-websocket";
import { api, apiPaths } from "@/lib/api";
import { useSessionStore } from "@/store/session-store";
import type { GroupSessionResponse, VoteChoice, WSEvent } from "@/types";

interface GroupSessionProps {
  groupId: string;
  session: GroupSessionResponse;
}

export function GroupSession({ groupId, session }: GroupSessionProps) {
  const {
    candidates,
    setCandidates,
    tally,
    setTally,
    myVotes,
    setVote,
    presentMembers,
    setPresent,
    winner,
    setWinner,
    status,
    setStatus,
    reset,
  } = useSessionStore();

  useEffect(() => {
    reset();
    setCandidates(session.candidates);
    setStatus(session.status === "active" ? "active" : session.status === "completed" ? "completed" : "idle");
  }, [session.id, session.candidates, session.status, reset, setCandidates, setStatus]);

  const handleMessage = (event: WSEvent) => {
    switch (event.type) {
      case "session_snapshot":
        setCandidates(event.candidates);
        setTally(event.tally);
        break;
      case "session_started":
        setCandidates(event.candidates);
        setStatus("active");
        break;
      case "member_joined":
        setPresent(event.user_id, event.display_name);
        break;
      case "vote_cast":
        setTally(event.tally);
        break;
      case "session_completed":
        setWinner(event.winner_movie_id, event.winner_title, event.winner_tmdb_id);
        break;
      case "session_expired":
        setStatus("expired");
        break;
      default:
        break;
    }
  };

  useWebSocket({
    url: `/api/v1/ws/sessions/${session.id}`,
    onMessage: handleMessage,
    enabled: session.status === "active" || session.status === "pending",
  });

  const castVote = async (movieId: string, vote: VoteChoice) => {
    setVote(movieId, vote);
    await api.post(apiPaths.castVote(groupId, session.id), {
      movie_id: movieId,
      vote,
    });
  };

  const [rerolling, setRerolling] = useState(false);
  const reroll = async () => {
    setRerolling(true);
    try {
      const resp = await api.post<GroupSessionResponse>(
        apiPaths.reroll(groupId, session.id)
      );
      setCandidates(resp.data.candidates);
      setTally({});
    } finally {
      setRerolling(false);
    }
  };

  const present = useMemo(() => Object.values(presentMembers), [presentMembers]);

  if (winner) {
    return (
      <div className="space-y-4 text-center py-12 animate-in fade-in zoom-in">
        <h2 className="text-3xl font-bold">🎬 Tonight you&apos;re watching</h2>
        <div className="text-5xl font-bold text-primary">{winner.title}</div>
        <a
          className="inline-block text-primary underline"
          href={`/movies/${winner.tmdbId}`}
        >
          See details →
        </a>
      </div>
    );
  }

  if (status === "expired") {
    return <div className="text-center py-8">Session expired without a winner.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between text-sm text-muted-foreground flex-wrap gap-2">
        <div>
          {candidates.length} candidates · {status}
          {present.length > 0 && (
            <> · with {present.join(", ")}</>
          )}
        </div>
        {status === "active" && (
          <Button
            variant="outline"
            size="sm"
            onClick={reroll}
            disabled={rerolling}
          >
            {rerolling ? "Re-rolling…" : "↻ Re-roll picks"}
          </Button>
        )}
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
        {candidates.map((c) => (
          <VoteCard
            key={c.movie_id}
            candidate={c}
            tally={tally[c.movie_id]}
            myVote={myVotes[c.movie_id]}
            onVote={(v) => void castVote(c.movie_id, v)}
            disabled={status !== "active"}
          />
        ))}
      </div>
    </div>
  );
}
