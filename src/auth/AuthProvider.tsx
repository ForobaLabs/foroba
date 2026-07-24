import { createContext, useContext, type ReactNode } from "react";
import { useSession } from "./useSession";
import type { SessionUser } from "./api";

const Ctx = createContext<{ user: SessionUser | null; loading: boolean }>({
  user: null,
  loading: true,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data, isLoading } = useSession();
  return (
    <Ctx.Provider value={{ user: data ?? null, loading: isLoading }}>
      {children}
    </Ctx.Provider>
  );
}

// Hook co-located with its Provider is a standard pattern; splitting into a separate
// file for Fast Refresh purity isn't worth the indirection for a single-line accessor.
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(Ctx);
