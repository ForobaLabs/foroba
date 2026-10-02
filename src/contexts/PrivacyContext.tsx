import { createContext, useContext, useState, type ReactNode } from 'react';

interface PrivacyContextValue {
  isPrivate: boolean;
  toggle: () => void;
}

const Ctx = createContext<PrivacyContextValue>({ isPrivate: false, toggle: () => {} });

const STORAGE_KEY = 'kelen-privacy';

/** Hidden-amounts preference shared by the shell toggle and every money figure. */
export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [isPrivate, setIsPrivate] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });

  const toggle = () => {
    setIsPrivate((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // storage unavailable
      }
      return next;
    });
  };

  return <Ctx.Provider value={{ isPrivate, toggle }}>{children}</Ctx.Provider>;
}

// Hook co-located with its Provider, same pattern as CurrencyContext.
// eslint-disable-next-line react-refresh/only-export-components
export const usePrivacy = () => useContext(Ctx);
