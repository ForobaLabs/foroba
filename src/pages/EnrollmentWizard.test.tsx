import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { EnrollmentWizard } from "./EnrollmentWizard";

vi.mock("@simplewebauthn/browser", () => ({
  startRegistration: vi.fn(async () => ({
    id: "cred-1",
    rawId: "cred-1",
    response: {},
    type: "public-key",
  })),
}));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/enroll"]}>
      <Routes>
        <Route path="/enroll" element={<EnrollmentWizard />} />
        <Route path="/onboarding" element={<div>Onboarding</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockFetchByUrl(handlers: Record<string, () => unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL) => {
      const path = String(url);
      const match = Object.keys(handlers).find((suffix) => path.endsWith(suffix));
      if (!match) throw new Error(`unhandled fetch: ${path}`);
      // Invoke eagerly, not lazily inside json() — success paths in api.ts never call
      // .json() on an ok response, so a spy wired only through json() would never be
      // recorded even though the request succeeded.
      const body = handlers[match]();
      return { ok: true, json: async () => body } as Response;
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("sets up TOTP: shows the QR code, verifies the code, then shows recovery codes", async () => {
  mockFetchByUrl({
    "/auth/2fa/enroll": () => ({ secret: "JBSWY3DPEHPK3PXP", qr: "data:image/png;base64,abc" }),
    "/auth/2fa/verify": () => ({ enabled: true }),
    "/auth/2fa/recovery-codes/regenerate": () => ({
      codes: Array.from({ length: 10 }, (_, i) => `CODE${i}`),
    }),
  });
  renderPage();

  fireEvent.click(screen.getByText("Authenticator app"));
  await waitFor(() => expect(screen.getByAltText("TOTP QR code")).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText("6-digit code"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify and continue" }));

  await waitFor(() => expect(screen.getByText("Save your recovery codes")).toBeInTheDocument());
  expect(screen.getByText("CODE0")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "I've saved these codes" }));
  await waitFor(() => expect(screen.getByText("Onboarding")).toBeInTheDocument());
});

test("sets up email OTP: auto-sends the code, verifies, then shows recovery codes", async () => {
  mockFetchByUrl({
    "/auth/2fa/email-otp/send": () => ({ sent: true }),
    "/auth/2fa/email-otp/verify": () => ({}),
    "/auth/2fa/recovery-codes/regenerate": () => ({
      codes: Array.from({ length: 10 }, (_, i) => `CODE${i}`),
    }),
  });
  renderPage();

  fireEvent.click(screen.getByText("Email code"));
  await waitFor(() =>
    expect(screen.getByText("We sent a 6-digit code to your email.")).toBeInTheDocument(),
  );

  fireEvent.change(screen.getByLabelText("6-digit code"), { target: { value: "654321" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify and continue" }));

  await waitFor(() => expect(screen.getByText("Save your recovery codes")).toBeInTheDocument());
});

test("sets up a passkey end-to-end without requiring any typed code", async () => {
  mockFetchByUrl({
    "/auth/webauthn/register/options": () => ({ challenge: "abc", rp: { id: "foroba.app" } }),
    "/auth/webauthn/register/verify": () => ({}),
    "/auth/2fa/recovery-codes/regenerate": () => ({
      codes: Array.from({ length: 10 }, (_, i) => `CODE${i}`),
    }),
  });
  renderPage();

  fireEvent.click(screen.getByText("Passkey (recommended)"));

  await waitFor(() => expect(screen.getByText("Save your recovery codes")).toBeInTheDocument());
});

test("shows an error and stays on the TOTP step when the code is invalid", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL) => {
      const path = String(url);
      if (path.endsWith("/auth/2fa/enroll")) {
        return {
          ok: true,
          json: async () => ({ secret: "JBSWY3DPEHPK3PXP", qr: "data:image/png;base64,abc" }),
        } as Response;
      }
      if (path.endsWith("/auth/2fa/verify")) {
        return { ok: false, json: async () => ({ detail: "Invalid code" }) } as Response;
      }
      throw new Error(`unhandled fetch: ${path}`);
    }),
  );
  renderPage();

  fireEvent.click(screen.getByText("Authenticator app"));
  await waitFor(() => expect(screen.getByAltText("TOTP QR code")).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText("6-digit code"), { target: { value: "000000" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify and continue" }));

  await waitFor(() => expect(screen.getByText("Invalid code.")).toBeInTheDocument());
  expect(screen.queryByText("Save your recovery codes")).not.toBeInTheDocument();
});
