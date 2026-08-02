import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@foroba/ui";
import { register } from "../auth/api";

const COUNTRIES: { code: string; label: string }[] = [
  { code: "IT", label: "Italy" },
  { code: "FR", label: "France" },
  { code: "DE", label: "Germany" },
  { code: "ES", label: "Spain" },
  { code: "NL", label: "Netherlands" },
  { code: "BE", label: "Belgium" },
  { code: "GB", label: "United Kingdom" },
  { code: "US", label: "United States" },
];

type Strength = { score: 0 | 1 | 2 | 3 | 4; label: string; color: string };

function evaluatePasswordStrength(password: string): Strength {
  if (!password) return { score: 0, label: "", color: "" };
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  const clamped = Math.min(score, 4) as 0 | 1 | 2 | 3 | 4;
  const levels: Record<number, { label: string; color: string }> = {
    0: { label: "Too weak", color: "var(--color-negative)" },
    1: { label: "Weak", color: "var(--color-negative)" },
    2: { label: "Fair", color: "var(--color-warning)" },
    3: { label: "Good", color: "var(--color-positive)" },
    4: { label: "Strong", color: "var(--color-positive)" },
  };
  return { score: clamped, ...levels[clamped] };
}

export function RegisterPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [emailConfirm, setEmailConfirm] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [birthYear, setBirthYear] = useState("");
  const [country, setCountry] = useState("");
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
    password === passwordConfirm;

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
        birthYear: birthYear ? Number(birthYear) : undefined,
        country: country || undefined,
      });
      await qc.invalidateQueries({ queryKey: ["session"] });
      navigate("/enroll", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-primary)] p-4">
      <Card className="w-full max-w-sm p-6">
        <h1 className="mb-1 text-xl font-semibold text-[var(--color-text-primary)]">
          Create your account
        </h1>
        <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
          Everything starts empty — you'll connect your own bank and investments next.
        </p>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="name" className="text-sm text-[var(--color-text-secondary)]">
              Full name
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
            <label htmlFor="email-confirm" className="text-sm text-[var(--color-text-secondary)]">
              Confirm email
            </label>
            <Input
              id="email-confirm"
              type="email"
              autoComplete="email"
              spellCheck={false}
              required
              value={emailConfirm}
              onChange={(e) => setEmailConfirm(e.target.value)}
              error={!emailsMatch ? "Emails do not match" : undefined}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="password" className="text-sm text-[var(--color-text-secondary)]">
              Password (min 8 chars)
            </label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              helper="Mix upper/lower case, numbers, and symbols for a stronger password."
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
                  {strength.label}
                </p>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="password-confirm" className="text-sm text-[var(--color-text-secondary)]">
              Confirm password
            </label>
            <Input
              id="password-confirm"
              type="password"
              autoComplete="new-password"
              required
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              error={!passwordsMatch ? "Passwords do not match" : undefined}
            />
          </div>

          <div className="border-t border-[var(--color-bg-border)] pt-4">
            <p className="mb-3 text-xs text-[var(--color-text-muted)]">
              Optional — you can skip these.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <label htmlFor="birth-year" className="text-sm text-[var(--color-text-secondary)]">
                  Year of birth
                </label>
                <Input
                  id="birth-year"
                  type="number"
                  inputMode="numeric"
                  placeholder="e.g. 1990"
                  value={birthYear}
                  onChange={(e) => setBirthYear(e.target.value)}
                  min={1900}
                  max={2100}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm text-[var(--color-text-secondary)]">Country</label>
                <Select value={country} onValueChange={setCountry}>
                  <SelectTrigger>
                    <SelectValue placeholder="Prefer not to say" />
                  </SelectTrigger>
                  <SelectContent>
                    {COUNTRIES.map((c) => (
                      <SelectItem key={c.code} value={c.code}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {error && (
            <p role="alert" className="text-sm text-[var(--color-negative)]">
              {error}
            </p>
          )}
          <Button type="submit" disabled={loading || !canSubmit} className="w-full">
            {loading ? "Creating account…" : "Create account"}
          </Button>
          <p className="text-center text-sm text-[var(--color-text-secondary)]">
            Already have an account?{" "}
            <a href="/login" className="text-[var(--color-accent)] hover:underline">
              Sign in
            </a>
          </p>
        </form>
      </Card>
    </div>
  );
}
