export interface SessionUser {
  id: number;
  email: string;
  name: string;
  tier: "free" | "premium";
  audience: "base" | "expert";
  audience_locked: boolean;
  totp_enabled: boolean;
  is_admin: boolean;
  display_currency: string;
  show_debts: boolean;
  birth_year: number | null;
  country: string | null;
  onboarding_completed_at: string | null;
}

const opts: RequestInit = { credentials: "include" };

export async function fetchMe(): Promise<SessionUser | null> {
  const r = await fetch("/jeli/auth/me", opts);
  if (r.status === 401) return null;
  if (!r.ok) throw new Error("session error");
  return r.json();
}

export async function login(email: string, password: string): Promise<SessionUser> {
  const r = await fetch("/jeli/auth/login", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error("invalid credentials");
  return r.json();
}

export interface RegisterInput {
  email: string;
  emailConfirm: string;
  name: string;
  password: string;
  passwordConfirm: string;
  birthYear?: number;
  country?: string;
}

export async function register(input: RegisterInput): Promise<SessionUser> {
  const r = await fetch("/jeli/auth/register", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: input.email,
      email_confirm: input.emailConfirm,
      name: input.name,
      password: input.password,
      password_confirm: input.passwordConfirm,
      birth_year: input.birthYear ?? null,
      country: input.country ?? null,
    }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    const detail = Array.isArray(body?.detail)
      ? body.detail[0]?.msg
      : body?.detail;
    throw new Error(detail ?? "Registration failed. Email may already be in use.");
  }
  return r.json();
}

export async function completeOnboarding(): Promise<void> {
  await fetch("/jeli/auth/onboarding/complete", { ...opts, method: "POST" });
}

export async function logout(): Promise<void> {
  await fetch("/jeli/auth/logout", { ...opts, method: "POST" });
}

export interface HouseholdMember {
  id: number;
  email: string;
  name: string;
}

export interface HouseholdState {
  household_id: string | null;
  members: HouseholdMember[];
  share_preferences: Record<string, boolean>;
}

export async function fetchHousehold(): Promise<HouseholdState> {
  const r = await fetch("/jeli/auth/household", opts);
  if (!r.ok) throw new Error("failed to load household");
  return r.json();
}

export async function joinHousehold(
  email: string,
): Promise<{ household_id: string; members: HouseholdMember[] }> {
  const r = await fetch("/jeli/auth/household/join", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    throw new Error(body?.detail ?? "failed to join household");
  }
  return r.json();
}

export async function leaveHousehold(): Promise<void> {
  const r = await fetch("/jeli/auth/household/leave", { ...opts, method: "POST" });
  if (!r.ok) throw new Error("failed to leave household");
}

export async function setSharePreference(
  resourceType: string,
  shared: boolean,
): Promise<void> {
  const r = await fetch("/jeli/auth/household/share", {
    ...opts,
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resource_type: resourceType, shared }),
  });
  if (!r.ok) throw new Error("failed to update share preference");
}

export async function updateDisplayCurrency(currency: string): Promise<void> {
  const r = await fetch("/jeli/auth/me/currency", {
    ...opts,
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_currency: currency }),
  });
  if (!r.ok) throw new Error("failed to update display currency");
}

export async function updateShowDebts(showDebts: boolean): Promise<void> {
  const r = await fetch("/jeli/auth/me/show-debts", {
    ...opts,
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ show_debts: showDebts }),
  });
  if (!r.ok) throw new Error("failed to update show_debts");
}
