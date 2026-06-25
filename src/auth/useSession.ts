import { useQuery } from "@tanstack/react-query";
import { fetchMe } from "./api";

export function useSession() {
  return useQuery({ queryKey: ["session"], queryFn: fetchMe, staleTime: 60_000 });
}
