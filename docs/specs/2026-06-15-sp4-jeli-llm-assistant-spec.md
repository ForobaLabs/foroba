# SP4 — Jeli: Unified Local LLM Assistant

> Status: Approved (2026-06-15). Author: Claude Sonnet 4.6.
> Execution model: same session writes and executes this spec.

---

## Vision

**Jeli** (from the Mande/Bambara griot tradition — "the one with the gift of speech") is a unified
cross-domain AI assistant that runs entirely on the user's machine via Ollama.

It answers questions spanning BOTH financial domains:
- Pazuru (bank accounts, cash flow, spending)
- Tsumi (ETF + crypto portfolio)

Examples:
- "How much can I invest this month given my spending?"
- "My portfolio dropped 8% — is my emergency fund OK?"
- "What's my savings rate this year?"

Jeli lives in the **Foroba** shell. Each sub-app (Pazuru, Tsumi) exposes a `/jeli` API endpoint
that Jeli can call to fetch context. Personality is configurable in Settings.

---

## Architecture

```
Foroba shell (React)
  └── JeliPanel (floating chat panel, drawer)
        └── POST /jeli/chat  → Foroba Jeli backend (FastAPI)
              ├── GET /pazuru-api/jeli/context → Pazuru context
              ├── GET /tsumi-api/jeli/context  → Tsumi context
              └── Ollama qwen3.5:9b (local)
```

### Context gathering
Each service exposes `GET /jeli/context` returning a compact JSON summary:
- **Pazuru**: total balance, top spending categories, monthly cash flow, recent transactions summary
- **Tsumi**: portfolio value, top positions, day/week change, asset allocation

Foroba Jeli backend merges both contexts into a system prompt + user query, sends to Ollama,
streams the response back to the React panel.

### Personality
Controlled by `JeliPersonality` (stored in `UserProfile.jeliPersonality`):
- `analytical` (0) ↔ `friendly` (10) slider in Settings
- `novice` ↔ `expert` slider in Settings (adapts jargon level)

These values are passed in the system prompt prefix.

---

## SP4 Tasks

### Foroba Jeli backend (issues #1–#8)

#### #1 Create `foroba/backend/` FastAPI app
`foroba/backend/main.py` — thin FastAPI with one route:
- `POST /jeli/chat` — accepts `{message: string, personality: {...}}`, streams response

#### #2 Create `foroba/backend/jeli_service.py`
- `gather_context()`: calls Pazuru + Tsumi `/jeli/context` endpoints (parallel, 3s timeout each, graceful if offline)
- `build_system_prompt(context, personality)`: formats context + personality into Ollama system prompt
- `stream_chat(system_prompt, message)`: calls Ollama `/api/chat` with `qwen3.5:9b`, returns streaming generator

#### #3 Jeli system prompt template
`foroba/backend/prompts/jeli_system.txt` — Jeli's persona:
- Knowledgeable about personal finance (ETF, crypto, cashflow, budgets)
- Analytical tone at 0, warm/friendly griot tone at 10
- Expert mode uses financial jargon; novice mode explains terms
- Always cites which data source (Pazuru/Tsumi) it's drawing from
- Privacy-first: never store conversation history

#### #4 Pazuru: add `/jeli/context` endpoint
`pazuru/backend/api/routes/jeli.py`:
- `GET /jeli/context` → calls `services.jeli_context_service` to return compact summary

#### #5 Pazuru: `jeli_context_service.py`
Returns: `{total_balance_eur, monthly_income_eur, monthly_expenses_eur, savings_rate_pct, top_5_categories: [{name, amount_eur}], cash_flow_trend: "positive"|"negative"|"stable"}`

#### #6 Tsumi: add `/jeli/context` endpoint
`tsumi/api/routes/jeli.py`:
- `GET /jeli/context` → calls portfolio service to return compact summary

#### #7 Tsumi: jeli context in services
Returns: `{total_value_eur, day_change_pct, week_change_pct, etf_allocation_pct, crypto_allocation_pct, top_5_positions: [{ticker, value_eur}], ytd_return_pct}`

#### #8 Foroba backend: `.env.example` + `requirements.txt` + `README.md`
`OLLAMA_BASE_URL=http://localhost:11434`, `OLLAMA_MODEL=qwen3.5:9b`,
`PAZURU_API_URL=http://localhost:8001`, `TSUMI_API_URL=http://localhost:8050`

### Foroba shell — Jeli UI (issues #9–#14)

#### #9 `JeliPanel` component
`foroba/src/components/JeliPanel.tsx`:
- Floating panel (bottom-right drawer, 400px wide, full height)
- Trigger: Jeli button in Topbar
- Displays conversation (user/assistant messages)
- Input box + send button
- Streaming response display (typewriter effect using fetch + ReadableStream)

#### #10 `useJeli` hook
`foroba/src/hooks/useJeli.ts`:
- State: messages[], isStreaming, error
- `sendMessage(text)`: POST to `/jeli/chat` (proxied), parse SSE stream

#### #11 Personality slider in Settings
`foroba/src/components/JeliPersonalitySettings.tsx`:
- Two sliders: analytical↔friendly (0–10), novice↔expert (0–10)
- Stored in localStorage['foroba.jeli.personality']
- Passed to every `/jeli/chat` call

#### #12 Jeli button in Topbar
Add Jeli icon button to `@foroba/ui` Topbar (or override in `foroba/src/App.tsx`)
Toggles `JeliPanel` open/closed.

#### #13 Jeli context display in Dashboard
`foroba/src/pages/DashboardPage.tsx`: add `InsightCard` with Jeli suggestion (pulled from last message or a static tip when idle).

#### #14 Foroba vite proxy: add `/jeli` → `http://localhost:8002`
Add to `foroba/vite.config.ts`.

### GitLab tracking (issues #15–#20)

#### #15 Write SP4 spec to docs/specs/
#### #16 Foroba backend GitLab CI (lint + test + docker build)
#### #17 Update Foroba wiki with Jeli ADRs
#### #18 Update Pazuru wiki with jeli/context ADR
#### #19 Update Tsumi wiki with jeli/context ADR
#### #20 Tag foroba v0.2.0 after Jeli integration

---

## Personality system prompt template

```
You are Jeli, a personal financial advisor for {user_name}.
Tone: {personality_tone} (0=analytical/precise, 10=warm/encouraging griot style)
Expertise: {expertise_level} (0=explain basics, 10=use financial terminology freely)

Current financial context:
--- CASH (Pazuru) ---
{pazuru_context}

--- PORTFOLIO (Tsumi) ---
{tsumi_context}

Rules:
- Answer only questions about personal finance
- When data is unavailable, say so clearly
- Cite which service (Pazuru/Tsumi) data comes from
- Never store or reference previous conversations
- Fiscal estimates are indicative only — recommend a professional for tax advice
```

---

## Definition of Done

- `POST /jeli/chat` returns streaming response from Ollama
- JeliPanel opens/closes, messages render in real time
- Personality sliders change Jeli's tone visibly in the prompt
- Both `/jeli/context` endpoints respond (gracefully if service offline)
- GitLab: 20 issues closed, milestone closed, foroba v0.2.0 tagged
