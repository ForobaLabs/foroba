import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  Input,
  PasswordInput,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@foroba/ui";
import { register } from "../auth/api";
import { loadIntent, parseIntent, saveIntent } from "../lib/signupIntent";

const COUNTRY_CODES = ["IT", "FR", "DE", "ES", "NL", "BE", "GB", "US"];

type Strength = { score: 0 | 1 | 2 | 3 | 4; color: string };

function evaluatePasswordStrength(password: string): Strength {
  if (!password) return { score: 0, color: "" };
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  const clamped = Math.min(score, 4) as 0 | 1 | 2 | 3 | 4;
  const colors = ["var(--color-negative)", "var(--color-negative)", "var(--color-warning)", "var(--color-positive)", "var(--color-positive)"];
  return { score: clamped, color: colors[clamped] };
}

export function RegisterPage() {
  const { t, i18n } = useTranslation();
  const countries = useMemo(() => {
    const names = new Intl.DisplayNames(i18n.language, { type: "region" });
    return COUNTRY_CODES.map((code) => ({ code, label: names.of(code) ?? code }));
  }, [i18n.language]);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const intent = useMemo(() => {
    const fromUrl = parseIntent(window.location.search);
    if (fromUrl) saveIntent(fromUrl);
    return fromUrl ?? loadIntent();
  }, []);
  const [email, setEmail] = useState("");
  const [emailConfirm, setEmailConfirm] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [birthYear, setBirthYear] = useState("");
  const [country, setCountry] = useState("");
  const [tosAccepted, setTosAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const strength = useMemo(() => evaluatePasswordStrength(password), [password]);
  const emailsMatch = emailConfirm.length === 0 || email.toLowerCase() === emailConfirm.toLowerCase();
  const passwordsMatch = passwordConfirm.length === 0 || password === passwordConfirm;

  const canSubmit =
    email.length > 0 &&
    emailConfirm.length > 0 &&
    email.toLowerCase() === emailConfirm.toLowerCase() &&
    name.length > 0 &&
    password.length >= 8 &&
    password === passwordConfirm &&
    tosAccepted;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!canSubmit) return;
    setLoading(true);
    try {
      await register({
        email,
        emailConfirm,
        name,
        password,
        passwordConfirm,
        tosAccepted,
        birthYear: birthYear ? Number(birthYear) : undefined,
        country: country || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["session"] });
      navigate("/enroll", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("register.errFailed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-primary)] p-4">
      <Card className="w-full max-w-sm p-6">
        <h1 className="mb-1 text-xl font-semibold text-[var(--color-text-primary)]">
          {t("register.title")}
        </h1>
        <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
          {t("register.intro")}
        </p>
        {intent && (
          <p role="note" className="mb-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-3 text-sm text-[var(--color-text-secondary)]">
            {t("register.intent", { app: intent.app.charAt(0).toUpperCase() + intent.app.slice(1) })}
            {intent.plan !== "free" && <> {t("register.intentPremium")}</>}
          </p>
        )}
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="name" className="text-sm text-[var(--color-text-secondary)]">
              {t("register.name")}
            </label>
            <Input
              id="name"
              type="text"
              autoComplete="name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="email" className="text-sm text-[var(--color-text-secondary)]">
              {t("register.email")}
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
            <label htmlFor="email-confirm" className="text-sm text-[var(--color-text-secondary)]">
              {t("register.emailConfirm")}
            </label>
            <Input
              id="email-confirm"
              type="email"
              autoComplete="email"
              spellCheck={false}
              required
              value={emailConfirm}
              onChange={(e) => setEmailConfirm(e.target.value)}
              error={!emailsMatch ? t("register.emailMismatch") : undefined}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="password" className="text-sm text-[var(--color-text-secondary)]">
              {t("register.password")}
            </label>
            <PasswordInput showLabel={t("login.showPassword")} hideLabel={t("login.hidePassword")}
              id="password"
              autoComplete="new-password"
              minLength={12}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              helper={t("register.passwordHelper")}
            />
            {password.length > 0 && (
              <div className="mt-1">
                <div className="flex h-1.5 gap-1">
                  {[0, 1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="flex-1 rounded-full"
                      style={{
                        backgroundColor:
                          i < strength.score ? strength.color : "var(--color-bg-border)",
                      }}
                    />
                  ))}
                </div>
                <p className="mt-1 text-xs" style={{ color: strength.color }}>
                  {t(`register.strength.${strength.score}`)}
                </p>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="password-confirm" className="text-sm text-[var(--color-text-secondary)]">
              {t("register.passwordConfirm")}
            </label>
            <PasswordInput showLabel={t("login.showPassword")} hideLabel={t("login.hidePassword")}
              id="password-confirm"
              autoComplete="new-password"
              required
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              error={!passwordsMatch ? t("register.passwordMismatch") : undefined}
            />
          </div>

          <div className="border-t border-[var(--color-bg-border)] pt-4">
            <p className="mb-3 text-xs text-[var(--color-text-muted)]">
              {t("register.optional")}
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <label htmlFor="birth-year" className="text-sm text-[var(--color-text-secondary)]">
                  {t("register.birthYear")}
                </label>
                <Input
                  id="birth-year"
                  type="number"
                  inputMode="numeric"
                  placeholder={t("register.birthYearPlaceholder")}
                  value={birthYear}
                  onChange={(e) => setBirthYear(e.target.value)}
                  min={1900}
                  max={2100}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm text-[var(--color-text-secondary)]">{t("register.country")}</label>
                <Select value={country} onValueChange={setCountry}>
                  <SelectTrigger>
                    <SelectValue placeholder={t("register.countryPlaceholder")} />
                  </SelectTrigger>
                  <SelectContent>
                    {countries.map((c) => (
                      <SelectItem key={c.code} value={c.code}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <label className="flex min-h-11 items-start gap-2 py-1 text-sm text-[var(--color-text-secondary)]">
            <input
              type="checkbox"
              checked={tosAccepted}
              onChange={(e) => setTosAccepted(e.target.checked)}
              className="mt-0.5 h-5 w-5 shrink-0"
            />
            <span>
              {t("register.tosPrefix")}{" "}
              <a href="/legal" className="text-[var(--color-accent)] hover:underline">
                {t("register.tos")}
              </a>{" "}
              {t("register.and")}{" "}
              <a href="/legal" className="text-[var(--color-accent)] hover:underline">
                {t("register.privacy")}
              </a>
              .
            </span>
          </label>

          {error && (
            <p role="alert" className="text-sm text-[var(--color-negative)]">
              {error}
            </p>
          )}
          <Button type="submit" disabled={loading || !canSubmit} className="w-full">
            {loading ? t("register.submitting") : t("register.submit")}
          </Button>
          <p className="text-center text-sm text-[var(--color-text-secondary)]">
            {t("register.haveAccount")}{" "}
            <a href="/login" className="text-[var(--color-accent)] hover:underline">
              {t("register.signIn")}
            </a>
          </p>
        </form>
      </Card>
    </div>
  );
}
