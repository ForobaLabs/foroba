# SP1 — `@foroba/ui` Design System Spec

> Status: Approved (2026-06-15). Written by Opus.
> Repo to create: `gitlab.com/bambac961/foroba-ui`
> Local folder: `/Users/abdoulaye_bamba/Desktop/Personal_Finance_HUB/foroba-ui/`
> npm package name: `@foroba/ui`
> Initial version: `0.1.0`
> Execution: Sonnet session, `superpowers:executing-plans`.
> Depends on: SP0 complete ✅

---

## 1. Goals

Deliver the **shared design system** that all three apps (Pazuru, Tsumi, Foroba) will consume.
A versioned npm package (`@foroba/ui@0.1.0`) published to the GitLab Package Registry of
`bambac961/foroba-ui`.

Concrete deliverables:
- New GitLab project `bambac961/foroba-ui`, full GitLab workflow (milestones, labels, wiki, CI).
- npm package with **design tokens**, **core UI components**, **layout components**, **page
  templates** (Settings, Legal, Help, About, Onboarding), **chart themes**, **i18n catalogs**, and
  **household TypeScript types**.
- GitLab CI that lints, type-checks, tests, builds, and **publishes to the Package Registry** on
  semver tags.

---

## 2. Repository setup

### 2.1 Create GitLab project
- Via REST API (PAT in `.env` as `GITLAB_PAT`):
  `POST /api/v4/projects` with `name=foroba-ui`, `path=foroba-ui`, `namespace=bambac961`,
  `visibility=private`, `description="@foroba/ui shared design system for the Foroba Suite"`.
- Init `main` + `develop` branches; protect `main` (no direct push).

### 2.2 Local folder
```
mkdir /Users/abdoulaye_bamba/Desktop/Personal_Finance_HUB/foroba-ui
cd foroba-ui && git init && git remote add origin git@gitlab.com:bambac961/foroba-ui.git
```

### 2.3 npm + TypeScript scaffold
- Node: ≥ 20. Package manager: **pnpm** (consistent with Pazuru; declare `engines.pnpm`).
- `package.json` name: `"@foroba/ui"`, version `"0.1.0"`, `"type": "module"`.
- Peer deps (NOT bundled): `react@^18 || ^19`, `react-dom@^18 || ^19`.
- Devtools: TypeScript 5.x, tsup, Tailwind v4 CSS (`@tailwindcss/vite`), Vitest, ESLint (flat
  config), Prettier.
- Build tool: **tsup** (dual CJS + ESM, `.d.ts` declarations, sourcemaps).
- `exports` map in `package.json`:
  ```json
  {
    ".": { "import": "./dist/index.js", "require": "./dist/index.cjs", "types": "./dist/index.d.ts" },
    "./tokens": { ... },
    "./charts": { ... },
    "./i18n": { ... }
  }
  ```

### 2.4 MR template
`.gitlab/merge_request_templates/sprint.md` — same as `tsumi/.gitlab/merge_request_templates/sprint.md`
(copy the template from `2026-06-15-gitlab-tracking-workflow.md`).

---

## 3. Design tokens

### 3.1 Foroba palette

The Foroba umbrella uses **teal** as its signature accent (growth, clarity, common wealth).
Pazuru keeps **indigo**; Tsumi keeps **electric blue**. All three sit harmoniously on the same
neutral base.

#### CSS variables (src/tokens/tokens.css)
```css
/* --- Foroba token file — imported by every consumer via their Tailwind config --- */
:root {
  /* Neutral base (light mode) */
  --color-bg-primary:     #F8FAFC;   /* slate-50 */
  --color-bg-surface:     #FFFFFF;
  --color-bg-elevated:    #F1F5F9;   /* slate-100 */
  --color-bg-border:      #E2E8F0;   /* slate-200 */
  --color-text-primary:   #0F172A;   /* slate-900 */
  --color-text-secondary: #64748B;   /* slate-500 */
  --color-text-muted:     #94A3B8;   /* slate-400 */

  /* Foroba accent (teal) */
  --color-accent:         #0D9488;   /* teal-600 */
  --color-accent-hover:   #0F766E;   /* teal-700 */
  --color-accent-subtle:  #CCFBF1;   /* teal-100 */

  /* Per-app accent overrides (consumed by Pazuru/Tsumi via their CSS) */
  --color-pazuru-accent:  #4F46E5;   /* indigo-600 */
  --color-tsumi-accent:   #2F81F7;   /* electric blue */

  /* Semantic colours */
  --color-positive:       #059669;   /* emerald-600 */
  --color-negative:       #DC2626;   /* red-600 */
  --color-warning:        #D97706;   /* amber-600 */
  --color-info:           #0284C7;   /* sky-600 */

  /* Typography */
  --font-sans:  'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono:  'JetBrains Mono', 'Fira Code', monospace;
  --font-size-base: 14px;

  /* Spacing scale (t-shirt) */
  --space-xs: 0.25rem;   /* 4px */
  --space-sm: 0.5rem;    /* 8px */
  --space-md: 1rem;      /* 16px */
  --space-lg: 1.5rem;    /* 24px */
  --space-xl: 2rem;      /* 32px */
  --space-2xl: 3rem;     /* 48px */

  /* Radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-full: 9999px;

  /* Sidebar */
  --sidebar-width: 240px;
}

/* Dark mode overrides — class-based (.dark) AND @media prefers-color-scheme */
.dark, @media (prefers-color-scheme: dark) {
  --color-bg-primary:     #0F1117;
  --color-bg-surface:     #1A1F2E;
  --color-bg-elevated:    #242938;
  --color-bg-border:      #2D3348;
  --color-text-primary:   #F1F5F9;   /* slate-100 */
  --color-text-secondary: #94A3B8;   /* slate-400 */
  --color-text-muted:     #64748B;   /* slate-500 */

  --color-accent:         #14B8A6;   /* teal-500 */
  --color-accent-hover:   #0D9488;   /* teal-600 */
  --color-accent-subtle:  rgba(20, 184, 166, 0.15);

  --color-positive:       #34D399;   /* emerald-400 */
  --color-negative:       #F87171;   /* red-400 */
  --color-warning:        #FBBF24;   /* amber-400 */
  --color-info:           #38BDF8;   /* sky-400 */
}
```

#### TypeScript constants (src/tokens/tokens.ts)
Mirror every CSS variable as a typed TS constant for use in imperative code (Recharts,
Plotly, canvas). Structure:
```ts
export const colors = { bg: { primary, surface, ... }, text: { ... }, accent: { ... }, ... }
export const spacing = { xs, sm, md, lg, xl, xl2 }
export const radius = { sm, md, lg, full }
export const typography = { fontSans, fontMono, fontSizeBase }
```

### 3.2 Theme switching strategy
- Class-based: add `.dark` to `<html>`. Consumers call `useTheme()` hook (provided by `@foroba/ui`).
- `useTheme()` reads `localStorage.theme` (values: `"light" | "dark" | "system"`).
  System mode listens to `matchMedia('(prefers-color-scheme: dark)')`.
- No theme state in app — `<html>` class is the single source of truth.
- Server-side safe (no hydration mismatch): apply theme class in a blocking inline `<script>`.
- Hook is exported as `useTheme` from `@foroba/ui`.

---

## 4. Components

All components are TypeScript-strict, Tailwind v4 classes, shadcn/ui architecture (but bundled
into the package — consumers do NOT need to run shadcn CLI). Each has a Vitest unit test.

### 4.1 Primitive components (src/components/primitives/)
| Component | Notes |
|---|---|
| `Button` | variants: primary, secondary, outline, ghost, destructive; sizes: sm, md, lg |
| `Input` | text/email/password/number; error state; label + helper text |
| `Textarea` | resizable, char counter |
| `Select` | native + styled; async option load |
| `Checkbox` | + indeterminate |
| `Switch` / `Toggle` | accessible |
| `Badge` | variants: default, positive, negative, warning, info, pea (Tsumi-specific) |
| `Avatar` | initials fallback; size sm/md/lg |
| `Spinner` | animated, accessible `aria-busy` |
| `Skeleton` | shimmer animation; width/height props |
| `Tooltip` | keyboard-accessible |
| `Toast` / `Toaster` | success/error/warning/info; stack support |
| `Dialog` / `Modal` | accessible focus trap, close on Esc |
| `Tabs` | horizontal; keyboard nav |
| `Card` | surface card with optional header/footer |
| `Table` | responsive; sortable column support |
| `Separator` | horizontal/vertical |
| `KpiCard` | big value + delta (pos/neg colour); migrated from Tsumi's current `kpi_card.py` |
| `InsightCard` | Jeli/AI-insight card: icon + title + body + confidence chip |

### 4.2 Layout components (src/layouts/)
| Component | Notes |
|---|---|
| `AppShell` | `children` = main area; `sidebar` slot; `header` slot; handles margin-left |
| `Sidebar` | fixed left; brand logo slot; `navItems` prop; active-link highlight |
| `NavItem` | icon + label; href; active state; keyboard nav |
| `Topbar` | breadcrumb + right slot (refresh button, user avatar); sticky; respects sidebar width |
| `Footer` | links: Privacy · Terms · Help · About · Language · Theme · tagline; responsive |
| `PageContainer` | `fluid` prop; sets max-width, padding, respects sidebar |
| `SectionHeader` | `title` + optional `action` slot; `description` |

### 4.3 Form patterns (src/components/forms/)
| Component | Notes |
|---|---|
| `FormField` | label + input + error message wrapper (react-hook-form compatible) |
| `AmountInput` | formatted number input with currency symbol; uses JetBrains Mono |
| `DatePicker` | lightweight (no heavy library); keyboard accessible |
| `LanguageSelect` | EN/FR/IT switcher, calls `useLanguage()` hook |
| `ThemeSelect` | system/light/dark, calls `useTheme()` hook |

---

## 5. Page templates

These are **React page-level components** exported from `@foroba/ui`. Each app mounts
them directly (with its router) and passes app-specific callbacks via props. Copy fits
in the i18n catalogs.

### 5.1 SettingsPage
Sections (all scrollable on one page, or tabbed):
- **Profile**: name, avatar, household role selector, base currency, date format, finance level slider (novice ↔ expert).
- **Appearance**: ThemeSelect + density (compact/comfortable) + reduce-motion toggle.
- **Language**: LanguageSelect.
- **Jeli (AI)**: enable/disable, personality slider (analytical ↔ friendly), verbosity, model info (read-only from env), "runs 100% locally" badge.
- **Connections**: slot for per-app connection rows (prop `connectionSlots: ReactNode[]`).
- **Privacy & Data**: local-first explainer, E2E sync toggle (disabled if not available), "Export my data" button, "Delete all data" button with confirmation dialog.
- **Notifications**: per-channel toggles (prop).
- **Household**: placeholder stub (linked to SP5).
- **About**: version, build, changelog, OSS licenses link, brand story.

### 5.2 LegalPage
Static-ish page. Content prop-injected (each app provides its own copy or falls back to
generic `@foroba/ui` strings). Sections:
- Privacy Policy (local-first, data minimization model).
- Terms of Service / EULA.
- Cookie / tracking statement.
- OSS licenses (auto-generated from package.json `license-checker` output — injected as prop).
- Imprint (placeholder company info).
- Data processing & security overview.
- "Last updated: `{date}`" per section.

### 5.3 HelpPage
- Searchable FAQ (items passed as props: `{ question, answer, tags }[]`).
- Guided tours trigger (calls `onStartTour()` prop per page key).
- Contact/feedback section (email link + GitLab issues link).
- Diagnostics export button (no sensitive data; calls `onExportDiagnostics()` prop).
- Financial education entry point (link to SP6 glossary).

### 5.4 AboutPage
- App name, version, build date, changelog (markdown prop).
- Jeli, Pazuru, Tsumi, Foroba name etymology.
- Links to Privacy, Terms, Help.
- "Open source? Partial" note + link to OSS licenses.

### 5.5 OnboardingPage
Stepper (4 steps, skippable, resumable — state persisted in `localStorage["foroba.onboarding"]`):
1. **Welcome**: Foroba brand story in 2 sentences. Language select. Dark/light select.
2. **Profile**: name, household type (just you / family), finance level slider. "Discreet: we never send this anywhere."
3. **Privacy**: local-first explainer, explicit "your data stays on this device" confirmation.
4. **Connect**: prompt to connect first data source (per-app slot). Skippable.

---

## 6. i18n catalogs

Package ships message catalogs **only** (no i18n library bundled). Consumers plug these
into their existing i18n library (react-i18next in Pazuru; others later).

### Structure (src/i18n/)
```
i18n/
├── locales/
│   ├── en.json
│   ├── fr.json
│   └── it.json
└── index.ts   # re-exports all locales + type-safe key types
```

### Coverage
Every UI string in all `@foroba/ui` components and page templates must have entries in
all three locales. Categories:
- `common.*`: OK, Cancel, Save, Delete, Loading, Error, Empty, Back, Next, etc.
- `settings.*`: all SettingsPage labels and descriptions.
- `legal.*`: Privacy Policy text, ToS text, cookie text (generic versions; apps can override).
- `help.*`: generic FAQ items (apps extend with their own).
- `onboarding.*`: all stepper copy.
- `nav.*`: sidebar/topbar nav labels.
- `jeli.*`: Jeli-specific labels (model info, personality slider labels).
- `errors.*`: generic error messages (network, service unavailable, unknown).
- `amounts.*`: formatting patterns for EUR, USD (with `Intl.NumberFormat`).

---

## 7. Chart themes

### 7.1 Recharts theme (src/charts/recharts.ts)
Exports a `RECHARTS_THEME` object:
```ts
{
  colors: [accent, positive, negative, warning, info, ...8 total],
  grid: { stroke: borderColor, strokeDasharray: '3 3' },
  axis: { tick: { fill: textSecondary }, axisLine: { stroke: borderColor } },
  tooltip: { contentStyle: { background: bgSurface, border, color } },
}
```
And helper hooks:
- `useRechartsTheme()` — returns the theme object, reacts to dark/light switches.

### 7.2 Plotly theme (src/charts/plotly.ts)
Exports `PLOTLY_LAYOUT_TEMPLATE` and `PLOTLY_CONFIG` objects matching Tsumi's current
`"plotly_dark"` override but using Foroba tokens. Used when Tsumi's pages are migrated
to React in SP3.

---

## 8. TypeScript types — Household & Profile

Shipped in `@foroba/ui` at SP1 so every app imports from the same canonical source.
Schema details finalized here (SP5 implements the UX; the schema is locked now to avoid
painful migrations).

### src/types/household.ts
```ts
export type FinanceLevel = 'novice' | 'intermediate' | 'expert';
export type HouseholdRole = 'owner' | 'member' | 'child_guardian' | 'view_only';
export type AccountType = 'single' | 'family';

export interface HouseholdMember {
  id: string;           // uuid
  name: string;
  avatarUrl?: string;
  role: HouseholdRole;
  financeLevel: FinanceLevel;
  language: 'en' | 'fr' | 'it';
  joinedAt: string;     // ISO 8601
}

export interface Child {
  id: string;
  name: string;
  birthYear: number;
  guardianIds: string[];
}

export interface Household {
  id: string;
  name: string;         // e.g. "Bamba household"
  type: AccountType;
  members: HouseholdMember[];
  children: Child[];
  createdAt: string;
  inviteToken?: string; // for SP5 family linking
}

export interface UserProfile extends HouseholdMember {
  baseCurrency: string;  // e.g. "EUR"
  dateFormat: 'DD/MM/YYYY' | 'MM/DD/YYYY' | 'YYYY-MM-DD';
  theme: 'system' | 'light' | 'dark';
  density: 'compact' | 'comfortable';
  reduceMotion: boolean;
  jeliEnabled: boolean;
  jeliPersonality: number;   // 0=analytical … 100=friendly
  jeliVerbosity: 'concise' | 'normal' | 'verbose';
}
```

### src/types/common.ts
```ts
export type Currency = 'EUR' | 'USD' | 'GBP' | 'CHF' | 'JPY';
export type AssetType = 'etf' | 'crypto' | 'stock' | 'cash';
export type ServiceStatus = 'ok' | 'degraded' | 'unavailable' | 'loading';

export interface ServiceHealth {
  name: string;
  status: ServiceStatus;
  lastRefresh?: string;
  error?: string;
}

export interface NetWorthSnapshot {
  date: string;         // ISO 8601
  totalEur: number;
  cashEur: number;      // Pazuru
  portfolioEur: number; // Tsumi
}
```

---

## 9. Hooks

Exported hooks (src/hooks/):
| Hook | Returns |
|---|---|
| `useTheme()` | `{ theme, setTheme }` — manages `localStorage.theme` + `.dark` class |
| `useLanguage()` | `{ language, setLanguage }` — manages `localStorage.language` + `i18n.changeLanguage` |
| `useUserProfile()` | reads/writes `UserProfile` from `localStorage["foroba.profile"]` |
| `useServiceHealth(services)` | polls `/health` endpoints, returns `ServiceHealth[]` |
| `useMediaQuery(query)` | reactive media query wrapper |

---

## 10. CI pipeline (.gitlab-ci.yml)

Stages: `lint` → `test` → `build` → `publish`.

```yaml
stages: [lint, test, build, publish]

variables:
  PNPM_VERSION: "9"
  NODE_VERSION: "20"

lint:
  stage: lint
  script:
    - pnpm install --frozen-lockfile
    - pnpm lint        # eslint flat config
    - pnpm tsc --noEmit

test:
  stage: test
  script:
    - pnpm install --frozen-lockfile
    - pnpm test --coverage
  coverage: '/Statements\s*:\s*(\d+\.?\d*)%/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura-coverage.xml

build:
  stage: build
  script:
    - pnpm install --frozen-lockfile
    - pnpm build       # tsup: CJS + ESM + .d.ts
  artifacts:
    paths: [dist/]

publish:
  stage: publish
  script:
    - pnpm install --frozen-lockfile
    - pnpm build
    - |
      # Publish to GitLab Package Registry
      echo "@foroba:registry=https://gitlab.com/api/v4/projects/${CI_PROJECT_ID}/packages/npm/" >> .npmrc
      echo "//gitlab.com/api/v4/projects/${CI_PROJECT_ID}/packages/npm/:_authToken=${CI_JOB_TOKEN}" >> .npmrc
      pnpm publish --no-git-checks
  rules:
    - if: '$CI_COMMIT_TAG =~ /^v[0-9]+\.[0-9]+\.[0-9]+$/'
```

---

## 11. GitLab setup — one-time checklist for `foroba-ui`

### 11.1 Milestone
`SP1 — Design System` — due open (no hard deadline yet).

### 11.2 Labels
Same set as all repos: `sp1`, `feature`, `fix`, `test`, `docs`, `chore`, `a11y`, `i18n`, `security`, `blocked`, `wontfix`.

### 11.3 Issues (create in `foroba-ui`, all in milestone `SP1 — Design System`)

| # | Title | Labels | Description summary |
|---|---|---|---|
| 1 | `[SP1] Repo scaffold: pnpm, tsup, TypeScript, ESLint, Vitest` | sp1, chore | Init package, tooling, CI stub, MR template, README |
| 2 | `[SP1] Design tokens: Foroba palette + CSS variables + TS constants` | sp1, feature | All CSS vars light/dark, TS constants mirror, tokens.css file |
| 3 | `[SP1] Theme switching: useTheme hook + class strategy` | sp1, feature | useTheme, localStorage, blocking script, system-adaptive |
| 4 | `[SP1] i18n: EN/FR/IT message catalogs` | sp1, feature, i18n | All strings for all templates, TypeScript key types |
| 5 | `[SP1] Primitive components: Button, Input, Badge, Avatar, Spinner, Skeleton, Tooltip, Toast` | sp1, feature | shadcn-style, Tailwind, tests |
| 6 | `[SP1] Primitive components: Dialog, Tabs, Card, Table, Switch, Select, Separator` | sp1, feature | continuation of #5 |
| 7 | `[SP1] KpiCard + InsightCard components` | sp1, feature | From Tsumi kpi_card.py; InsightCard for Jeli |
| 8 | `[SP1] Layout components: AppShell, Sidebar, NavItem, Topbar, Footer, PageContainer` | sp1, feature | Full layout system |
| 9 | `[SP1] Form patterns: FormField, AmountInput, DatePicker, LanguageSelect, ThemeSelect` | sp1, feature | react-hook-form compatible |
| 10 | `[SP1] Page template: SettingsPage` | sp1, feature | All 8 settings sections, prop-injected callbacks |
| 11 | `[SP1] Page template: LegalPage` | sp1, feature, i18n | All legal sections, prop-injected content |
| 12 | `[SP1] Page template: HelpPage` | sp1, feature | FAQ, tours, diagnostics, contact |
| 13 | `[SP1] Page template: AboutPage + OnboardingPage` | sp1, feature | 4-step onboarding, About sections |
| 14 | `[SP1] TypeScript types: UserProfile, Household, Member, Child, NetWorthSnapshot, ServiceHealth` | sp1, feature | Canonical household data model |
| 15 | `[SP1] Hooks: useUserProfile, useLanguage, useServiceHealth, useMediaQuery` | sp1, feature | All hooks with tests |
| 16 | `[SP1] Chart themes: Recharts + Plotly` | sp1, feature | useRechartsTheme, PLOTLY_LAYOUT_TEMPLATE |
| 17 | `[SP1] Barrel export (index.ts) + package.json exports map` | sp1, chore | All public exports, subpath exports |
| 18 | `[SP1] CI: lint → test → build → publish to GitLab Package Registry` | sp1, chore | Full pipeline, rules for publish on tag |
| 19 | `[SP1] Wiki: Home, Architecture, Tech-Stack, Design-System, ADRs` | sp1, docs | All mandatory wiki pages + 7 ADRs from master plan |
| 20 | `[SP1] Release v0.1.0: tag + publish + announce` | sp1, chore | Tag, CI publish, verify install from registry |

### 11.4 Wiki pages to create
Required pages (from `2026-06-15-gitlab-tracking-workflow.md`):
- **Home**: what is `@foroba/ui`, install instructions, version badge.
- **Architecture**: monorepo vs dedicated-repo decision (ADR), tsup + ESM/CJS, Tailwind v4.
- **Tech-Stack**: pnpm, TypeScript 5, tsup, Tailwind v4, shadcn/ui, Vitest, GitLab Package Registry.
- **Design-System**: full token table (colors, spacing, typography), dark/light palette chart, per-app accent table.
- **Sprint-Reviews/SP1**: written after SP1 completion.
- **Architecture-Decision-Log/ADR-001** through **ADR-007**: the 7 locked decisions from the master plan.
- **Known-Issues**: empty at start, populated as discovered.
- **Runbook**: how to install, build, publish a new version, consume in apps.

---

## 12. Package.json (key fields)

```json
{
  "name": "@foroba/ui",
  "version": "0.1.0",
  "description": "Shared design system for the Foroba Suite (Pazuru, Tsumi, Foroba)",
  "type": "module",
  "main": "./dist/index.cjs",
  "module": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": "./dist/index.js",
      "require": "./dist/index.cjs",
      "types": "./dist/index.d.ts"
    },
    "./tokens": {
      "import": "./dist/tokens.js",
      "require": "./dist/tokens.cjs",
      "types": "./dist/tokens.d.ts"
    },
    "./charts": {
      "import": "./dist/charts.js",
      "require": "./dist/charts.cjs",
      "types": "./dist/charts.d.ts"
    },
    "./i18n": {
      "import": "./dist/i18n.js",
      "require": "./dist/i18n.cjs",
      "types": "./dist/i18n.d.ts"
    },
    "./tokens.css": "./dist/tokens.css"
  },
  "peerDependencies": {
    "react": "^18 || ^19",
    "react-dom": "^18 || ^19"
  },
  "files": ["dist", "README.md"],
  "scripts": {
    "build": "tsup",
    "dev": "tsup --watch",
    "lint": "eslint src",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit"
  },
  "publishConfig": {
    "@foroba:registry": "https://gitlab.com/api/v4/projects/FOROBA_UI_PROJECT_ID/packages/npm/"
  }
}
```

---

## 13. File tree

```
foroba-ui/
├── .gitlab/
│   └── merge_request_templates/
│       └── sprint.md
├── .gitlab-ci.yml
├── .eslintrc.mjs            (or eslint.config.mjs)
├── .gitignore
├── .npmrc                   (registry config for local publish)
├── .prettierrc
├── LICENSE                  (MIT)
├── README.md
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── tsup.config.ts
├── vitest.config.ts
└── src/
    ├── index.ts             (barrel export — everything public)
    ├── tokens/
    │   ├── tokens.css       (CSS variables, both modes)
    │   └── tokens.ts        (TS constants)
    ├── hooks/
    │   ├── useTheme.ts
    │   ├── useLanguage.ts
    │   ├── useUserProfile.ts
    │   ├── useServiceHealth.ts
    │   └── useMediaQuery.ts
    ├── types/
    │   ├── household.ts
    │   └── common.ts
    ├── components/
    │   ├── primitives/
    │   │   ├── Button.tsx
    │   │   ├── Input.tsx
    │   │   ├── Textarea.tsx
    │   │   ├── Select.tsx
    │   │   ├── Checkbox.tsx
    │   │   ├── Switch.tsx
    │   │   ├── Badge.tsx
    │   │   ├── Avatar.tsx
    │   │   ├── Spinner.tsx
    │   │   ├── Skeleton.tsx
    │   │   ├── Tooltip.tsx
    │   │   ├── Toast.tsx
    │   │   ├── Dialog.tsx
    │   │   ├── Tabs.tsx
    │   │   ├── Card.tsx
    │   │   ├── Table.tsx
    │   │   ├── Separator.tsx
    │   │   └── index.ts
    │   ├── display/
    │   │   ├── KpiCard.tsx
    │   │   ├── InsightCard.tsx
    │   │   └── index.ts
    │   └── forms/
    │       ├── FormField.tsx
    │       ├── AmountInput.tsx
    │       ├── DatePicker.tsx
    │       ├── LanguageSelect.tsx
    │       ├── ThemeSelect.tsx
    │       └── index.ts
    ├── layouts/
    │   ├── AppShell.tsx
    │   ├── Sidebar.tsx
    │   ├── NavItem.tsx
    │   ├── Topbar.tsx
    │   ├── Footer.tsx
    │   ├── PageContainer.tsx
    │   ├── SectionHeader.tsx
    │   └── index.ts
    ├── pages/
    │   ├── SettingsPage.tsx
    │   ├── LegalPage.tsx
    │   ├── HelpPage.tsx
    │   ├── AboutPage.tsx
    │   ├── OnboardingPage.tsx
    │   └── index.ts
    ├── charts/
    │   ├── recharts.ts      (RECHARTS_THEME, useRechartsTheme)
    │   └── plotly.ts        (PLOTLY_LAYOUT_TEMPLATE, PLOTLY_CONFIG)
    └── i18n/
        ├── locales/
        │   ├── en.json
        │   ├── fr.json
        │   └── it.json
        └── index.ts
```

---

## 14. Definition of Done for SP1

- [ ] GitLab project `bambac961/foroba-ui` exists; `main` + `develop` branches protected.
- [ ] All 20 issues created + closed by the end of SP1.
- [ ] `pnpm install && pnpm build` succeeds; `dist/` contains CJS + ESM + `.d.ts`.
- [ ] `pnpm test` all green (≥ 80% statement coverage).
- [ ] `pnpm lint && pnpm tsc --noEmit` zero errors.
- [ ] `tokens.css` light and dark vars verified visually (simple HTML testbed).
- [ ] All i18n keys present in all three locales (CI or test enforces this).
- [ ] Package published to GitLab Package Registry as `@foroba/ui@0.1.0`.
- [ ] A consumer test: add `@foroba/ui` to Pazuru's `devDependencies`, import `Button`, `useTheme`,
  `colors` — verify types resolve; no runtime errors.
- [ ] Wiki: all mandatory pages created; all 7 ADRs written.
- [ ] MR !1 `feature/sp1-design-system` → `develop` → `main`; tag `v0.1.0`.
- [ ] `MEMORY.md` updated: SP1 complete, package registry URL, version.

---

## 15. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Tailwind v4 CSS-first changes peer-dep install flow | Follow Tailwind v4 official "package consumption" guide; test with both Pazuru (Vite) and a plain HTML consumer |
| GitLab Package Registry npm auth in CI | Use `CI_JOB_TOKEN` (built-in); document in Runbook for local `pnpm publish` using PAT |
| shadcn components have implicit @radix-ui peer deps | Bundle radix-ui dependencies inside `@foroba/ui` (not peer deps) to keep consumer setup simple |
| tsup dual output breaks some consumers | Add a `dist/` smoke-test Vitest that imports from both CJS and ESM paths |
| French/Italian translations not native quality | Mark all FR/IT translations as `[DRAFT — human review needed]` until reviewed by user |
