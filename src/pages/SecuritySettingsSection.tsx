import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { startRegistration } from "@simplewebauthn/browser";
import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, Input } from "@foroba/ui";
import {
  changePassword,
  deleteAccount,
  enrollTotp,
  fetchConsents,
  fetchMfaMethods,
  fetchSessions,
  passkeyRegisterOptions,
  passkeyRegisterVerify,
  regenerateRecoveryCodes,
  removeMfaMethod,
  revokeSession,
  sendEmailOtp,
  verifyEmailOtp,
  verifyTotp,
} from "../auth/api";

const DELETE_CONFIRM_PHRASE = "DELETE";

// startRegistration()'s underlying navigator.credentials.create() promise
// never settles on its own in a headless/no-authenticator environment (the
// @simplewebauthn/browser public API doesn't accept an AbortSignal to cancel
// it), so it's raced against this bound instead (FOR-D09).
const WEBAUTHN_TIMEOUT_MS = 60_000;

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
  const { data: sessions, refetch: refetchSessions } = useQuery({
    queryKey: ["sessions"],
    queryFn: fetchSessions,
  });
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [newRecoveryCodes, setNewRecoveryCodes] = useState<string[] | null>(null);
  // Which not-yet-enrolled method the user is currently adding, plus its inline setup state.
  const [addingMethod, setAddingMethod] = useState<MethodKey | null>(null);
  const [addCode, setAddCode] = useState("");
  const [totpQr, setTotpQr] = useState<string | null>(null);
  // Bumped on every handleStartAdd/cancelAdd call so a startRegistration()
  // promise that resolves/rejects after the user has already cancelled (or
  // started a different method) is recognized as stale and ignored.
  const addRequestId = useRef(0);
  // Change password
  const [changePwOpen, setChangePwOpen] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [newPwConfirm, setNewPwConfirm] = useState("");
  const [changePwError, setChangePwError] = useState<string | null>(null);
  const [changingPw, setChangingPw] = useState(false);
  // Active devices
  const [revokingSession, setRevokingSession] = useState<number | null>(null);
  // Delete account
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
    addRequestId.current += 1;
    setAddingMethod(null);
    setAddCode("");
    setTotpQr(null);
  }

  async function handleStartAdd(method: MethodKey) {
    setMfaError(null);
    setAddCode("");
    setAddingMethod(method);
    const requestId = (addRequestId.current += 1);
    try {
      if (method === "totp") {
        const { qr } = await enrollTotp();
        setTotpQr(qr);
      } else if (method === "email_otp") {
        await sendEmailOtp();
      } else {
        const options = await passkeyRegisterOptions();
        const attestation = await Promise.race([
          startRegistration({ optionsJSON: options }),
          new Promise<never>((_, reject) => {
            setTimeout(
              () => reject(new Error("Passkey setup timed out. Please try again.")),
              WEBAUTHN_TIMEOUT_MS,
            );
          }),
        ]);
        if (requestId !== addRequestId.current) return; // cancelled/superseded meanwhile
        await passkeyRegisterVerify(JSON.stringify(attestation), "Passkey");
        await qc.invalidateQueries({ queryKey: ["mfa-methods"] });
        cancelAdd();
      }
    } catch (err) {
      if (requestId !== addRequestId.current) return; // cancelled/superseded meanwhile
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

  function closeChangePwDialog() {
    setChangePwOpen(false);
    setCurrentPw("");
    setNewPw("");
    setNewPwConfirm("");
    setChangePwError(null);
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setChangingPw(true);
    setChangePwError(null);
    try {
      await changePassword(currentPw, newPw, newPwConfirm);
      closeChangePwDialog();
    } catch (err) {
      setChangePwError(err instanceof Error ? err.message : "Failed to change password.");
    } finally {
      setChangingPw(false);
    }
  }

  async function handleRevokeSession(sessionId: number) {
    setRevokingSession(sessionId);
    try {
      await revokeSession(sessionId);
      await refetchSessions();
    } finally {
      setRevokingSession(null);
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

      {/* Change password */}
      <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-bg-border)] bg-[var(--color-bg-surface)] px-4.5 py-3.5">
        <span className="text-sm text-[var(--color-text-primary)]">Password</span>
        <button
          type="button"
          onClick={() => setChangePwOpen(true)}
          className="text-xs font-semibold text-[var(--color-accent)]"
        >
          Change
        </button>
      </div>

      <Dialog open={changePwOpen} onOpenChange={(open) => (open ? setChangePwOpen(true) : closeChangePwDialog())}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change password</DialogTitle>
            <DialogDescription>
              Enter your current password and choose a new one. All active mobile sessions
              will be signed out.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleChangePassword} className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-xs text-[var(--color-text-secondary)]">
              Current password
              <Input
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-[var(--color-text-secondary)]">
              New password
              <Input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                autoComplete="new-password"
                required
                minLength={8}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-[var(--color-text-secondary)]">
              Confirm new password
              <Input
                type="password"
                value={newPwConfirm}
                onChange={(e) => setNewPwConfirm(e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>
            {changePwError && (
              <p role="alert" className="text-xs text-[var(--color-negative)]">
                {changePwError}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={closeChangePwDialog}
                className="text-xs font-semibold text-[var(--color-text-secondary)]"
              >
                Cancel
              </button>
              <Button
                type="submit"
                disabled={changingPw || currentPw.length === 0 || newPw.length < 8 || newPwConfirm.length === 0}
              >
                {changingPw ? "Saving…" : "Change password"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

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
                    className="inline-flex min-h-11 min-w-11 items-center justify-center px-2 text-xs font-semibold text-[var(--color-accent)] disabled:cursor-not-allowed"
                  >
                    Add
                  </button>
                )}
              </div>
              {addingMethod === key && key === "webauthn" && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs text-[var(--color-text-secondary)]">
                    Follow your browser or security key's prompt to finish adding a passkey.
                  </p>
                  <button
                    type="button"
                    onClick={cancelAdd}
                    className="self-start text-xs font-semibold text-[var(--color-text-secondary)]"
                  >
                    Cancel
                  </button>
                </div>
              )}
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

      {sessions && sessions.length > 0 && (
        <>
          <h2 className="mt-3 px-0.5 text-xs font-bold uppercase tracking-wide text-[var(--color-text-secondary)]">
            Active devices
          </h2>
          {sessions.map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-bg-border)] bg-[var(--color-bg-surface)] px-4.5 py-3.5"
            >
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="truncate text-sm text-[var(--color-text-primary)]">
                  {s.device_label}
                </span>
                <span className="text-xs text-[var(--color-text-secondary)]">
                  Last active{" "}
                  {s.last_used_at
                    ? new Date(s.last_used_at).toLocaleDateString()
                    : new Date(s.created_at).toLocaleDateString()}
                </span>
              </div>
              <button
                type="button"
                disabled={revokingSession === s.id}
                onClick={() => handleRevokeSession(s.id)}
                className="shrink-0 text-xs font-semibold text-[var(--color-negative)] disabled:cursor-not-allowed disabled:text-[var(--color-text-secondary)]"
              >
                {revokingSession === s.id ? "Revoking…" : "Revoke"}
              </button>
            </div>
          ))}
        </>
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
              This permanently erases your data in Foroba, Naforo, and Yiriba — accounts,
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
