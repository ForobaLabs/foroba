import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { startRegistration } from "@simplewebauthn/browser";
import { Button, Card, Input } from "@foroba/ui";
import {
  enrollTotp,
  fetchMfaMethods,
  passkeyRegisterOptions,
  passkeyRegisterVerify,
  regenerateRecoveryCodes,
  sendEmailOtp,
  verifyEmailOtp,
  verifyTotp,
} from "../auth/api";

type MethodKey = "totp" | "email_otp" | "webauthn";
type Stage = "choose" | "passkey" | "totp" | "email_otp" | "more" | "recovery";

export function EnrollmentWizard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [stage, setStage] = useState<Stage>("choose");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [totpSecret, setTotpSecret] = useState<string | null>(null);
  const [totpQr, setTotpQr] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [emailOtpCode, setEmailOtpCode] = useState("");
  const [emailOtpSent, setEmailOtpSent] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  // Methods enrolled so far in this session — the user can add more than one before
  // finishing, since step-up later lets them pick whichever enrolled method they prefer.
  const [enrolled, setEnrolled] = useState<Set<MethodKey>>(new Set());

  const backStage: Stage = enrolled.size > 0 ? "more" : "choose";

  useEffect(() => {
    // FOR-D06: App's guard only forces users INTO /enroll when mfa_enrollment_pending is
    // true — it never stops an already-fully-enrolled user from navigating here directly
    // (URL/bookmark/back-button) and re-triggering enrollment. Bounce them to /settings
    // instead; re-enrollment from an already-enrolled state now requires the dedicated
    // password-confirmation flow in SecuritySettingsSection, not this wizard.
    let cancelled = false;
    void fetchMfaMethods()
      .then((methods) => {
        if (cancelled) return;
        if (methods.totp_enabled || methods.email_otp_enabled || methods.webauthn_enabled) {
          navigate("/settings", { replace: true });
        }
      })
      .catch(() => {
        // Best-effort guard only — if the check itself fails, fall through to the wizard.
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  function onMethodEnrolled(method: MethodKey) {
    setEnrolled((prev) => new Set(prev).add(method));
    // Server clears mfa_enrollment_pending as soon as any method is enrolled — refetch the
    // cached session so App's guard (foroba#173) stops redirecting here once we navigate away.
    void qc.invalidateQueries({ queryKey: ["session"] });
    setStage("more");
  }

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
      onMethodEnrolled("webauthn");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Passkey setup failed.");
      setStage(backStage);
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
      onMethodEnrolled("totp");
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
      onMethodEnrolled("email_otp");
    } catch {
      setError("Invalid or expired code.");
    } finally {
      setLoading(false);
    }
  }

  const methodOptions: { key: MethodKey; label: string; description: string; onClick: () => void }[] = [
    {
      key: "webauthn",
      label: "Passkey (recommended)",
      description: "Use your device's fingerprint, face, or security key. No codes to remember.",
      onClick: onChoosePasskey,
    },
    {
      key: "totp",
      label: "Authenticator app",
      description: "Scan a QR code with Google Authenticator, 1Password, or similar.",
      onClick: onChooseTotp,
    },
    {
      key: "email_otp",
      label: "Email code",
      description: "Get a one-time code sent to your registered email each time you sign in.",
      onClick: onChooseEmailOtp,
    },
  ];

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
              {methodOptions.map((m) => (
                <button
                  key={m.key}
                  onClick={m.onClick}
                  disabled={loading}
                  className="rounded-md border border-[var(--color-bg-border)] p-4 text-left transition-colors hover:bg-[var(--color-bg-elevated)]"
                >
                  <p className="font-medium text-[var(--color-text-primary)]">{m.label}</p>
                  <p className="text-sm text-[var(--color-text-secondary)]">{m.description}</p>
                </button>
              ))}
            </div>
            {error && (
              <p role="alert" className="mt-4 text-sm text-[var(--color-negative)]">
                {error}
              </p>
            )}
          </>
        )}

        {stage === "more" && (
          <>
            <h1 className="mb-1 text-xl font-semibold text-[var(--color-text-primary)]">
              Add another way to sign in?
            </h1>
            <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
              You can enable more than one method now, or add more later in Settings → Security.
            </p>
            <div className="flex flex-col gap-3">
              {methodOptions
                .filter((m) => !enrolled.has(m.key))
                .map((m) => (
                  <button
                    key={m.key}
                    onClick={m.onClick}
                    disabled={loading}
                    className="rounded-md border border-[var(--color-bg-border)] p-4 text-left transition-colors hover:bg-[var(--color-bg-elevated)]"
                  >
                    <p className="font-medium text-[var(--color-text-primary)]">{m.label}</p>
                    <p className="text-sm text-[var(--color-text-secondary)]">{m.description}</p>
                  </button>
                ))}
            </div>
            {error && (
              <p role="alert" className="mt-4 text-sm text-[var(--color-negative)]">
                {error}
              </p>
            )}
            <Button className="mt-4 w-full" onClick={() => void goToRecovery()}>
              Finish setup
            </Button>
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
              onClick={() => setStage(backStage)}
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
              onClick={() => setStage(backStage)}
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
                  onClick={() => setStage(backStage)}
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
