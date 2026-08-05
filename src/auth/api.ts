import type {
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
} from "@simplewebauthn/browser";

export interface SessionUser {
  id: number;
  email: string;
  name: string;
  tier: "free" | "premium";
  audience: "base" | "expert";
  audience_locked: boolean;
  totp_enabled: boolean;
  email_otp_enabled: boolean;
  webauthn_enabled: boolean;
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

export async function login(email: string, password: string): Promise<SessionUser | Mfa2FAChallenge> {
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
  tosAccepted: boolean;
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
      tos_accepted: input.tosAccepted,
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

export async function deleteAccount(password: string): Promise<void> {
  const r = await fetch("/jeli/auth/account", {
    ...opts,
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    throw new Error(body?.detail ?? "Failed to delete account. Please try again.");
  }
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

export interface ConsentRecord {
  document_type: "terms_of_service" | "privacy_policy";
  document_version: string;
  accepted_at: string;
}

export async function fetchConsents(): Promise<ConsentRecord[]> {
  const r = await fetch("/jeli/auth/consents", opts);
  if (!r.ok) throw new Error("failed to load consent records");
  return r.json();
}

export interface MfaMethods {
  totp_enabled: boolean;
  email_otp_enabled: boolean;
  webauthn_enabled: boolean;
  recovery_codes_remaining: number;
}

export async function fetchMfaMethods(): Promise<MfaMethods> {
  const r = await fetch("/jeli/auth/2fa/methods", opts);
  if (!r.ok) throw new Error("failed to load MFA methods");
  return r.json();
}

export async function removeMfaMethod(method: "totp" | "email_otp" | "webauthn"): Promise<void> {
  const r = await fetch(`/jeli/auth/2fa/methods/${method}`, { ...opts, method: "DELETE" });
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    throw new Error(body?.detail ?? "failed to remove method");
  }
}

export async function regenerateRecoveryCodes(): Promise<string[]> {
  const r = await fetch("/jeli/auth/2fa/recovery-codes/regenerate", { ...opts, method: "POST" });
  if (!r.ok) throw new Error("failed to regenerate recovery codes");
  return (await r.json()).codes;
}

export async function sendEmailOtp(): Promise<void> {
  const r = await fetch("/jeli/auth/2fa/email-otp/send", { ...opts, method: "POST" });
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    throw new Error(body?.detail ?? "failed to send email code");
  }
}

export async function verifyEmailOtp(code: string): Promise<void> {
  const r = await fetch("/jeli/auth/2fa/email-otp/verify", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!r.ok) throw new Error("invalid or expired code");
}

export async function enrollTotp(): Promise<{ secret: string; qr: string }> {
  const r = await fetch("/jeli/auth/2fa/enroll", { ...opts, method: "POST" });
  if (!r.ok) throw new Error("failed to start TOTP enrollment");
  return r.json();
}

export async function verifyTotp(code: string): Promise<void> {
  const r = await fetch("/jeli/auth/2fa/verify", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!r.ok) throw new Error("invalid code");
}

export async function passkeyRegisterOptions(): Promise<PublicKeyCredentialCreationOptionsJSON> {
  const r = await fetch("/jeli/auth/webauthn/register/options", { ...opts, method: "POST" });
  if (!r.ok) throw new Error("failed to start passkey registration");
  return r.json();
}

export async function passkeyRegisterVerify(credential: string, label: string): Promise<void> {
  const r = await fetch("/jeli/auth/webauthn/register/verify", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential, label }),
  });
  if (!r.ok) throw new Error("passkey registration failed");
}

export interface Mfa2FAChallenge {
  mfa_required: true;
  email: string;
  methods: ("totp" | "email_otp" | "webauthn")[];
}

export async function loginWithMethod(
  email: string,
  code: string,
  method: "totp" | "email_otp",
): Promise<SessionUser> {
  const r = await fetch("/jeli/auth/login/2fa", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code, method }),
  });
  if (!r.ok) throw new Error("invalid code");
  return r.json();
}

export async function sendLoginEmailOtp(email: string): Promise<void> {
  const r = await fetch("/jeli/auth/login/email-otp/send", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => null);
    throw new Error(body?.detail ?? "failed to send email code");
  }
}

export async function loginWithRecoveryCode(email: string, recoveryCode: string): Promise<SessionUser> {
  const r = await fetch("/jeli/auth/login/recovery-code", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, recovery_code: recoveryCode }),
  });
  if (!r.ok) throw new Error("invalid recovery code");
  return r.json();
}

export async function passkeyLoginOptions(email: string): Promise<PublicKeyCredentialRequestOptionsJSON> {
  const r = await fetch("/jeli/auth/login/webauthn/options-by-email", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!r.ok) throw new Error("passkey not set up for this account");
  return r.json();
}

export async function passkeyLoginVerify(email: string, credential: string): Promise<SessionUser> {
  const r = await fetch("/jeli/auth/login/webauthn/verify", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, credential }),
  });
  if (!r.ok) throw new Error("passkey verification failed");
  return r.json();
}

export type StepupApp = "pazuru" | "tsumi";

export async function stepupVerify(
  app: StepupApp,
  method: "totp" | "email_otp" | "recovery_code" | "webauthn",
  codeOrCredential: string,
): Promise<void> {
  const body =
    method === "webauthn"
      ? { app, method, credential: codeOrCredential }
      : { app, method, code: codeOrCredential };
  const r = await fetch("/jeli/auth/stepup/verify", {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("step-up verification failed");
}
