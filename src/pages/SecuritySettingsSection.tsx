import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { startRegistration } from "@simplewebauthn/browser";
import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, Input } from "@foroba/ui";
import {
  deleteAccount,
  enrollTotp,
  fetchConsents,
  fetchMfaMethods,
  passkeyRegisterOptions,
  passkeyRegisterVerify,
  regenerateRecoveryCodes,
  removeMfaMethod,
  sendEmailOtp,
  verifyEmailOtp,
  verifyTotp,
} from "../auth/api";

const DELETE_CONFIRM_PHRASE = "DELETE";

const CONSENT_LABELS: Record<string, string> = {
  terms_of_service: "Terms of Service",
  privacy_policy: "Privacy Policy",
};

type MethodKey = "totp" | "email_otp" | "webauthn";

const METHOD_ROWS: { key: MethodKey; label: string }[] = [
  { key: "totp", label: "Authenticator app" },
  { key: "email_otp", label: "Email code" },
  { key: "webauthn", label: "Passkey" },
];

export function SecuritySettingsSection() {
  const qc = useQueryClient();
  const { data: mfa } = useQuery({ queryKey: ["mfa-methods"], queryFn: fetchMfaMethods });
  const { data: consents } = useQuery({ queryKey: ["consents"], queryFn: fetchConsents });
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [newRecoveryCodes, setNewRecoveryCodes] = useState<string[] | null>(null);
  // Which not-yet-enrolled method the user is currently adding, plus its inline setup state.
  const [addingMethod, setAddingMethod] = useState<MethodKey | null>(null);
  const [addCode, setAddCode] = useState("");
  const [totpQr, setTotpQr] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  if (!mfa) return null;

  const enabledCount = [mfa.totp_enabled, mfa.email_otp_enabled, mfa.webauthn_enabled].filter(
    Boolean,
  ).length;

  async function handleRemove(method: MethodKey) {
    setSavingKey(method);
    setMfaError(null);
    try {
      await removeMfaMethod(method);
      await qc.invalidateQueries({ queryKey: ["mfa-methods"] });
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Failed to remove method.");
    } finally {
      setSavingKey(null);
    }
  }

  function cancelAdd() {
    setAddingMethod(null);
    setAddCode("");
    setTotpQr(null);
  }

  async function handleStartAdd(method: MethodKey) {
    setMfaError(null);
    setAddCode("");
    setAddingMethod(method);
    try {
      if (method === "totp") {
        const { qr } = await enrollTotp();
        setTotpQr(qr);
      } else if (method === "email_otp") {
        await sendEmailOtp();
      } else {
        const options = await passkeyRegisterOptions();
        const attestation = await startRegistration({ optionsJSON: options });
        await passkeyRegisterVerify(JSON.stringify(attestation), "Passkey");
        await qc.invalidateQueries({ queryKey: ["mfa-methods"] });
        cancelAdd();
      }
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Failed to start setup.");
      cancelAdd();
    }
  }

  async function handleVerifyAdd() {
    if (!addingMethod || addingMethod === "webauthn") return;
    setSavingKey(addingMethod);
    setMfaError(null);
    try {
      if (addingMethod === "totp") {
        await verifyTotp(addCode);
      } else {
        await verifyEmailOtp(addCode);
      }
      await qc.invalidateQueries({ queryKey: ["mfa-methods"] });
      cancelAdd();
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Invalid code.");
    } finally {
      setSavingKey(null);
    }
  }

  async function handleRegenerate() {
    setSavingKey("recovery");
    setMfaError(null);
    try {
      const codes = await regenerateRecoveryCodes();
      setNewRecoveryCodes(codes);
      await qc.invalidateQueries({ queryKey: ["mfa-methods"] });
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Failed to regenerate codes.");
    } finally {
      setSavingKey(null);
    }
  }

  function closeDeleteDialog() {
    setDeleteDialogOpen(false);
    setDeletePassword("");
    setDeleteConfirmText("");
    setDeleteError(null);
  }

  async function handleDeleteAccount() {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteAccount(deletePassword);
      window.location.href = "/login";
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete account.");
      setDeleting(false);
    }
  }

  return (
    <>
      <h2 className="mt-3 px-0.5 text-xs font-bold uppercase tracking-wide text-[var(--color-text-secondary)]">
        Security
      </h2>

      {METHOD_ROWS.map(({ key, label }) => {
        const enabled = mfa[`${key}_enabled` as const];
        if (!enabled) {
          return (
            <div
              key={key}
              className="flex flex-col gap-3 rounded-lg border border-[var(--color-bg-border)] bg-[var(--color-bg-surface)] px-4.5 py-3.5"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-[var(--color-text-primary)]">
                  {label} — Not set up
                </span>
                {addingMethod !== key && (
                  <button
                    type="button"
                    aria-label={`Add ${label}`}
                    disabled={savingKey !== null}
                    onClick={() => handleStartAdd(key)}
                    className="text-xs font-semibold text-[var(--color-accent)] disabled:cursor-not-allowed"
                  >
                    Add
                  </button>
                )}
              </div>
              {addingMethod === key && key !== "webauthn" && (
                <div className="flex flex-col gap-2">
                  {key === "totp" && totpQr && (
                    <img src={totpQr} alt="TOTP QR code" className="mx-auto h-32 w-32" />
                  )}
                  {key === "email_otp" && (
                    <p className="text-xs text-[var(--color-text-secondary)]">
                      We sent a 6-digit code to your email.
                    </p>
                  )}
                  <Input
                    value={addCode}
                    onChange={(e) => setAddCode(e.target.value)}
                    placeholder="6-digit code"
                  />
                  <div className="flex gap-2">
                    <Button
                      onClick={handleVerifyAdd}
                      disabled={savingKey === key || addCode.length === 0}
                    >
                      Verify
                    </Button>
                    <button
                      type="button"
                      onClick={cancelAdd}
                      className="text-xs font-semibold text-[var(--color-text-secondary)]"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        }
        return (
          <div
            key={key}
            className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-bg-border)] bg-[var(--color-bg-surface)] px-4.5 py-3.5"
          >
            <span className="text-sm text-[var(--color-text-primary)]">{label} — Enabled</span>
            <button
              type="button"
              aria-label={`Remove ${label}`}
              disabled={savingKey === key || enabledCount <= 1}
              onClick={() => handleRemove(key)}
              className="text-xs font-semibold text-[var(--color-negative)] disabled:cursor-not-allowed disabled:text-[var(--color-text-secondary)]"
            >
              Remove
            </button>
          </div>
        );
      })}

      <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-bg-border)] bg-[var(--color-bg-surface)] px-4.5 py-3.5">
        <span className="text-sm text-[var(--color-text-primary)]">
          Recovery codes — {mfa.recovery_codes_remaining} remaining
        </span>
        <button
          type="button"
          disabled={savingKey === "recovery"}
          onClick={handleRegenerate}
          className="text-xs font-semibold text-[var(--color-accent)] disabled:cursor-not-allowed"
        >
          Regenerate
        </button>
      </div>

      {newRecoveryCodes && (
        <div className="grid grid-cols-2 gap-1.5 rounded-lg border border-[var(--color-bg-border)] bg-[var(--color-bg-surface)] px-4.5 py-3.5 font-mono text-sm text-[var(--color-text-primary)]">
          {newRecoveryCodes.map((c) => (
            <span key={c}>{c}</span>
          ))}
        </div>
      )}

      {consents && consents.length > 0 && (
        <>
          <h2 className="mt-3 px-0.5 text-xs font-bold uppercase tracking-wide text-[var(--color-text-secondary)]">
            Legal
          </h2>
          {consents.map((c) => (
            <div
              key={c.document_type}
              className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-bg-border)] bg-[var(--color-bg-surface)] px-4.5 py-3.5"
            >
              <span className="text-sm text-[var(--color-text-primary)]">
                {CONSENT_LABELS[c.document_type] ?? c.document_type}
              </span>
              <span className="text-xs text-[var(--color-text-secondary)]">
                Accepted v{c.document_version} on{" "}
                {new Date(c.accepted_at.replace(" ", "T") + "Z").toLocaleDateString()}
              </span>
            </div>
          ))}
        </>
      )}

      {mfaError && (
        <p role="alert" className="m-0.5 text-xs text-[var(--color-negative)]">
          {mfaError}
        </p>
      )}

      <h2 className="mt-3 px-0.5 text-xs font-bold uppercase tracking-wide text-[var(--color-negative)]">
        Danger zone
      </h2>
      <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-negative)] bg-[var(--color-bg-surface)] px-4.5 py-3.5">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-[var(--color-text-primary)]">
            Delete my account
          </span>
          <span className="text-xs text-[var(--color-text-secondary)]">
            Permanently erases your data across the whole suite. This cannot be undone.
          </span>
        </div>
        <Button
          variant="destructive"
          onClick={() => setDeleteDialogOpen(true)}
        >
          Delete account
        </Button>
      </div>

      <Dialog open={deleteDialogOpen} onOpenChange={(open) => (open ? setDeleteDialogOpen(true) : closeDeleteDialog())}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete your account</DialogTitle>
            <DialogDescription>
              This permanently erases your data in Foroba, Pazuru, and Tsumi — accounts,
              transactions, portfolio, budgets, goals, and everything else tied to your
              account. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-xs text-[var(--color-text-secondary)]">
              Confirm your password
              <Input
                type="password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-[var(--color-text-secondary)]">
              Type {DELETE_CONFIRM_PHRASE} to confirm
              <Input
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
              />
            </label>
            {deleteError && (
              <p role="alert" className="text-xs text-[var(--color-negative)]">
                {deleteError}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={closeDeleteDialog}
                className="text-xs font-semibold text-[var(--color-text-secondary)]"
              >
                Cancel
              </button>
              <Button
                variant="destructive"
                disabled={
                  deleting ||
                  deletePassword.length === 0 ||
                  deleteConfirmText !== DELETE_CONFIRM_PHRASE
                }
                onClick={handleDeleteAccount}
              >
                {deleting ? "Deleting…" : "Delete account"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
