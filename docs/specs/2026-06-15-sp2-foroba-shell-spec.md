# SP2 — Foroba Shell + Net Worth Dashboard

> Status: Approved (2026-06-15).
> Repo to create: `gitlab.com/bambac961/foroba`
> Local folder: `/Users/abdoulaye_bamba/Desktop/Personal_Finance_HUB/foroba/`
> Depends on: SP1 ✅ (@foroba/ui@0.1.0 available)
> Execution: Sonnet session, `superpowers:executing-plans`.

---

## 1. Goals

Build the **Foroba superapp shell** — the React app that:
1. Aggregates Pazuru (bank accounts + cashflow) and Tsumi (ETF + crypto portfolio) via their REST APIs.
2. Shows **unified net worth** (cash + portfolio) on a single dashboard.
3. Provides unified navigation, theme/language switching, onboarding, and the "real webapp" pages
   (Settings, Legal, Help, About) from `@foroba/ui`.
4. Handles "service unavailable" gracefully when Pazuru/Tsumi are offline.
5. Git-commits `docs/superpowers/specs/` (previously untracked) into the `foroba` repo.

Foroba does NOT reimplement Pazuru/Tsumi logic — it consumes their REST APIs.

---

## 2. Repository setup

### 2.1 Create GitLab project
- `POST /api/v4/projects`: `name=foroba`, `path=foroba`, `namespace_id=117751796` (bambac961),
  `visibility=private`, `description="Foroba — unified personal finance superapp shell"`.

### 2.2 Local scaffold
```
mkdir /Users/abdoulaye_bamba/Desktop/Personal_Finance_HUB/foroba
cd foroba
# React 19 + Vite + TypeScript + Tailwind v4
pnpm create vite . --template react-ts
pnpm add @foroba/ui
# (configure .npmrc for registry first)
pnpm add react-router-dom @tanstack/react-query recharts
pnpm add -D tailwindcss@next @tailwindcss/vite
```

### 2.3 .npmrc (for @foroba/ui registry)
```
@foroba:registry=https://gitlab.com/api/v4/projects/83344613/packages/npm/
//gitlab.com/api/v4/projects/83344613/packages/npm/:_authToken=${FOROBA_UI_TOKEN}
```
`FOROBA_UI_TOKEN` = same GitLab PAT (in `.env`, never committed).

### 2.4 Tech stack
| Layer | Choice |
|---|---|
| Framework | React 19 + Vite 6 |
| TypeScript | strict |
| Routing | React Router v7 |
| Data fetching | TanStack Query v5 |
| Design | `@foroba/ui` (tokens, components, layouts, pages) |
| Charts | Recharts + `@foroba/ui/charts` theme |
| State | React Context + TanStack Query (no Redux) |
| i18n | react-i18next + `@foroba/ui/i18n` catalogs |
| Backend | NONE — reads Pazuru API + Tsumi API |
| Tests | Vitest + Testing Library |
| CI | GitLab CI (lint → test → build) |

---

## 3. App structure

```
foroba/
├── .gitlab/
│   └── merge_request_templates/sprint.md
├── .gitlab-ci.yml
├── .env.example           (PAZURU_API_URL, TSUMI_API_URL, FOROBA_UI_TOKEN)
├── .gitignore
├── README.md
├── index.html             (include themeInitScript from @foroba/ui)
├── package.json
├── vite.config.ts         (Tailwind v4 plugin)
├── tsconfig.json
├── vitest.config.ts
└── src/
    ├── main.tsx           (QueryClient, I18nextProvider, RouterProvider)
    ├── App.tsx            (AppShell + RouterOutlet)
    ├── router.tsx         (React Router v7 routes)
    ├── i18n.ts            (react-i18next init with @foroba/ui catalogs)
    ├── api/
    │   ├── pazuru.ts      (fetch wrapper for Pazuru REST API)
    │   ├── tsumi.ts       (fetch wrapper for Tsumi REST API)
    │   └── foroba.ts      (net worth aggregation logic)
    ├── hooks/
    │   ├── useNetWorth.ts (TanStack Query: Pazuru + Tsumi → NetWorthSnapshot)
    │   ├── usePazuruHealth.ts
    │   └── useTsumiHealth.ts
    ├── pages/
    │   ├── DashboardPage.tsx     (net worth, allocation, KpiCards)
    │   ├── AccountsPage.tsx      (redirect to Pazuru UI or embed summary)
    │   ├── PortfolioPage.tsx     (redirect to Tsumi UI or embed summary)
    │   ├── SettingsPage.tsx      (wraps @foroba/ui SettingsPage with app props)
    │   ├── LegalPage.tsx         (wraps @foroba/ui LegalPage)
    │   ├── HelpPage.tsx          (wraps @foroba/ui HelpPage)
    │   ├── AboutPage.tsx         (wraps @foroba/ui AboutPage)
    │   └── OnboardingPage.tsx    (wraps @foroba/ui OnboardingPage)
    ├── components/
    │   ├── NetWorthChart.tsx     (Recharts area chart, useRechartsTheme)
    │   ├── AllocationPie.tsx     (Recharts pie: cash vs portfolio)
    │   ├── ServiceStatusBar.tsx  (shows if Pazuru/Tsumi are unavailable)
    │   └── AppNavItems.tsx       (nav item list for Sidebar)
    └── docs/                    (symlink or copy of superpowers specs)
```

---

## 4. Routes

| Path | Component | Description |
|---|---|---|
| `/` | `DashboardPage` | Net worth + allocation + sparklines |
| `/accounts` | `AccountsPage` | Pazuru cashflow summary |
| `/portfolio` | `PortfolioPage` | Tsumi portfolio summary |
| `/settings` | `SettingsPage` | @foroba/ui SettingsPage |
| `/legal` | `LegalPage` | @foroba/ui LegalPage |
| `/help` | `HelpPage` | @foroba/ui HelpPage |
| `/about` | `AboutPage` | @foroba/ui AboutPage |
| `/onboarding` | `OnboardingPage` | @foroba/ui OnboardingPage (first-run) |

---

## 5. API contracts

### 5.1 Pazuru endpoints consumed
- `GET /api/health` → `{ status: 'ok' | 'error' }`
- `GET /api/accounts/summary` → `{ totalBalance: number, currency: string, accounts: [...] }`
  *(If this endpoint doesn't exist yet, Foroba shows a placeholder with "Pazuru not connected" message.)*

### 5.2 Tsumi endpoints consumed
- `GET /health` → `{ status: 'ok' }`
- `GET /api/portfolio/summary` → `{ totalValueEur: number, positions: [...] }`
  *(If endpoint doesn't exist, show placeholder with graceful degradation.)*

### 5.3 Net worth aggregation (client-side)
```ts
NetWorthSnapshot = {
  date: now(),
  totalEur: pazuruCash + tsumiPortfolio,
  cashEur: pazuruCash,      // 0 if Pazuru unavailable
  portfolioEur: tsumiPortfolio, // 0 if Tsumi unavailable
}
```
Both services are polled every 60 seconds via TanStack Query.

---

## 6. Dashboard UI (DashboardPage)

```
┌─────────────────────────────────────────────────────┐
│  Net Worth  €XX,XXX.XX   ↑ +X.X% today              │
│  ──────────────────────────────────────────────────  │
│  KpiCard: Cash (Pazuru)    KpiCard: Portfolio (Tsumi)│
│  ──────────────────────────────────────────────────  │
│  Area chart: net worth over time (last 30d sparkline)│
│  ──────────────────────────────────────────────────  │
│  Pie: Cash X% / Portfolio X%                         │
│  ──────────────────────────────────────────────────  │
│  ServiceStatusBar (hidden if both OK)                │
└─────────────────────────────────────────────────────┘
```

- Uses `KpiCard`, `InsightCard` from `@foroba/ui`.
- If Pazuru offline: Cash = "–" with Badge variant=`default` showing "Pazuru offline".
- If Tsumi offline: Portfolio = "–" with Badge `default`.
- Both offline: full `ServiceUnavailable` state card.

---

## 7. i18n setup

```ts
// src/i18n.ts
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { en, fr, it } from '@foroba/ui/i18n';

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, fr: { translation: fr }, it: { translation: it } },
  lng: localStorage.getItem('foroba.language') ?? 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});
export default i18n;
```

---

## 8. Vite config

```ts
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/pazuru-api': { target: process.env.PAZURU_API_URL ?? 'http://localhost:8001', rewrite: p => p.replace('/pazuru-api', '') },
      '/tsumi-api':  { target: process.env.TSUMI_API_URL  ?? 'http://localhost:8000', rewrite: p => p.replace('/tsumi-api', '') },
    },
  },
});
```

---

## 9. CI (.gitlab-ci.yml)

Stages: `lint` → `test` → `build`.
Same pattern as `foroba-ui` but no `publish` stage. Artefact: `dist/` (static bundle).

---

## 10. GitLab setup

### Milestone: `SP2 — Foroba Shell`
### Labels: same set as all repos (sp2, feature, fix, test, docs, chore, a11y, i18n, security, blocked)

### Issues (20)
| # | Title | Labels |
|---|---|---|
| 1 | `[SP2] Repo scaffold: Vite, React 19, TS strict, Tailwind v4, @foroba/ui` | sp2, chore |
| 2 | `[SP2] Configure .npmrc + install @foroba/ui from GitLab registry` | sp2, chore |
| 3 | `[SP2] App shell: AppShell + Sidebar + Topbar + Footer from @foroba/ui` | sp2, feature |
| 4 | `[SP2] React Router v7 routes + lazy loading` | sp2, feature |
| 5 | `[SP2] TanStack Query setup + API clients (Pazuru + Tsumi)` | sp2, feature |
| 6 | `[SP2] i18n setup: react-i18next + @foroba/ui catalogs` | sp2, feature, i18n |
| 7 | `[SP2] Theme + language switching wired to useTheme/useLanguage` | sp2, feature |
| 8 | `[SP2] DashboardPage: net worth KPIs + ServiceStatusBar` | sp2, feature |
| 9 | `[SP2] NetWorthChart: Recharts area chart with @foroba/ui theme` | sp2, feature |
| 10 | `[SP2] AllocationPie: cash vs portfolio` | sp2, feature |
| 11 | `[SP2] AccountsPage: Pazuru summary + "service unavailable" fallback` | sp2, feature |
| 12 | `[SP2] PortfolioPage: Tsumi summary + "service unavailable" fallback` | sp2, feature |
| 13 | `[SP2] SettingsPage: wire @foroba/ui SettingsPage with app callbacks` | sp2, feature |
| 14 | `[SP2] LegalPage, HelpPage, AboutPage wired from @foroba/ui` | sp2, feature |
| 15 | `[SP2] OnboardingPage: first-run flow, skip on return` | sp2, feature |
| 16 | `[SP2] Empty/loading/error states for all pages` | sp2, feature |
| 17 | `[SP2] Commit docs/superpowers/specs/ into foroba repo` | sp2, docs |
| 18 | `[SP2] CI: lint → test → build (static bundle)` | sp2, chore |
| 19 | `[SP2] Wiki: Home, Architecture, Data-Model, Sprint-Reviews/SP2` | sp2, docs |
| 20 | `[SP2] Release v0.1.0: tag + announce` | sp2, chore |

---

## 11. Definition of Done

- [ ] GitLab project `bambac961/foroba` exists; main + develop branches.
- [ ] `pnpm install && pnpm build` succeeds; `dist/` is a valid static SPA.
- [ ] `pnpm test` all green.
- [ ] Dashboard loads (with or without Pazuru/Tsumi running) — no crash, graceful "unavailable".
- [ ] Theme switching: `.dark` class toggled on `<html>`, persists on refresh.
- [ ] Language switching EN/FR/IT: all labels change instantly.
- [ ] `docs/superpowers/specs/` committed in this repo.
- [ ] 20 GitLab issues created and closed.
- [ ] Wiki updated (Sprint Review SP2 + ADRs inherited).
- [ ] Tag `v0.1.0` on main.
