import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  acceptHouseholdInvite,
  fetchHousehold,
  joinHousehold,
  leaveHousehold,
  setSharePreference,
} from "./api";

const HOUSEHOLD_QUERY_KEY = ["household"];

export function useHousehold() {
  const queryClient = useQueryClient();

  const household = useQuery({
    queryKey: HOUSEHOLD_QUERY_KEY,
    queryFn: fetchHousehold,
    staleTime: 30_000,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: HOUSEHOLD_QUERY_KEY });

  const join = useMutation({
    mutationFn: (email: string) => joinHousehold(email),
    onSuccess: invalidate,
  });

  const acceptInvite = useMutation({
    mutationFn: (token: string) => acceptHouseholdInvite(token),
    onSuccess: invalidate,
  });

  const leave = useMutation({
    mutationFn: leaveHousehold,
    onSuccess: invalidate,
  });

  const toggleShare = useMutation({
    mutationFn: ({ resourceType, shared }: { resourceType: string; shared: boolean }) =>
      setSharePreference(resourceType, shared),
    onSuccess: invalidate,
  });

  return { household, join, acceptInvite, leave, toggleShare };
}
