"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { fetchMeIfPossible } from "@/lib/auth";
import { useAuthStore } from "@/store/auth-store";

export default function OAuthCallbackPage() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const token = params.get("access_token");
    if (token) {
      useAuthStore.getState().setAccessToken(token);
      void fetchMeIfPossible().then(() => router.replace("/"));
    } else {
      router.replace("/auth/login");
    }
  }, [params, router]);

  return <div className="text-center py-12">Signing you in…</div>;
}
