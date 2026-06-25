import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useSession } from "./useSession";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ id: 1, email: "a@b.com", name: "A", tier: "free",
      audience: "base", audience_locked: false, totp_enabled: false }),
  }) as unknown as typeof fetch;
});

describe("useSession", () => {
  it("returns the current user when /auth/me succeeds", async () => {
    const { result } = renderHook(() => useSession(), { wrapper });
    await waitFor(() => expect(result.current.data?.email).toBe("a@b.com"));
  });
});
