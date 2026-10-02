import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { startAuthentication } from "@simplewebauthn/browser";
import { Button, Card, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, Input } from "@foroba/ui";
import { useAuth } from "../auth/AuthProvider";
import {
  confirmPasswordReset,
  login,
  loginWithMethod,
  loginWithRecoveryCode,
  passkeyLoginOptions,
  passkeyLoginVerify,
  requestPasswordReset,
  sendLoginEmailOtp,
  type Mfa2FAChallenge,
} from "../auth/api";

export function LoginPage() {
  const { t } = useTranslation();
  const methodLabels: Record<"totp" | "email_otp", string> = {
    totp: t("login.methodTotp"),
    email_otp: t("login.methodEmail"),
  };
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { user, loading: sessionLoading } = useAuth();
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
  // Forgot-password flow
  const [forgotOpen, setForgotOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotSent, setForgotSent] = useState(false);
  const [forgotCode, setForgotCode] = useState("");
  const [forgotNewPw, setForgotNewPw] = useState("");
  const [forgotNewPwConfirm, setForgotNewPwConfirm] = useState("");
  const [forgotError, setForgotError] = useState<string | null>(null);
  const [forgotLoading, setForgotLoading] = useState(false);

  const challengeMethods = (challenge?.methods.filter((m) => m !== "webauthn") ?? []) as (
    | "totp"
    | "email_otp"
  )[];
  const hasPasskeyStepUp = challenge?.methods.includes("webauthn") ?? false;

  useEffect(() => {
    if (challenge && method === "email_otp" && !emailOtpSent) {
      sendLoginEmailOtp(challenge.email)
        .then(() => setEmailOtpSent(true))
        .catch((err) => setError(err instanceof Error ? err.message : t("login.errSendCode")));
    }
  }, [challenge, method, emailOtpSent]);

  // FOR-D08: a second tab sharing the suite_session cookie could still land on
  // and interact with the raw login form instead of the authenticated app shell.
  if (!sessionLoading && user) {
    return <Navigate to="/" replace />;
  }

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
      setError(t("login.errInvalid"));
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
      setError(t("login.errCode"));
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
      setError(t("login.errRecovery"));
    } finally {
      setLoading(false);
    }
  }

  async function onPasskeyLogin() {
    if (!email) {
      setError(t("login.errEmailFirst"));
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
      setError(err instanceof Error ? err.message : t("login.errPasskey"));
    } finally {
      setLoading(false);
    }
  }

  async function onForgotRequest(e: React.FormEvent) {
    e.preventDefault();
    setForgotLoading(true);
    setForgotError(null);
    try {
      await requestPasswordReset(forgotEmail);
      setForgotSent(true);
    } catch (err) {
      setForgotError(err instanceof Error ? err.message : t("login.errReset"));
    } finally {
      setForgotLoading(false);
    }
  }

  async function onForgotConfirm(e: React.FormEvent) {
    e.preventDefault();
    setForgotLoading(true);
    setForgotError(null);
    try {
      await confirmPasswordReset(forgotEmail, forgotCode, forgotNewPw, forgotNewPwConfirm);
      setForgotOpen(false);
      setForgotSent(false);
      setForgotCode("");
      setForgotNewPw("");
      setForgotNewPwConfirm("");
    } catch (err) {
      setForgotError(err instanceof Error ? err.message : t("login.errResetConfirm"));
    } finally {
      setForgotLoading(false);
    }
  }

  if (challenge) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-primary)] p-4">
        <Card className="w-full max-w-sm p-6">
          <h1 className="mb-1 text-xl font-semibold text-[var(--color-text-primary)]">
            {t("login.verifyTitle")}
          </h1>
          <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
            {t("login.signedInAs", { email: challenge.email })}
          </p>
          {!useRecoveryCode ? (
            <form onSubmit={onVerifyCode} className="flex flex-col gap-4">
              {challengeMethods.length > 1 && (
                <div className="flex flex-col gap-1">
                  <label htmlFor="method" className="text-sm text-[var(--color-text-secondary)]">
                    {t("login.method")}
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
                        {methodLabels[m]}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {method === "email_otp" && (
                <p className="text-xs text-[var(--color-text-muted)]">
                  {emailOtpSent ? t("login.codeSent", { email: challenge.email }) : t("login.sendingCode")}
                </p>
              )}
              <div className="flex flex-col gap-1">
                <label htmlFor="code" className="text-sm text-[var(--color-text-secondary)]">
                  {methodLabels[method]}
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
                {loading ? t("login.verifying") : t("login.verify")}
              </Button>
              {hasPasskeyStepUp && (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={onPasskeyLogin}
                  disabled={loading}
                  className="w-full"
                >
                  {t("login.passkeyInstead")}
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
                {t("login.useRecovery")}
              </button>
            </form>
          ) : (
            <form onSubmit={onVerifyRecoveryCode} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1">
                <label htmlFor="recovery-code" className="text-sm text-[var(--color-text-secondary)]">
                  {t("login.recoveryCode")}
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
                {loading ? t("login.verifying") : t("login.verify")}
              </Button>
              <button
                type="button"
                onClick={() => {
                  setUseRecoveryCode(false);
                  setError(null);
                }}
                className="text-center text-sm text-[var(--color-accent)] hover:underline"
              >
                {t("login.backToCode")}
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
          {t("login.title")}
        </h1>
        <form onSubmit={onSubmitPassword} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="email" className="text-sm text-[var(--color-text-secondary)]">
              {t("login.email")}
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
              {t("login.password")}
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
            {loading ? t("login.signingIn") : t("login.signIn")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={onPasskeyLogin}
            disabled={loading}
            className="w-full"
          >
            {t("login.passkey")}
          </Button>
          <button
            type="button"
            onClick={() => { setForgotEmail(email); setForgotOpen(true); }}
            className="text-center text-sm text-[var(--color-accent)] hover:underline"
          >
            {t("login.forgot")}
          </button>
          <p className="text-center text-sm text-[var(--color-text-secondary)]">
            {t("login.noAccount")}{" "}
            <a href="/register" className="text-[var(--color-accent)] hover:underline">
              {t("login.register")}
            </a>
          </p>
        </form>
      </Card>

      <Dialog open={forgotOpen} onOpenChange={(open) => { if (!open) { setForgotOpen(false); setForgotSent(false); setForgotError(null); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("login.resetTitle")}</DialogTitle>
            <DialogDescription>
              {forgotSent
                ? t("login.resetSent")
                : t("login.resetAsk")}
            </DialogDescription>
          </DialogHeader>
          {!forgotSent ? (
            <form onSubmit={onForgotRequest} className="flex flex-col gap-3">
              <Input
                type="email"
                placeholder={t("login.emailPlaceholder")}
                value={forgotEmail}
                onChange={(e) => setForgotEmail(e.target.value)}
                required
                autoComplete="email"
              />
              {forgotError && (
                <p role="alert" className="text-xs text-[var(--color-negative)]">{forgotError}</p>
              )}
              <Button type="submit" disabled={forgotLoading || forgotEmail.length === 0} className="w-full">
                {forgotLoading ? t("login.sending") : t("login.sendReset")}
              </Button>
            </form>
          ) : (
            <form onSubmit={onForgotConfirm} className="flex flex-col gap-3">
              <Input
                type="text"
                placeholder={t("login.codePlaceholder")}
                inputMode="numeric"
                value={forgotCode}
                onChange={(e) => setForgotCode(e.target.value)}
                required
                autoComplete="one-time-code"
              />
              <Input
                type="password"
                placeholder={t("login.newPassword")}
                value={forgotNewPw}
                onChange={(e) => setForgotNewPw(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
              <Input
                type="password"
                placeholder={t("login.confirmNewPassword")}
                value={forgotNewPwConfirm}
                onChange={(e) => setForgotNewPwConfirm(e.target.value)}
                required
                autoComplete="new-password"
              />
              {forgotError && (
                <p role="alert" className="text-xs text-[var(--color-negative)]">{forgotError}</p>
              )}
              <Button
                type="submit"
                disabled={forgotLoading || forgotCode.length === 0 || forgotNewPw.length < 8}
                className="w-full"
              >
                {forgotLoading ? t("login.resetting") : t("login.resetPassword")}
              </Button>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
