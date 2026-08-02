import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { LoginPage } from "./LoginPage";

vi.mock("@simplewebauthn/browser", () => ({
  startAuthentication: vi.fn(async () => ({
    id: "cred-1",
    rawId: "cred-1",
    response: {},
    type: "public-key",
  })),
}));

const fakeUser = {
  id: 1,
  email: "demo@foroba.app",
  name: "Demo",
  tier: "free",
  audience: "base",
  audience_locked: false,
  totp_enabled: true,
  email_otp_enabled: false,
  webauthn_enabled: false,
  is_admin: false,
  display_currency: "EUR",
  show_debts: false,
  birth_year: null,
  country: null,
  onboarding_completed_at: "2026-01-01",
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockFetchByUrl(handlers: Record<string, () => unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL) => {
      const path = String(url);
      const match = Object.keys(handlers).find((suffix) => path.endsWith(suffix));
      if (!match) throw new Error(`unhandled fetch: ${path}`);
      // Invoke eagerly, not lazily inside json() — success paths in api.ts (e.g.
      // sendLoginEmailOtp) never call .json() on an ok response, so a spy wired only
      // through json() would never be recorded even though the request succeeded.
      const body = handlers[match]();
      return { ok: true, json: async () => body } as Response;
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("logs straight in when the account has no MFA enrolled (kill-switch edge case)", async () => {
  mockFetchByUrl({ "/auth/login": () => fakeUser });
  renderPage();

  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "demo@foroba.app" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Demo!2026" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() => expect(screen.getByText("Home")).toBeInTheDocument());
});

test("shows a code challenge after password login returns mfa_required, then verifies via TOTP", async () => {
  mockFetchByUrl({
    "/auth/login/2fa": () => fakeUser,
    "/auth/login": () => ({ mfa_required: true, email: "demo@foroba.app", methods: ["totp"] }),
  });
  renderPage();

  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "demo@foroba.app" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Demo!2026" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() => expect(screen.getByText("Verify it's you")).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("Authenticator app code"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify" }));

  await waitFor(() => expect(screen.getByText("Home")).toBeInTheDocument());
});

test("sends and verifies an email OTP code as the second factor", async () => {
  const sendSpy = vi.fn(() => ({ sent: true }));
  mockFetchByUrl({
    "/auth/login/email-otp/send": sendSpy,
    "/auth/login/2fa": () => fakeUser,
    "/auth/login": () => ({
      mfa_required: true,
      email: "demo@foroba.app",
      methods: ["totp", "email_otp"],
    }),
  });
  renderPage();

  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "demo@foroba.app" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Demo!2026" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() => expect(screen.getByText("Verify it's you")).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("Verification method"), { target: { value: "email_otp" } });

  await waitFor(() => expect(sendSpy).toHaveBeenCalled());
  await waitFor(() =>
    expect(screen.getByText(/Code sent to demo@foroba.app/)).toBeInTheDocument(),
  );

  fireEvent.change(screen.getByLabelText("Email code"), { target: { value: "654321" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify" }));

  await waitFor(() => expect(screen.getByText("Home")).toBeInTheDocument());
});

test("supports signing in with a recovery code instead of a normal code", async () => {
  mockFetchByUrl({
    "/auth/login/recovery-code": () => fakeUser,
    "/auth/login": () => ({ mfa_required: true, email: "demo@foroba.app", methods: ["totp"] }),
  });
  renderPage();

  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "demo@foroba.app" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Demo!2026" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() => expect(screen.getByText("Verify it's you")).toBeInTheDocument());
  fireEvent.click(screen.getByText("Use a recovery code instead"));
  fireEvent.change(screen.getByLabelText("Recovery code"), { target: { value: "ABCD1234EF" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify" }));

  await waitFor(() => expect(screen.getByText("Home")).toBeInTheDocument());
});

test("signs in with a passkey directly, without ever submitting a password", async () => {
  mockFetchByUrl({
    "/auth/login/webauthn/options-by-email": () => ({ challenge: "abc", rpId: "foroba.app" }),
    "/auth/login/webauthn/verify": () => fakeUser,
  });
  renderPage();

  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "demo@foroba.app" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in with passkey" }));

  await waitFor(() => expect(screen.getByText("Home")).toBeInTheDocument());
});
