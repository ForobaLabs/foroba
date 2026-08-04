import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { startAuthentication } from "@simplewebauthn/browser";
import { Button, Card, Input } from "@foroba/ui";
import {
  login,
  loginWithMethod,
  loginWithRecoveryCode,
  passkeyLoginOptions,
  passkeyLoginVerify,
  sendLoginEmailOtp,
  type Mfa2FAChallenge,
} from "../auth/api";

const METHOD_LABELS: Record<"totp" | "email_otp", string> = {
  totp: "Authenticator app code",
  email_otp: "Email code",
};

export function LoginPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [challenge, setChallenge] = useState<Mfa2FAChallenge | null>(null);
  const [method, setMethod] = useState<"totp" | "email_otp">("totp");
  const [code, setCode] = useState("");
  const [emailOtpSent, setEmailOtpSent] = useState(false);
  const [useRecoveryCode, setUseRecoveryCode] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");

  const challengeMethods = (challenge?.methods.filter((m) => m !== "webauthn") ?? []) as (
    | "totp"
    | "email_otp"
  )[];
  const hasPasskeyStepUp = challenge?.methods.includes("webauthn") ?? false;

  useEffect(() => {
    if (challenge && method === "email_otp" && !emailOtpSent) {
      sendLoginEmailOtp(challenge.email)
        .then(() => setEmailOtpSent(true))
        .catch((err) => setError(err instanceof Error ? err.message : "Failed to send code."));
    }
  }, [challenge, method, emailOtpSent]);

  async function finishLogin() {
    await qc.invalidateQueries({ queryKey: ["session"] });
    navigate("/", { replace: true });
  }

  async function onSubmitPassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await login(email, password);
      if ("mfa_required" in result) {
        const nonWebauthn = result.methods.filter((m) => m !== "webauthn") as (
          | "totp"
          | "email_otp"
        )[];
        setChallenge(result);
        setMethod(nonWebauthn[0] ?? "totp");
        setEmailOtpSent(false);
      } else {
        await finishLogin();
      }
    } catch {
      setError("Invalid email or password.");
    } finally {
      setLoading(false);
    }
  }

  async function onVerifyCode(e: React.FormEvent) {
    e.preventDefault();
    if (!challenge) return;
    setError(null);
    setLoading(true);
    try {
      await loginWithMethod(challenge.email, code, method);
      await finishLogin();
    } catch {
      setError("Invalid code.");
    } finally {
      setLoading(false);
    }
  }

  async function onVerifyRecoveryCode(e: React.FormEvent) {
    e.preventDefault();
    if (!challenge) return;
    setError(null);
    setLoading(true);
    try {
      await loginWithRecoveryCode(challenge.email, recoveryCode);
      await finishLogin();
    } catch {
      setError("Invalid recovery code.");
    } finally {
      setLoading(false);
    }
  }

  async function onPasskeyLogin() {
    if (!email) {
      setError("Enter your email first.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const options = await passkeyLoginOptions(email);
      const assertion = await startAuthentication({ optionsJSON: options });
      await passkeyLoginVerify(email, JSON.stringify(assertion));
      await finishLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Passkey sign-in failed.");
    } finally {
      setLoading(false);
    }
  }

  if (challenge) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-primary)] p-4">
        <Card className="w-full max-w-sm p-6">
          <h1 className="mb-1 text-xl font-semibold text-[var(--color-text-primary)]">
            Verify it's you
          </h1>
          <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
            Signed in as {challenge.email}
          </p>
          {!useRecoveryCode ? (
            <form onSubmit={onVerifyCode} className="flex flex-col gap-4">
              {challengeMethods.length > 1 && (
                <div className="flex flex-col gap-1">
                  <label htmlFor="method" className="text-sm text-[var(--color-text-secondary)]">
                    Verification method
                  </label>
                  <select
                    id="method"
                    className="rounded-md border border-[var(--color-bg-border)] bg-[var(--color-bg-primary)] p-2 text-[var(--color-text-primary)]"
                    value={method}
                    onChange={(e) => {
                      setMethod(e.target.value as "totp" | "email_otp");
                      setEmailOtpSent(false);
                      setCode("");
                    }}
                  >
                    {challengeMethods.map((m) => (
                      <option key={m} value={m}>
                        {METHOD_LABELS[m]}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {method === "email_otp" && (
                <p className="text-xs text-[var(--color-text-muted)]">
                  {emailOtpSent ? `Code sent to ${challenge.email}.` : "Sending code…"}
                </p>
              )}
              <div className="flex flex-col gap-1">
                <label htmlFor="code" className="text-sm text-[var(--color-text-secondary)]">
                  {METHOD_LABELS[method]}
                </label>
                <Input
                  id="code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>
              {error && (
                <p role="alert" className="text-sm text-[var(--color-negative)]">
                  {error}
                </p>
              )}
              <Button type="submit" disabled={loading || code.length === 0} className="w-full">
                {loading ? "Verifying…" : "Verify"}
              </Button>
              {hasPasskeyStepUp && (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={onPasskeyLogin}
                  disabled={loading}
                  className="w-full"
                >
                  Sign in with passkey instead
                </Button>
              )}
              <button
                type="button"
                onClick={() => {
                  setUseRecoveryCode(true);
                  setError(null);
                }}
                className="text-center text-sm text-[var(--color-accent)] hover:underline"
              >
                Use a recovery code instead
              </button>
            </form>
          ) : (
            <form onSubmit={onVerifyRecoveryCode} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1">
                <label htmlFor="recovery-code" className="text-sm text-[var(--color-text-secondary)]">
                  Recovery code
                </label>
                <Input
                  id="recovery-code"
                  type="text"
                  autoComplete="off"
                  required
                  value={recoveryCode}
                  onChange={(e) => setRecoveryCode(e.target.value)}
                />
              </div>
              {error && (
                <p role="alert" className="text-sm text-[var(--color-negative)]">
                  {error}
                </p>
              )}
              <Button
                type="submit"
                disabled={loading || recoveryCode.length === 0}
                className="w-full"
              >
                {loading ? "Verifying…" : "Verify"}
              </Button>
              <button
                type="button"
                onClick={() => {
                  setUseRecoveryCode(false);
                  setError(null);
                }}
                className="text-center text-sm text-[var(--color-accent)] hover:underline"
              >
                Back to verification code
              </button>
            </form>
          )}
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-primary)] p-4">
      <Card className="w-full max-w-sm p-6">
        <h1 className="mb-6 text-xl font-semibold text-[var(--color-text-primary)]">
          Sign in to Foroba
        </h1>
        <form onSubmit={onSubmitPassword} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="email" className="text-sm text-[var(--color-text-secondary)]">
              Email
            </label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              spellCheck={false}
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="password" className="text-sm text-[var(--color-text-secondary)]">
              Password
            </label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-[var(--color-negative)]">
              {error}
            </p>
          )}
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Signing in…" : "Sign in"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={onPasskeyLogin}
            disabled={loading}
            className="w-full"
          >
            Sign in with passkey
          </Button>
          <p className="text-center text-sm text-[var(--color-text-secondary)]">
            No account?{" "}
            <a href="/register" className="text-[var(--color-accent)] hover:underline">
              Register
            </a>
          </p>
        </form>
      </Card>
    </div>
  );
}
