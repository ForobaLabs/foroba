# SP2

# SP2 Sprint Review — Foroba Shell

**Date**: 2026-06-15  
**Tag**: v0.1.0  
**Commit**: 6e3c9a6

## Completed (20/20 issues closed)

### Infrastructure
- #1 Scaffolded Vite + React 19 + TypeScript (strict)
- #2 @foroba/ui wired as `file:../foroba-ui` local dep
- #3 Tailwind CSS v4 + `@foroba/ui/tokens.css` imported
- #19 CI: lint (tsc) → test (vitest) → build (vite)
- #20 All suite specs copied to `docs/specs/`

### Layout & Routing
- #4 React Router v7 with lazy-loaded routes (7 pages)
- #5 AppShell with Sidebar, Topbar, Footer from @foroba/ui
- #18 Blocking theme-init script in `index.html` (no FOUC)

### Data Layer
- #6 API helpers: `pazuru.ts`, `tsumi.ts`, `foroba.ts` (5s timeout)
- #7 `useNetWorth` hook (TanStack Query, 60s refetch)
- #8 `useServiceHealth` hooks (30s refetch)

### Dashboard
- #9 DashboardPage: KPI card, charts, service status
- #10 NetWorthChart: Recharts AreaChart with `useRechartsTheme()`
- #11 AllocationPie: Recharts PieChart (cash vs portfolio)
- #12 ServiceStatusBar: hidden if both OK, warns when offline

### Pages
- #13 AccountsPage (Pazuru proxy placeholder)
- #14 PortfolioPage (Tsumi proxy placeholder)
- #15 AppSettingsPage → `@foroba/ui` SettingsPage
- #16 AppOnboardingPage → `@foroba/ui` OnboardingPage
- #17 react-i18next with EN/FR/IT from `@foroba/ui/i18n`

## What is NOT done (deferred to SP3)
- Full Pazuru bank transaction UI
- Full Tsumi portfolio React migration
- Real backend data flowing into net worth chart

