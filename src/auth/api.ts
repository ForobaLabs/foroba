export interface SessionUser {
  id: number;
  email: string;
  name: string;
  tier: "free" | "premium";
  audience: "base" | "expert";
  audience_locked: boolean;
  totp_enabled: boolean;
  is_admin: boolean;
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
