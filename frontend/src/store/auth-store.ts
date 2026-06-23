/**
 * Auth state lives in memory only — access tokens never touch localStorage.
 * The refresh token cookie (httpOnly) drives session continuity on reload.
 */
import { create } from "zustand";

import type { UserResponse } from "@/types";

interface AuthState {
  user: UserResponse | null;
  accessToken: string | null;
  setAuth: (user: UserResponse | null, accessToken: string | null) => void;
  setAccessToken: (token: string | null) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  setAuth: (user, accessToken) => set({ user, accessToken }),
  setAccessToken: (accessToken) => set({ accessToken }),
  clearAuth: () => set({ user: null, accessToken: null }),
}));
