import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import i18n from "../i18n";
import { RegisterPage } from "./RegisterPage";

beforeAll(() => i18n.changeLanguage("en"));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/register"]}>
        <Routes>
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/enroll" element={<div>Enroll</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("redirects to the mandatory enrollment wizard after successful registration", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => ({ id: 1, email: "a@b.com" }) } as Response)),
  );
  renderPage();

  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Ada" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ada@example.com" } });
  fireEvent.change(screen.getByLabelText("Confirm email"), { target: { value: "ada@example.com" } });
  fireEvent.change(screen.getByLabelText("Password (min 8 chars)"), {
    target: { value: "Sup3rSecret!" },
  });
  fireEvent.change(screen.getByLabelText("Confirm password"), {
    target: { value: "Sup3rSecret!" },
  });
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));

  await waitFor(() => expect(screen.getByText("Enroll")).toBeInTheDocument());
});

test("blocks submission until the Terms of Service checkbox is checked", () => {
  renderPage();

  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Ada" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ada@example.com" } });
  fireEvent.change(screen.getByLabelText("Confirm email"), { target: { value: "ada@example.com" } });
  fireEvent.change(screen.getByLabelText("Password (min 8 chars)"), {
    target: { value: "Sup3rSecret!" },
  });
  fireEvent.change(screen.getByLabelText("Confirm password"), {
    target: { value: "Sup3rSecret!" },
  });

  expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
});

test("shows the sign-up intent from the site and stays honest about paid plans", () => {
  sessionStorage.clear();
  window.history.pushState({}, "", "/register?app=naforo&plan=premium");
  renderPage();
  expect(screen.getByRole("note")).toHaveTextContent(/signing up for Naforo/i);
  expect(screen.getByRole("note")).toHaveTextContent(/not available yet/i);
  expect(JSON.parse(sessionStorage.getItem("foroba.signupIntent") ?? "{}")).toEqual({ app: "naforo", plan: "premium" });
  window.history.pushState({}, "", "/");
});

test("accepts the expert plan intent and stays honest about paid plans", () => {
  sessionStorage.clear();
  window.history.pushState({}, "", "/register?app=yiriba&plan=expert");
  renderPage();
  expect(screen.getByRole("note")).toHaveTextContent(/not available yet/i);
  expect(JSON.parse(sessionStorage.getItem("foroba.signupIntent") ?? "{}")).toEqual({ app: "yiriba", plan: "expert" });
  window.history.pushState({}, "", "/");
});

test("ignores a hostile intent", () => {
  sessionStorage.clear();
  window.history.pushState({}, "", "/register?app=https://evil.example&plan=premium");
  renderPage();
  expect(screen.queryByRole("note")).toBeNull();
  window.history.pushState({}, "", "/");
});
