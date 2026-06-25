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

export const useAuth = () => useContext(Ctx);
