import { useEffect } from "react";

import { fetchMeIfPossible } from "@/lib/auth";
import { useAuthStore } from "@/store/auth-store";

export function useAuth() {
  const { user, accessToken, clearAuth } = useAuthStore();

  useEffect(() => {
    if (!user) {
      void fetchMeIfPossible();
    }
  }, [user]);

  return { user, accessToken, isAuthenticated: !!user, clearAuth };
}
