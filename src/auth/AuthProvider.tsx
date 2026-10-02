import { createContext, useContext, type ReactNode } from "react";
import { useSession } from "./useSession";
import type { SessionUser } from "./api";

const Ctx = createContext<{
  user: SessionUser | null;
  loading: boolean;
  /** /auth/me failed for a reason other than 401 (outage, rate limit, offline): do not treat as signed out. */
  unavailable: boolean;
  retry: () => void;
}>({
  user: null,
  loading: true,
  unavailable: false,
  retry: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data, isLoading, isError, refetch } = useSession();
  return (
    <Ctx.Provider value={{ user: data ?? null, loading: isLoading, unavailable: isError && !data, retry: () => void refetch() }}>
      {children}
    </Ctx.Provider>
  );
}

// Hook co-located with its Provider is a standard pattern; splitting into a separate
// file for Fast Refresh purity isn't worth the indirection for a single-line accessor.
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(Ctx);
