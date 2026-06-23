"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { GroupSession } from "@/components/group-session";
import { useSession } from "@/hooks/use-group";

function SessionInner() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const groupId = search.get("group") ?? undefined;
  const { data, isLoading, error } = useSession(groupId, params.id);

  if (!groupId) {
    return (
      <div className="space-y-3">
        <p className="text-muted-foreground">
          Missing group context — open this session from your groups page.
        </p>
        <Link href="/groups" className="text-primary underline text-sm">
          Back to groups
        </Link>
      </div>
    );
  }
  if (isLoading || !data) {
    return <p className="text-muted-foreground">Loading session…</p>;
  }
  if (error) {
    return (
      <div className="space-y-3">
        <p className="text-destructive">Could not load session.</p>
        <Link
          href={`/groups/${groupId}`}
          className="text-primary underline text-sm"
        >
          Back to group
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Link
        href={`/groups/${groupId}`}
        className="text-xs text-muted-foreground hover:text-foreground"
      >
        ← Back to group
      </Link>
      <GroupSession groupId={groupId} session={data} />
    </div>
  );
}

export default function SessionPage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>
      <SessionInner />
    </Suspense>
  );
}
