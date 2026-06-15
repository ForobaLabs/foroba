# App Completeness Requirements — every Foroba surface must have these

> These are the "real product" pieces that a serious webapp/mobile app needs and that the
> current apps are missing. They are delivered as reusable scaffolding in `@foroba/ui` (SP1)
> and wired into each app (Pazuru, Tsumi, Foroba). Each item below becomes GitLab issues.
> All copy is i18n (EN/FR/IT). All pages work in light/dark and are WCAG 2.2 AA.

## 1. Settings (every app)
- **Profile**: name, avatar, household role (single / family member / child guardian), language,
  base currency, date/number format, expert↔novice finance level (feeds Jeli & gamification).
- **Appearance**: theme = system / light / dark; density; reduce-motion.
- **Language**: EN / FR / IT switcher.
- **Jeli (AI)**: personality slider (analytical ↔ friendly), verbosity, model name (from `.env`),
  enable/disable, "Jeli runs 100% locally" notice.
- **Connections**: bank connectors (Pazuru: Enable Banking), broker/exchange (Tsumi: DeGiro,
  Binance, Boursorama), connection health/status, add/remove, last refresh.
- **Privacy & Data**: local-first explanation; optional E2E sync toggle (future); **export my data**
  (JSON/CSV); **delete all my data** (local wipe) with confirm; no-tracking statement.
- **Notifications / reminders** (e.g., tax deadlines, budget thresholds) — local only.
- **Households** (SP5): members list, invite via secure link, roles/permissions, children accounts.

## 2. Legal & compliance (every app — required for stores & GDPR)
- **Privacy Policy** (local-first, data minimization, what the server can/can't see).
- **Terms of Service / EULA**.
- **Cookie / tracking statement** (state: no third-party tracking).
- **Fiscal disclaimer** (Tsumi & any tax output): "indicative estimate, not tax advice —
  verify with a commercialista / expert-comptable." (already mandated for Tsumi).
- **Open-source licenses / credits** (auto-generated attributions page).
- **Imprint / company info** (placeholder until the startup entity exists).
- **Data Processing & Security overview** (encryption, local storage, read-only connectors).
- Versioned legal docs with "last updated" date; acceptance tracked at onboarding.

## 3. Help & support (every app)
- **Onboarding / first-run**: discreet profiling (single vs family, finance level), connect first
  source, privacy explainer. Skippable, resumable.
- **Help Center / FAQ** (i18n, searchable).
- **Guided tours / tooltips** for key screens (dismissible).
- **Financial education** entry point (SP6): glossary, "learn" cards, contextual explainers
  (e.g., what is TER, PEA, drawdown, IVAFE) — Jeli-assisted.
- **Contact / support**: contact form or mailto, feedback link, GitLab issues link (for now),
  diagnostics export (no sensitive data) to attach to reports.
- **About**: version, build, changelog/release notes, links to legal, brand story (Foroba/Pazuru/
  Tsumi/Jeli meanings).

## 4. User profile & account
- Profile view/edit (see Settings).
- Household membership & roles (SP5).
- Per-person vs household data scoping.
- Account security: local app lock (PIN/biometric on mobile), session handling for cloud mode.

## 5. Mobile-app readiness (future, design now)
- App icons, splash screens, adaptive icons (iOS/Android), maskable PWA icons.
- Store metadata: name, subtitle, description (i18n), keywords, screenshots, privacy nutrition
  labels (Apple) / Data Safety (Google) — consistent with local-first claims.
- Deep links / universal links; offline-first behavior; safe-area / notch handling; haptics.
- Push/local notifications (reminders) — local where possible.
- Responsive layouts from day 1 (the shared design system is mobile-aware).

## 6. Quality baseline (every screen)
- Empty / loading / error states.
- Graceful "service unavailable" when Pazuru/Tsumi API is down (no crash).
- Keyboard navigation, focus rings, ARIA, color-contrast (WCAG 2.2 AA).
- i18n complete (no hardcoded UI strings).
- Light/dark parity.

## 7. Footer (web)
Links: Privacy · Terms · Help · About · Language · Theme · "Local-first, your data stays yours".
