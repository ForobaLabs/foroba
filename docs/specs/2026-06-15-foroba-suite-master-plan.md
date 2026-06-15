# Foroba Suite — Master Plan (Design)

> Status: Approved (2026-06-15). Author: brainstorming session (Opus).
> This document is the umbrella design for the whole suite. Each sub-project (SP)
> gets its own spec + implementation plan before any code is written.
> Execution model: this and the SP specs are written with Opus; a Sonnet session
> then EXECUTES them (see `superpowers:executing-plans`).

---

## 1. Vision

**Foroba** (fòroba = "common field / common wealth" in Bambara) is the umbrella
brand for a suite of **local-first, privacy-first personal-finance apps**, built to
eventually become a startup product (web now, native iOS/Android/macOS later, optional
cloud deployment).

Three product surfaces + one shared design system:

| Repo (GitLab `bambac961/...`) | Role | Stack |
|---|---|---|
| `foroba-ui` (`@foroba/ui`) | Shared design system (versioned npm package) | TypeScript, Tailwind v4, shadcn/ui, i18n |
| `pazuru` *(exists)* | Bank-account aggregation & cashflow | React 19 + Vite + TS + FastAPI + SQLite + Ollama |
| `tsumi` *(rename of `pfh_finance_asset_dashboard`)* | ETF + crypto portfolio | FastAPI + DuckDB; UI migrating Dash → React |
| `foroba` *(new)* | Superapp shell: unified net worth + Jeli + onboarding | React 19 + Vite + TS |

Foroba does not reimplement Pazuru/Tsumi logic — it **consumes their REST APIs** and adds
a unified net worth, cross-domain AI (Jeli), onboarding and household management.

---

## 2. Locked decisions (do not relitigate without an ADR)

1. **Stack convergence — React/TypeScript everywhere.** Tsumi's Plotly Dash UI is
   progressively rewritten in React on `@foroba/ui`. Python backends (FastAPI + DuckDB/SQLite)
   remain as data sources. One base → shared components → clean path to mobile/macOS.
2. **Brand — Foroba is a NEW umbrella brand** with a new modern shared palette (light + dark).
   Pazuru and Tsumi adopt it, each keeping one distinctive accent color.
3. **Data model — multi-person (household) from day 1.** Entities: `household`, `member`,
   optional `child`. A single user = household of 1. Onboarding asks the profile discreetly.
   The *schema* is designed now (SP1/SP2); family *features* ship in SP5. No painful migrations.
4. **Privacy — local-first + OPTIONAL end-to-end-encrypted sync** for family/multi-device.
   Default 100% local. The server can NEVER read plaintext financial data. No financial data
   in `localStorage` (in-memory or via API only).
5. **Cloud-ready from day 1.** Same codebase runs locally OR on a server via config only
   (`local SQLite/DuckDB` ↔ `managed DB` swappable). Containerized, stateless-friendly services.
   Server stores ONLY the minimum to function (auth, encrypted sync blobs, operational metadata)
   — *data minimization*.
6. **i18n — EN / FR / IT** everywhere, with a language switcher in Settings.
7. **Jeli** (griot, "the one with the gift of speech") = the single unified local LLM assistant
   across both domains (replaces per-app chatbots). Runs on Ollama (`qwen3.5:9b` +
   `mxbai-embed-large`), reusing Pazuru's LangChain + ChromaDB. **Personality configurable in
   Settings**: analytical ↔ friendly, and adapts to finance-expert ↔ novice. No external LLM, ever.
8. **Gamification — serious.** Money is serious; jokes allowed, **emoji minimal**. Tied to real
   behavior (savings, budget adherence, goals), never vanity metrics. Paired with financial education.

---

## 3. Cross-cutting principles (apply to every sub-project)

- **GitLab-tracked, no black box.** Every sub-project = a Milestone; every task = an Issue;
  every architectural decision = an ADR in the Wiki; every merge = an MR closing its Issues.
  Mirror the workflow already used by Tsumi (see `docs/superpowers/specs/2026-06-15-gitlab-tracking-workflow.md`).
- **Conventional commits** linked to issues (`feat(ui): ... — closes #N`).
- **TypeScript strict** (no `any`); **Python type-hinted + Ruff/black clean**.
- **Definition of Done** per app (lint + test green, i18n complete, light/dark works,
  empty/loading/error states, a11y pass, docs/wiki updated, issue closed).
- **Accessibility (WCAG 2.2 AA)** as a baseline, not an afterthought (keyboard nav, contrast,
  ARIA, focus management) — also prepares mobile.
- **App completeness** (every surface must have it): see
  `docs/superpowers/specs/2026-06-15-app-completeness-requirements.md`.

---

## 4. Sub-projects

Ordered by dependency. Each gets its own `YYYY-MM-DD-spec.md` + implementation plan when reached.

### SP0 — Cleanup & Rename to Tsumi  *(spec written: `2026-06-15-sp0-rename-tsumi-spec.md`)*
Delete duplicate `etf-dashboard` (after explicit confirm); rename folder + code + docs + DB
file + badges `pfh_finance_asset_dashboard` → `tsumi`; rename the GitLab project & path; update
remotes/links; keep lint + tests green. Foundational hygiene before anything else.

### SP1 — Foundation: `@foroba/ui` design system
New repo `foroba-ui`. Deliver the new modern palette (light/dark), design tokens, typography,
i18n base (EN/FR/IT), reusable shadcn components, chart theme, Jeli/insight cards, and the
scaffolding for the "real app" pages (Settings, Legal, Help, Profile, footer). Publish to the
GitLab Package Registry. **This is the startup-ready core.**

### SP2 — Foroba shell + Net Worth Dashboard
New repo `foroba`. React app consuming Pazuru + Tsumi APIs; unified net worth & allocation;
navigation; theme + language switch; the app-completeness pages mounted from `@foroba/ui`.
Graceful "service unavailable" states. This is where `docs/superpowers/specs/` get git-committed.

### SP3 — Pazuru & Tsumi adopt `@foroba/ui`
Pazuru: re-skin onto shared tokens (keep an accent) + add i18n EN/FR/IT.
Tsumi: migrate UI from Dash → React on the shared base, **page by page** (largest effort,
fully splittable into issues per page). Backend untouched.

### SP4 — Jeli (unified local LLM assistant)
One cross-domain assistant (Pazuru transactions + Tsumi positions) on Ollama; personality config
in Settings; replaces per-app chatbots; reuses LangChain + ChromaDB. Cross-domain context
("how much can I invest this month given my spending?").

### SP5 — Profiles & Household (single / family) + onboarding
Implement the household data model + member/children linking via secure invite; discreet
onboarding profiling (single vs family, expert vs novice — also feeds Jeli & gamification);
permissions and per-person vs household views.

### SP6 — Serious gamification + financial education
Behavior-based goals/streaks/milestones (savings, budget adherence), education content/tips,
Jeli-driven nudges. No childish badges; tasteful, money-serious.

### Future (ideas only, not scheduled)
Native iOS/Android (React Native or Capacitor reusing `@foroba/ui` tokens), macOS App Store app,
production E2E-encrypted sync + cloud deploy, go-to-market.

---

## 5. Dependency graph

```
SP0  →  SP1  →  SP2  →  SP3
                 │
                 ├──→  SP4 (needs SP2 + Pazuru AI)
                 ├──→  SP5 (schema designed in SP1/SP2; features here)
                 └──→  SP6 (needs SP1, SP2, SP5)
Cross-cutting (cloud-ready, E2E, a11y, GitLab tracking): applied from SP0 onward.
```

---

## 6. Brand & design direction (for SP1)

- **Umbrella identity:** Foroba = "common wealth / common field". Warm-but-serious, modern,
  fintech-grade. Light AND dark must both feel first-class (system-adaptive + manual override).
- **Per-app accents:** Pazuru keeps an indigo lineage; Tsumi a market/finance accent; Foroba a
  neutral premium base that hosts both. Exact palette decided in the SP1 spec (with token names).
- **Naming heritage:** Pazuru (パズル, puzzle), Tsumi (積み, "stacking/accumulation"), Jeli (griot).
  Wordmarks may show the original script subtly; primary UI text follows the selected language.
- **Tone:** data first, advice after. Jeli can praise/warn like a griot but stays useful and
  non-patronizing; tone slider in Settings governs how warm vs analytical it is.

---

## 7. Open items to resolve inside individual SP specs
- Exact shared palette + token names (SP1).
- Tsumi Dash→React migration order, page by page (SP3).
- Net worth aggregation contract / API gaps in Pazuru & Tsumi (SP2).
- Household schema details + invite/permission model (SP5).
- E2E sync protocol choice (future), kept out of MVP but not architecturally blocked.
