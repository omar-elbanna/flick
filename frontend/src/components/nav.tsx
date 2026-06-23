"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { logout } from "@/lib/auth";

export function Nav() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuth();
  const [search, setSearch] = useState("");

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = search.trim();
    if (q.length > 0) router.push(`/search?q=${encodeURIComponent(q)}`);
  };

  return (
    <nav className="border-b border-border sticky top-0 z-50 bg-background/95 backdrop-blur">
      <div className="container flex items-center gap-4 py-3">
        <Link
          href="/"
          aria-label="Home"
          className="flex items-center gap-2 font-bold text-xl text-primary shrink-0"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M3 9.5 12 3l9 6.5V20a2 2 0 0 1-2 2h-4v-7h-6v7H5a2 2 0 0 1-2-2Z" />
          </svg>
          Flick
        </Link>

        {isAuthenticated && (
          <form
            onSubmit={submitSearch}
            className="relative flex-1 max-w-md hidden sm:block"
          >
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search movies…"
              className="pl-9"
            />
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
          </form>
        )}

        <div className="flex items-center gap-3 text-sm ml-auto">
          {isAuthenticated ? (
            <>
              <Link href="/groups" className="hover:text-primary hidden md:inline">
                Groups
              </Link>
              <Link href="/profile" className="hover:text-primary hidden md:inline">
                Profile
              </Link>
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  await logout();
                  router.push("/auth/login");
                }}
              >
                Sign out{user?.display_name ? ` (${user.display_name})` : ""}
              </Button>
            </>
          ) : (
            <>
              <Link href="/auth/login" className="hover:text-primary">
                Log in
              </Link>
              <Link href="/auth/register">
                <Button size="sm">Sign up</Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
