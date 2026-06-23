"use client";

import { AxiosError } from "axios";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useCreateGroup, useGroups, useJoinGroup } from "@/hooks/use-group";

function extractError(err: unknown): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data as
      | { detail?: string | { detail?: string; code?: string } }
      | undefined;
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.detail === "object" && data?.detail?.detail) return data.detail.detail;
  }
  return "Something went wrong.";
}

export default function GroupsPage() {
  const groups = useGroups();
  const createGroup = useCreateGroup();
  const joinGroup = useJoinGroup();
  const [newName, setNewName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [createErr, setCreateErr] = useState<string | null>(null);
  const [joinErr, setJoinErr] = useState<string | null>(null);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold">Your groups</h1>
        <p className="text-muted-foreground mt-1">
          Start a session — Flick picks 5 movies, your friends vote, the winner shows up.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Create a group</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                const name = newName.trim();
                if (!name) return;
                setCreateErr(null);
                createGroup.mutate(name, {
                  onSuccess: () => setNewName(""),
                  onError: (err) => setCreateErr(extractError(err)),
                });
              }}
            >
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Group name"
                maxLength={100}
              />
              <Button type="submit" disabled={createGroup.isPending}>
                {createGroup.isPending ? "Creating…" : "Create"}
              </Button>
            </form>
            {createErr && <p className="text-sm text-destructive">{createErr}</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Join with invite code</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                const code = inviteCode.trim().toUpperCase();
                if (!code) return;
                setJoinErr(null);
                joinGroup.mutate(code, {
                  onSuccess: () => setInviteCode(""),
                  onError: (err) => setJoinErr(extractError(err)),
                });
              }}
            >
              <Input
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                placeholder="8-char code"
                maxLength={8}
                className="font-mono tracking-widest uppercase"
              />
              <Button type="submit" disabled={joinGroup.isPending}>
                {joinGroup.isPending ? "Joining…" : "Join"}
              </Button>
            </form>
            {joinErr && <p className="text-sm text-destructive">{joinErr}</p>}
          </CardContent>
        </Card>
      </div>

      {groups.isLoading ? (
        <p className="text-muted-foreground py-8 text-center">Loading…</p>
      ) : !groups.data || groups.data.length === 0 ? (
        <div className="text-center py-12 space-y-2 text-muted-foreground">
          <p>No groups yet — create one above or join with a friend&apos;s code.</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {groups.data.map((g) => (
            <Card key={g.id}>
              <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
                <Link
                  href={`/groups/${g.id}`}
                  className="flex-1 min-w-[200px] hover:opacity-80"
                >
                  <div className="font-semibold">{g.name}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {g.member_count} member{g.member_count === 1 ? "" : "s"} · code{" "}
                    <code className="bg-muted px-1.5 py-0.5 rounded font-mono">
                      {g.invite_code}
                    </code>{" "}
                    · you&apos;re the {g.role}
                  </div>
                </Link>
                <Link href={`/groups/${g.id}`}>
                  <Button variant="outline" size="sm">
                    Open
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
