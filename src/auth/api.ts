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

export async function register(
  email: string,
  name: string,
  password: string,
): Promise<SessionUser> {
  const r = await fetch("/jeli/auth/register", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name, password }),
  });
  if (!r.ok) throw new Error("registration failed");
  return r.json();
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
