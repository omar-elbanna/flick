/**
 * Axios client with refresh-token interceptor.
 * - Adds Authorization: Bearer from Zustand store on every request.
 * - On 401, attempts one refresh via /api/v1/auth/refresh and retries.
 * - Refresh failure clears auth state.
 */
import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

import { useAuthStore } from "@/store/auth-store";
import type { TokenResponse } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 60_000,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token && config.headers) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

let refreshInFlight: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const resp = await axios.post<TokenResponse>(
        `${API_BASE_URL}/api/v1/auth/refresh`,
        null,
        { withCredentials: true }
      );
      useAuthStore.getState().setAccessToken(resp.data.access_token);
      return resp.data.access_token;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

api.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    const original = error.config as
      | (AxiosRequestConfig & { _retried?: boolean })
      | undefined;
    if (
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      !original.url?.includes("/auth/refresh") &&
      !original.url?.includes("/auth/login")
    ) {
      try {
        const newToken = await refreshAccessToken();
        original._retried = true;
        original.headers = {
          ...(original.headers ?? {}),
          Authorization: `Bearer ${newToken}`,
        };
        return api.request(original);
      } catch {
        useAuthStore.getState().clearAuth();
      }
    }
    return Promise.reject(error);
  }
);

export const apiPaths = {
  register: "/api/v1/auth/register",
  login: "/api/v1/auth/login",
  refresh: "/api/v1/auth/refresh",
  logout: "/api/v1/auth/logout",
  me: "/api/v1/auth/me",
  googleStart: "/api/v1/auth/google",
  moviesSearch: "/api/v1/movies/search",
  moviesTrending: "/api/v1/movies/trending",
  moviesGenres: "/api/v1/movies/genres",
  movieDetail: (id: number | string) => `/api/v1/movies/${id}`,
  rate: "/api/v1/ratings",
  rating: (id: string) => `/api/v1/ratings/${id}`,
  myRatings: "/api/v1/users/me/ratings",
  watchlist: "/api/v1/watchlist",
  watchlistItem: (id: string) => `/api/v1/watchlist/${id}`,
  myWatchlist: "/api/v1/users/me/watchlist",
  recoPersonal: "/api/v1/recommendations/personal",
  recoMood: "/api/v1/recommendations/mood",
  recoSimilar: (id: number | string) => `/api/v1/recommendations/similar/${id}`,
  groups: "/api/v1/groups",
  group: (id: string) => `/api/v1/groups/${id}`,
  joinGroup: "/api/v1/groups/join",
  leaveGroup: (id: string) => `/api/v1/groups/${id}/members/me`,
  groupMembers: (id: string) => `/api/v1/groups/${id}/members`,
  groupSessions: (id: string) => `/api/v1/groups/${id}/sessions`,
  groupSession: (groupId: string, sessionId: string) =>
    `/api/v1/groups/${groupId}/sessions/${sessionId}`,
  castVote: (groupId: string, sessionId: string) =>
    `/api/v1/groups/${groupId}/sessions/${sessionId}/votes`,
  reroll: (groupId: string, sessionId: string) =>
    `/api/v1/groups/${groupId}/sessions/${sessionId}/reroll`,
};
