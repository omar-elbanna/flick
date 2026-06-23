import { api, apiPaths } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import type { TokenResponse, UserResponse } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function login(email: string, password: string): Promise<UserResponse> {
  const tokenResp = await api.post<TokenResponse>(apiPaths.login, {
    email,
    password,
  });
  useAuthStore.getState().setAccessToken(tokenResp.data.access_token);
  const me = await api.get<UserResponse>(apiPaths.me);
  useAuthStore.getState().setAuth(me.data, tokenResp.data.access_token);
  return me.data;
}

export async function register(
  email: string,
  password: string,
  displayName: string
): Promise<UserResponse> {
  await api.post<UserResponse>(apiPaths.register, {
    email,
    password,
    display_name: displayName,
  });
  return login(email, password);
}

export async function logout(): Promise<void> {
  try {
    await api.post(apiPaths.logout);
  } finally {
    useAuthStore.getState().clearAuth();
  }
}

export function googleOAuthRedirect(): void {
  window.location.href = `${API_BASE_URL}${apiPaths.googleStart}`;
}

export async function fetchMeIfPossible(): Promise<UserResponse | null> {
  try {
    const me = await api.get<UserResponse>(apiPaths.me);
    useAuthStore.getState().setAuth(me.data, useAuthStore.getState().accessToken);
    return me.data;
  } catch {
    return null;
  }
}
