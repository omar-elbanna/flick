"use client";

import { AxiosError } from "axios";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useGroup, useStartSession } from "@/hooks/use-group";

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

export default function GroupDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { data: group, isLoading } = useGroup(params.id);
  const startSession = useStartSession();
  const [startErr, setStartErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const copyInvite = async () => {
    if (!group) return;
    try {
      await navigator.clipboard.writeText(group.invite_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable
    }
  };

  if (isLoading) return <p className="text-muted-foreground">Loading group…</p>;
  if (!group) return <p className="text-muted-foreground">Group not found.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <Link
            href="/groups"
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            ← All groups
          </Link>
          <h1 className="text-3xl font-bold mt-1">{group.name}</h1>
          <p className="text-sm text-muted-foreground">
            {group.members.length} member{group.members.length === 1 ? "" : "s"}
          </p>
        </div>
        <Button
          size="lg"
          disabled={startSession.isPending}
          onClick={() => {
            setStartErr(null);
            startSession.mutate(group.id, {
              onSuccess: (s) => router.push(`/session/${s.id}?group=${group.id}`),
              onError: (err) => setStartErr(extractError(err)),
            });
          }}
        >
          {startSession.isPending ? "Picking movies…" : "Start a session"}
        </Button>
      </div>

      {startErr && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {startErr}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Invite friends</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-sm text-muted-foreground">
            Share this 8-character code so friends can join:
          </p>
          <div className="flex items-center gap-3">
            <code className="text-2xl font-mono tracking-widest bg-muted px-4 py-2 rounded-md">
              {group.invite_code}
            </code>
            <Button variant="outline" onClick={copyInvite}>
              {copied ? "Copied!" : "Copy"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Members</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y divide-border">
            {group.members.map((m) => (
              <li
                key={m.user_id}
                className="flex items-center gap-3 py-2 first:pt-0 last:pb-0"
              >
                <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center text-sm font-bold text-primary">
                  {m.display_name[0]?.toUpperCase() ?? "?"}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium">{m.display_name}</div>
                  <div className="text-xs text-muted-foreground capitalize">
                    {m.role}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
