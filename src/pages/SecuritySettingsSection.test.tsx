import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SecuritySettingsSection } from "./SecuritySettingsSection";

function mockFetchByUrl(byUrl: Record<string, () => Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const key = Object.keys(byUrl).find((k) => url.endsWith(k));
      if (!key) throw new Error(`Unexpected fetch: ${url}`);
      return Promise.resolve(byUrl[key]());
    }),
  );
}

function renderSection() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SecuritySettingsSection />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("SecuritySettingsSection", () => {
  it("lists enrolled methods and blocks removing the last remaining one", async () => {
    mockFetchByUrl({
      "/auth/2fa/methods": () =>
        new Response(
          JSON.stringify({
            totp_enabled: true,
            email_otp_enabled: false,
            webauthn_enabled: false,
            recovery_codes_remaining: 10,
          }),
          { status: 200 },
        ),
    });
    renderSection();
    await waitFor(() => screen.getByText(/Authenticator app/));
    const removeBtn = screen.getByRole("button", { name: "Remove Authenticator app" });
    expect(removeBtn).toBeDisabled();
  });

  it("removes a method when more than one is enrolled", async () => {
    const user = userEvent.setup();
    mockFetchByUrl({
      "/auth/2fa/methods": () =>
        new Response(
          JSON.stringify({
            totp_enabled: true,
            email_otp_enabled: true,
            webauthn_enabled: false,
            recovery_codes_remaining: 10,
          }),
          { status: 200 },
        ),
      "/auth/2fa/methods/email_otp": () =>
        new Response(JSON.stringify({ removed: "email_otp" }), { status: 200 }),
    });
    renderSection();
    await waitFor(() => screen.getByText(/Email code/));
    const removeBtn = screen.getByRole("button", { name: "Remove Email code" });
    expect(removeBtn).toBeEnabled();
    await user.click(removeBtn);
    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/auth/2fa/methods/email_otp"),
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
  });

  it("regenerates recovery codes and displays them once", async () => {
    const user = userEvent.setup();
    mockFetchByUrl({
      "/auth/2fa/methods": () =>
        new Response(
          JSON.stringify({
            totp_enabled: true,
            email_otp_enabled: false,
            webauthn_enabled: false,
            recovery_codes_remaining: 3,
          }),
          { status: 200 },
        ),
      "/auth/2fa/recovery-codes/regenerate": () =>
        new Response(JSON.stringify({ codes: ["AAAA-1111", "BBBB-2222"] }), { status: 200 }),
    });
    renderSection();
    await waitFor(() => screen.getByText(/3 remaining/));
    await user.click(screen.getByRole("button", { name: "Regenerate" }));
    await waitFor(() => screen.getByText("AAAA-1111"));
    expect(screen.getByText("BBBB-2222")).toBeInTheDocument();
  });
});
