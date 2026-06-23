/**
 * TypeScript interfaces mirroring the backend Pydantic schemas.
 * Update both sides together when changing a contract.
 */

export type UUID = string;
export type ISODate = string;

export interface UserResponse {
  id: UUID;
  email: string;
  display_name: string;
  avatar_url: string | null;
  created_at: ISODate;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface MovieSummary {
  id: number;
  tmdb_id?: number;
  title: string;
  overview: string | null;
  release_date: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  original_language: string | null;
  vote_average: number | null;
  vote_count: number | null;
}

export interface MovieSearchResponse {
  page: number;
  results: MovieSummary[];
  total_pages: number;
  total_results: number;
}

export interface MovieDetail {
  id: UUID;
  tmdb_id: number;
  title: string;
  overview: string | null;
  release_date: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  genres: Array<{ id: number; name: string }>;
  runtime_minutes: number | null;
  tmdb_rating: string | null;
  tmdb_vote_count: number | null;
  original_language: string | null;
  cached_at: ISODate;
}

export interface RatingResponse {
  id: UUID;
  movie_id: UUID;
  tmdb_id: number;
  movie_title: string;
  poster_path: string | null;
  score: number;
  review: string | null;
  created_at: ISODate;
  updated_at: ISODate;
}

export interface PaginatedRatings {
  items: RatingResponse[];
  page: number;
  page_size: number;
  total: number;
}

export interface WatchlistItemResponse {
  id: UUID;
  movie_id: UUID;
  tmdb_id: number;
  movie_title: string;
  poster_path: string | null;
  added_at: ISODate;
  watched: boolean;
  watched_at: ISODate | null;
}

export interface PaginatedWatchlist {
  items: WatchlistItemResponse[];
  page: number;
  page_size: number;
  total: number;
}

export interface RecommendedMovie {
  tmdb_id: number;
  title: string;
  overview: string | null;
  poster_path: string | null;
  release_date: string | null;
  reasoning: string;
}

export interface RecommendationsResponse {
  recommendations: RecommendedMovie[];
  cached: boolean;
}

export type GroupMemberRole = "owner" | "member";
export type GroupSessionStatus = "pending" | "active" | "completed" | "expired";
export type VoteChoice = "yes" | "no" | "maybe";

export interface GroupMemberResponse {
  user_id: UUID;
  display_name: string;
  avatar_url: string | null;
  role: GroupMemberRole;
  joined_at: ISODate;
}

export interface GroupSummary {
  id: UUID;
  name: string;
  invite_code: string;
  created_at: ISODate;
  member_count: number;
  role: GroupMemberRole;
}

export interface GroupDetail {
  id: UUID;
  name: string;
  invite_code: string;
  created_by: UUID;
  created_at: ISODate;
  is_active: boolean;
  members: GroupMemberResponse[];
}

export interface SessionCandidate {
  tmdb_id: number;
  movie_id: UUID;
  title: string;
  poster_path: string | null;
  overview: string | null;
  reasoning: string;
}

export interface GroupSessionResponse {
  id: UUID;
  group_id: UUID;
  status: GroupSessionStatus;
  started_by: UUID;
  started_at: ISODate;
  completed_at: ISODate | null;
  candidates: SessionCandidate[];
  winner_movie_id: UUID | null;
  winner_tmdb_id: number | null;
}

export type WSTallyEntry = { yes: number; no: number; maybe: number; score: number };
export type WSTally = Record<string, WSTallyEntry>;

export type WSEvent =
  | {
      type: "session_snapshot";
      session_id: UUID;
      candidates: SessionCandidate[];
      tally: WSTally;
    }
  | {
      type: "session_started";
      session_id: UUID;
      candidates: SessionCandidate[];
      started_at: ISODate;
    }
  | { type: "member_joined"; user_id: UUID; display_name: string }
  | {
      type: "vote_cast";
      user_id: UUID;
      movie_id: UUID;
      vote: VoteChoice;
      tally: WSTally;
    }
  | {
      type: "session_completed";
      session_id: UUID;
      winner_movie_id: UUID;
      winner_tmdb_id: number;
      winner_title: string;
    }
  | { type: "session_expired"; session_id: UUID }
  | { type: "pong" };
