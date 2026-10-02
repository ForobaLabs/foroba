import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
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

  async function copyCodes(codes: string[]) {
    try {
      await navigator.clipboard.writeText(codes.join("\n"));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can be unavailable (insecure context, denied permission) — the codes stay visible and downloadable.
    }
  }

  function downloadCodes(codes: string[]) {
    const url = URL.createObjectURL(new Blob([codes.join("\n") + "\n"], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "foroba-recovery-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
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
      setError(err instanceof Error ? err.message : t("enroll.errPasskey"));
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
      setError(t("enroll.errTotpStart"));
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
      setError(t("enroll.errCode"));
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
      setError(t("enroll.errEmailSend"));
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
      setError(t("enroll.errEmailCode"));
    } finally {
      setLoading(false);
    }
  }

  const methodOptions: { key: MethodKey; label: string; description: string; onClick: () => void }[] = [
    {
      key: "webauthn",
      label: t("enroll.passkeyLabel"),
      description: t("enroll.passkeyDesc"),
      onClick: onChoosePasskey,
    },
    {
      key: "totp",
      label: t("enroll.totpLabel"),
      description: t("enroll.totpDesc"),
      onClick: onChooseTotp,
    },
    {
      key: "email_otp",
      label: t("enroll.emailLabel"),
      description: t("enroll.emailDesc"),
      onClick: onChooseEmailOtp,
    },
  ];

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-primary)] p-4">
      <Card className="w-full max-w-md p-6">
        {stage === "choose" && (
          <>
            <h1 className="mb-1 text-xl font-semibold text-[var(--color-text-primary)]">
              {t("enroll.chooseTitle")}
            </h1>
            <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
              {t("enroll.chooseIntro")}
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
              {t("enroll.moreTitle")}
            </h1>
            <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
              {t("enroll.moreIntro")}
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
              {t("enroll.finish")}
            </Button>
          </>
        )}

        {stage === "totp" && (
          <form onSubmit={onVerifyTotp} className="flex flex-col gap-4">
            <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
              {t("enroll.qrTitle")}
            </h1>
            <p className="text-sm text-[var(--color-text-secondary)]">
              {t("enroll.qrIntro")}
            </p>
            {totpQr && <img src={totpQr} alt={t("enroll.qrAlt")} className="mx-auto h-40 w-40" />}
            {totpSecret && (
              <p className="break-all text-center text-xs text-[var(--color-text-muted)]">
                {totpSecret}
              </p>
            )}
            <div className="flex flex-col gap-1">
              <label htmlFor="totp-code" className="text-sm text-[var(--color-text-secondary)]">
                {t("enroll.code6")}
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
              {loading ? t("enroll.verifying") : t("enroll.verifyContinue")}
            </Button>
            <button
              type="button"
              onClick={() => setStage(backStage)}
              className="text-center text-sm text-[var(--color-accent)] hover:underline"
            >
              {t("enroll.back")}
            </button>
          </form>
        )}

        {stage === "email_otp" && (
          <form onSubmit={onVerifyEmailOtp} className="flex flex-col gap-4">
            <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
              {t("enroll.emailTitle")}
            </h1>
            <p className="text-sm text-[var(--color-text-secondary)]">
              {emailOtpSent ? t("enroll.emailSent") : t("enroll.emailSending")}
            </p>
            <div className="flex flex-col gap-1">
              <label
                htmlFor="email-otp-code"
                className="text-sm text-[var(--color-text-secondary)]"
              >
                {t("enroll.code6")}
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
              {loading ? t("enroll.verifying") : t("enroll.verifyContinue")}
            </Button>
            <button
              type="button"
              onClick={() => setStage(backStage)}
              className="text-center text-sm text-[var(--color-accent)] hover:underline"
            >
              {t("enroll.back")}
            </button>
          </form>
        )}

        {stage === "passkey" && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <p className="text-sm text-[var(--color-text-secondary)]">
              {t("enroll.passkeyPrompt")}
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
                  {t("enroll.back")}
                </button>
              </>
            )}
          </div>
        )}

        {stage === "recovery" && recoveryCodes && (
          <div className="flex flex-col gap-4">
            <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
              {t("enroll.recoveryTitle")}
            </h1>
            <p className="text-sm text-[var(--color-text-secondary)]">
              {t("enroll.recoveryIntro")}
            </p>
            <div className="grid grid-cols-2 gap-2 rounded-md border border-[var(--color-bg-border)] bg-[var(--color-bg-elevated)] p-4 font-mono text-sm text-[var(--color-text-primary)]">
              {recoveryCodes.map((c) => (
                <span key={c}>{c}</span>
              ))}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button variant="secondary" className="w-full" onClick={() => void copyCodes(recoveryCodes)}>
                {copied ? t("enroll.copied") : t("enroll.copyCodes")}
              </Button>
              <Button variant="secondary" className="w-full" onClick={() => downloadCodes(recoveryCodes)}>
                {t("enroll.downloadCodes")}
              </Button>
            </div>
            <Button className="w-full" onClick={() => navigate("/onboarding", { replace: true })}>
              {t("enroll.saved")}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
