import { create } from "zustand";

import type { SessionCandidate, VoteChoice, WSTally } from "@/types";

interface SessionState {
  candidates: SessionCandidate[];
  tally: WSTally;
  myVotes: Record<string, VoteChoice>;
  presentMembers: Record<string, string>;
  winner: { movieId: string; title: string; tmdbId: number } | null;
  status: "idle" | "active" | "completed" | "expired";
  setCandidates: (candidates: SessionCandidate[]) => void;
  setTally: (tally: WSTally) => void;
  setVote: (movieId: string, vote: VoteChoice) => void;
  setPresent: (userId: string, name: string) => void;
  setWinner: (movieId: string, title: string, tmdbId: number) => void;
  setStatus: (status: SessionState["status"]) => void;
  reset: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  candidates: [],
  tally: {},
  myVotes: {},
  presentMembers: {},
  winner: null,
  status: "idle",
  setCandidates: (candidates) => set({ candidates }),
  setTally: (tally) => set({ tally }),
  setVote: (movieId, vote) =>
    set((s) => ({ myVotes: { ...s.myVotes, [movieId]: vote } })),
  setPresent: (userId, name) =>
    set((s) => ({ presentMembers: { ...s.presentMembers, [userId]: name } })),
  setWinner: (movieId, title, tmdbId) =>
    set({ winner: { movieId, title, tmdbId }, status: "completed" }),
  setStatus: (status) => set({ status }),
  reset: () =>
    set({
      candidates: [],
      tally: {},
      myVotes: {},
      presentMembers: {},
      winner: null,
      status: "idle",
    }),
}));
