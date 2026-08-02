import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { startRegistration } from "@simplewebauthn/browser";
import { Button, Card, Input } from "@foroba/ui";
import {
  enrollTotp,
  passkeyRegisterOptions,
  passkeyRegisterVerify,
  regenerateRecoveryCodes,
  sendEmailOtp,
  verifyEmailOtp,
  verifyTotp,
} from "../auth/api";

type Stage = "choose" | "passkey" | "totp" | "email_otp" | "recovery";

export function EnrollmentWizard() {
  const navigate = useNavigate();
  const [stage, setStage] = useState<Stage>("choose");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [totpSecret, setTotpSecret] = useState<string | null>(null);
  const [totpQr, setTotpQr] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [emailOtpCode, setEmailOtpCode] = useState("");
  const [emailOtpSent, setEmailOtpSent] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);

  async function goToRecovery() {
    const codes = await regenerateRecoveryCodes();
    setRecoveryCodes(codes);
    setStage("recovery");
  }

  async function onChoosePasskey() {
    setError(null);
    setLoading(true);
    setStage("passkey");
    try {
      const options = await passkeyRegisterOptions();
      const attestation = await startRegistration({ optionsJSON: options });
      await passkeyRegisterVerify(JSON.stringify(attestation), "Primary passkey");
      await goToRecovery();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Passkey setup failed.");
      setStage("choose");
    } finally {
      setLoading(false);
    }
  }

  async function onChooseTotp() {
    setError(null);
    setStage("totp");
    try {
      const { secret, qr } = await enrollTotp();
      setTotpSecret(secret);
      setTotpQr(qr);
    } catch {
      setError("Failed to start authenticator setup.");
    }
  }

  async function onVerifyTotp(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await verifyTotp(totpCode);
      await goToRecovery();
    } catch {
      setError("Invalid code.");
    } finally {
      setLoading(false);
    }
  }

  async function onChooseEmailOtp() {
    setError(null);
    setStage("email_otp");
    setEmailOtpSent(false);
    try {
      await sendEmailOtp();
      setEmailOtpSent(true);
    } catch {
      setError("Failed to send email code.");
    }
  }

  async function onVerifyEmailOtp(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await verifyEmailOtp(emailOtpCode);
      await goToRecovery();
    } catch {
      setError("Invalid or expired code.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-primary)] p-4">
      <Card className="w-full max-w-md p-6">
        {stage === "choose" && (
          <>
            <h1 className="mb-1 text-xl font-semibold text-[var(--color-text-primary)]">
              Secure your account
            </h1>
            <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
              This handles real financial data, so a second factor is required. Pick how you'd
              like to sign in.
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={onChoosePasskey}
                disabled={loading}
                className="rounded-md border border-[var(--color-bg-border)] p-4 text-left transition-colors hover:bg-[var(--color-bg-elevated)]"
              >
                <p className="font-medium text-[var(--color-text-primary)]">
                  Passkey (recommended)
                </p>
                <p className="text-sm text-[var(--color-text-secondary)]">
                  Use your device's fingerprint, face, or security key. No codes to remember.
                </p>
              </button>
              <button
                onClick={onChooseTotp}
                disabled={loading}
                className="rounded-md border border-[var(--color-bg-border)] p-4 text-left transition-colors hover:bg-[var(--color-bg-elevated)]"
              >
                <p className="font-medium text-[var(--color-text-primary)]">Authenticator app</p>
                <p className="text-sm text-[var(--color-text-secondary)]">
                  Scan a QR code with Google Authenticator, 1Password, or similar.
                </p>
              </button>
              <button
                onClick={onChooseEmailOtp}
                disabled={loading}
                className="rounded-md border border-[var(--color-bg-border)] p-4 text-left transition-colors hover:bg-[var(--color-bg-elevated)]"
              >
                <p className="font-medium text-[var(--color-text-primary)]">Email code</p>
                <p className="text-sm text-[var(--color-text-secondary)]">
                  Get a one-time code sent to your registered email each time you sign in.
                </p>
              </button>
            </div>
            {error && (
              <p role="alert" className="mt-4 text-sm text-[var(--color-negative)]">
                {error}
              </p>
            )}
          </>
        )}

        {stage === "totp" && (
          <form onSubmit={onVerifyTotp} className="flex flex-col gap-4">
            <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
              Scan this QR code
            </h1>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Scan it with your authenticator app, then enter the 6-digit code it shows.
            </p>
            {totpQr && <img src={totpQr} alt="TOTP QR code" className="mx-auto h-40 w-40" />}
            {totpSecret && (
              <p className="break-all text-center text-xs text-[var(--color-text-muted)]">
                {totpSecret}
              </p>
            )}
            <div className="flex flex-col gap-1">
              <label htmlFor="totp-code" className="text-sm text-[var(--color-text-secondary)]">
                6-digit code
              </label>
              <Input
                id="totp-code"
                type="text"
                inputMode="numeric"
                required
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
              />
            </div>
            {error && (
              <p role="alert" className="text-sm text-[var(--color-negative)]">
                {error}
              </p>
            )}
            <Button type="submit" disabled={loading || totpCode.length === 0} className="w-full">
              {loading ? "Verifying…" : "Verify and continue"}
            </Button>
            <button
              type="button"
              onClick={() => setStage("choose")}
              className="text-center text-sm text-[var(--color-accent)] hover:underline"
            >
              Back
            </button>
          </form>
        )}

        {stage === "email_otp" && (
          <form onSubmit={onVerifyEmailOtp} className="flex flex-col gap-4">
            <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
              Check your email
            </h1>
            <p className="text-sm text-[var(--color-text-secondary)]">
              {emailOtpSent ? "We sent a 6-digit code to your email." : "Sending code…"}
            </p>
            <div className="flex flex-col gap-1">
              <label
                htmlFor="email-otp-code"
                className="text-sm text-[var(--color-text-secondary)]"
              >
                6-digit code
              </label>
              <Input
                id="email-otp-code"
                type="text"
                inputMode="numeric"
                required
                value={emailOtpCode}
                onChange={(e) => setEmailOtpCode(e.target.value)}
              />
            </div>
            {error && (
              <p role="alert" className="text-sm text-[var(--color-negative)]">
                {error}
              </p>
            )}
            <Button
              type="submit"
              disabled={loading || emailOtpCode.length === 0}
              className="w-full"
            >
              {loading ? "Verifying…" : "Verify and continue"}
            </Button>
            <button
              type="button"
              onClick={() => setStage("choose")}
              className="text-center text-sm text-[var(--color-accent)] hover:underline"
            >
              Back
            </button>
          </form>
        )}

        {stage === "passkey" && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <p className="text-sm text-[var(--color-text-secondary)]">
              Follow your browser's prompt to set up your passkey…
            </p>
            {error && (
              <>
                <p role="alert" className="text-sm text-[var(--color-negative)]">
                  {error}
                </p>
                <button
                  onClick={() => setStage("choose")}
                  className="text-sm text-[var(--color-accent)] hover:underline"
                >
                  Back
                </button>
              </>
            )}
          </div>
        )}

        {stage === "recovery" && recoveryCodes && (
          <div className="flex flex-col gap-4">
            <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
              Save your recovery codes
            </h1>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Each code can be used once to sign in if you lose access to your other method.
              They're shown only this once — save them somewhere safe.
            </p>
            <div className="grid grid-cols-2 gap-2 rounded-md border border-[var(--color-bg-border)] bg-[var(--color-bg-elevated)] p-4 font-mono text-sm text-[var(--color-text-primary)]">
              {recoveryCodes.map((c) => (
                <span key={c}>{c}</span>
              ))}
            </div>
            <Button className="w-full" onClick={() => navigate("/onboarding", { replace: true })}>
              I've saved these codes
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
