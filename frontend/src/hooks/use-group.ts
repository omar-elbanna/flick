import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiPaths } from "@/lib/api";
import type {
  GroupDetail,
  GroupSessionResponse,
  GroupSummary,
} from "@/types";

export function useGroups() {
  return useQuery({
    queryKey: ["groups"],
    queryFn: async () => {
      const resp = await api.get<GroupSummary[]>(apiPaths.groups);
      return resp.data;
    },
  });
}

export function useGroup(groupId: string | undefined) {
  return useQuery({
    queryKey: ["group", groupId],
    enabled: !!groupId,
    queryFn: async () => {
      const resp = await api.get<GroupDetail>(apiPaths.group(groupId!));
      return resp.data;
    },
  });
}

export function useCreateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) => {
      const resp = await api.post<GroupSummary>(apiPaths.groups, { name });
      return resp.data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["groups"] });
    },
  });
}

export function useJoinGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (inviteCode: string) => {
      const resp = await api.post<GroupDetail>(apiPaths.joinGroup, {
        invite_code: inviteCode,
      });
      return resp.data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["groups"] });
    },
  });
}

export function useStartSession() {
  return useMutation({
    mutationFn: async (groupId: string) => {
      const resp = await api.post<GroupSessionResponse>(
        apiPaths.groupSessions(groupId)
      );
      return resp.data;
    },
  });
}

export function useSession(groupId: string | undefined, sessionId: string | undefined) {
  return useQuery({
    queryKey: ["session", groupId, sessionId],
    enabled: !!groupId && !!sessionId,
    queryFn: async () => {
      const resp = await api.get<GroupSessionResponse>(
        apiPaths.groupSession(groupId!, sessionId!)
      );
      return resp.data;
    },
  });
}
