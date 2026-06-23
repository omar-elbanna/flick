import { useQuery } from "@tanstack/react-query";

import { api, apiPaths } from "@/lib/api";
import type { MovieDetail, MovieSearchResponse } from "@/types";

export function useTrending() {
  return useQuery({
    queryKey: ["movies", "trending"],
    queryFn: async () => {
      const resp = await api.get<MovieSearchResponse>(apiPaths.moviesTrending);
      return resp.data;
    },
    staleTime: 60 * 60 * 1000,
  });
}

export function useMovieSearch(query: string) {
  return useQuery({
    queryKey: ["movies", "search", query],
    enabled: query.trim().length > 0,
    queryFn: async () => {
      const resp = await api.get<MovieSearchResponse>(apiPaths.moviesSearch, {
        params: { q: query },
      });
      return resp.data;
    },
  });
}

export function useMovieDetail(tmdbId: number | undefined) {
  return useQuery({
    queryKey: ["movies", "detail", tmdbId],
    enabled: typeof tmdbId === "number",
    queryFn: async () => {
      const resp = await api.get<MovieDetail>(apiPaths.movieDetail(tmdbId!));
      return resp.data;
    },
  });
}
