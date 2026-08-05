import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { RegisterPage } from "./RegisterPage";

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
