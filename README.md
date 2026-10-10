# Foroba

**Foroba** (fòroba = "common field / common wealth") is the unified super-app shell for the Personal Finance HUB suite.

It aggregates net worth from **Pazuru** (bank accounts) and **Tsumi** (ETF + crypto) into a single dashboard built on `@foroba/ui`.

## Stack

| Layer | Technology |
|---|---|
| Framework | React 19 + Vite 6 |
| Language | TypeScript (strict) |
| Styles | Tailwind CSS v4 + `@foroba/ui` tokens |
| Routing | React Router v7 |
| Data | TanStack Query v5 |
| Charts | Recharts |
| i18n | react-i18next + `@foroba/ui/i18n` (EN/FR/IT) |
| Tests | Vitest + Testing Library |

## Quick start

```bash
cp .env.example .env
pnpm install
pnpm dev          # http://localhost:5173
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `VITE_PAZURU_API_URL` | `http://localhost:8001` | Pazuru FastAPI base URL |
| `VITE_TSUMI_API_URL` | `http://localhost:8000` | Tsumi FastAPI base URL |

## Scripts

```bash
pnpm dev        # dev server
pnpm build      # tsc + vite build → dist/
pnpm test       # vitest watch
pnpm test:run   # vitest single run (CI)
pnpm lint       # ESLint
```

## Routes

| Path | Page |
|---|---|
| `/` | Dashboard — net worth, charts, allocation |
| `/accounts` | Accounts (Pazuru) |
| `/portfolio` | Portfolio (Tsumi) |
| `/settings` | Settings |
| `/help` | FAQ |
| `/legal` | Privacy / Terms / Fiscal / OSS |
| `/about` | About |
| `/onboarding` | First-run wizard |

## Related repos

- [`ForobaLabs/foroba-ui`](https://github.com/ForobaLabs/foroba-ui) — shared design system
- [`ForobaLabs/pazuru`](https://github.com/ForobaLabs/pazuru) — bank accounts (SP3+)
- [`ForobaLabs/tsumi`](https://github.com/ForobaLabs/tsumi) — ETF + crypto portfolio (SP3+)
