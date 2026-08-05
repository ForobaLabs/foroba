import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SecuritySettingsSection } from "./SecuritySettingsSection";

vi.mock("@simplewebauthn/browser", () => ({
  startRegistration: vi.fn(async () => ({
    id: "cred-1",
    rawId: "cred-1",
    response: {},
    type: "public-key",
  })),
}));

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
      "/auth/consents": () => new Response(JSON.stringify([]), { status: 200 }),
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
      "/auth/consents": () => new Response(JSON.stringify([]), { status: 200 }),
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

  it("lets the user add a not-yet-enrolled method (email OTP)", async () => {
    const user = userEvent.setup();
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
      "/auth/2fa/email-otp/send": () => new Response(JSON.stringify({ sent: true }), { status: 200 }),
      "/auth/2fa/email-otp/verify": () => new Response(JSON.stringify({}), { status: 200 }),
      "/auth/consents": () => new Response(JSON.stringify([]), { status: 200 }),
    });
    renderSection();
    await waitFor(() => screen.getByRole("button", { name: "Add Email code" }));

    await user.click(screen.getByRole("button", { name: "Add Email code" }));
    await waitFor(() =>
      expect(screen.getByPlaceholderText("6-digit code")).toBeInTheDocument(),
    );
    await user.type(screen.getByPlaceholderText("6-digit code"), "654321");
    await user.click(screen.getByRole("button", { name: "Verify" }));

    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/auth/2fa/email-otp/verify"),
        expect.objectContaining({ method: "POST" }),
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
      "/auth/consents": () => new Response(JSON.stringify([]), { status: 200 }),
    });
    renderSection();
    await waitFor(() => screen.getByText(/3 remaining/));
    await user.click(screen.getByRole("button", { name: "Regenerate" }));
    await waitFor(() => screen.getByText("AAAA-1111"));
    expect(screen.getByText("BBBB-2222")).toBeInTheDocument();
  });

  it("surfaces the accepted legal document versions", async () => {
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
      "/auth/consents": () =>
        new Response(
          JSON.stringify([
            {
              document_type: "terms_of_service",
              document_version: "2026-07-31",
              accepted_at: "2026-08-06 12:00:00",
            },
            {
              document_type: "privacy_policy",
              document_version: "2026-07-31",
              accepted_at: "2026-08-06 12:00:00",
            },
          ]),
          { status: 200 },
        ),
    });
    renderSection();
    await waitFor(() => screen.getByText("Terms of Service"));
    expect(screen.getByText("Privacy Policy")).toBeInTheDocument();
    expect(screen.getAllByText(/Accepted v2026-07-31/)).toHaveLength(2);
  });

  describe("delete account", () => {
    function mockMethods() {
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
        "/auth/consents": () => new Response(JSON.stringify([]), { status: 200 }),
      });
    }

    it("keeps the confirm button disabled until password and DELETE phrase are both filled", async () => {
      const user = userEvent.setup();
      mockMethods();
      renderSection();
      await waitFor(() => screen.getByRole("button", { name: "Delete account" }));
      await user.click(screen.getByRole("button", { name: "Delete account" }));

      const confirmBtn = screen.getByRole("button", { name: "Delete account" });
      expect(confirmBtn).toBeDisabled();

      await user.type(screen.getByLabelText(/Confirm your password/), "mypassword");
      expect(confirmBtn).toBeDisabled();

      await user.type(screen.getByLabelText(/Type DELETE to confirm/), "DELETE");
      expect(confirmBtn).toBeEnabled();
    });

    it("redirects to /login on success", async () => {
      const user = userEvent.setup();
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
        "/auth/consents": () => new Response(JSON.stringify([]), { status: 200 }),
        "/auth/account": () => new Response(null, { status: 204 }),
      });
      Object.defineProperty(window, "location", { writable: true, value: { href: "" } });
      renderSection();
      await waitFor(() => screen.getByRole("button", { name: "Delete account" }));
      await user.click(screen.getByRole("button", { name: "Delete account" }));
      await user.type(screen.getByLabelText(/Confirm your password/), "mypassword");
      await user.type(screen.getByLabelText(/Type DELETE to confirm/), "DELETE");
      await user.click(screen.getByRole("button", { name: "Delete account" }));

      await waitFor(() => expect(window.location.href).toBe("/login"));
    });

    it("shows an inline error and keeps the dialog open on failure", async () => {
      const user = userEvent.setup();
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
        "/auth/consents": () => new Response(JSON.stringify([]), { status: 200 }),
        "/auth/account": () =>
          new Response(JSON.stringify({ detail: "Invalid password" }), { status: 401 }),
      });
      renderSection();
      await waitFor(() => screen.getByRole("button", { name: "Delete account" }));
      await user.click(screen.getByRole("button", { name: "Delete account" }));
      await user.type(screen.getByLabelText(/Confirm your password/), "wrongpassword");
      await user.type(screen.getByLabelText(/Type DELETE to confirm/), "DELETE");
      await user.click(screen.getByRole("button", { name: "Delete account" }));

      await waitFor(() => screen.getByText("Invalid password"));
      expect(screen.getByLabelText(/Confirm your password/)).toBeInTheDocument();
    });
  });
});
