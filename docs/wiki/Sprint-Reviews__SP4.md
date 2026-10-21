# SP4

# SP4 Sprint Review — Jeli LLM Assistant

**Date**: 2026-06-15  
**Tag**: v0.2.0  
**Commit**: 72d4ccd

## Completed (20/20 issues)

### Foroba Backend
- #21 FastAPI Jeli backend at `foroba/backend/main.py` (port 8002)
- #22 `jeli_service.py`: parallel context gathering, system prompt builder, Ollama streaming
- #23 `prompts/jeli_system.txt`: persona template with personality slots
- #32 `.env.example`, `requirements.txt`, `config.py` (pydantic-settings)
- #33 CORS + `/health` endpoint

### API Context Endpoints
- #24 Pazuru `GET /jeli/context` → cash summary (balance, income, expenses, top categories)
- #34 Pazuru `/jeli` router registered in `app/main.py`
- #25 Tsumi `GET /jeli/context` → portfolio summary (value, positions, allocation)
- #35 Tsumi `/jeli` router registered in `frontend/app.py`

### Foroba Shell
- #27 `JeliPanel.tsx`: floating 400px drawer, streaming chat, stop/clear buttons
- #28 `useJeli` hook: fetch + ReadableStream, abort on stop, message accumulation
- #29 `JeliPersonalitySettings.tsx`: dual sliders (tone 0-10, expertise 0-10)
- #30 Jeli button in Topbar (`App.tsx` actions slot)
- #31 Personality persisted in `localStorage["foroba.jeli.personality"]`
- #26 Vite proxy: `/jeli → localhost:8002`
- #36 SP4 spec copied to `docs/specs/`
- #37 `.env.example` updated with `VITE_JELI_API_URL`

## Architecture decision
See [ADR-004: Jeli Streaming Architecture](ADR/ADR-004-jeli-streaming-architecture)

## Deferred to later sprints
- Jeli voice input (future)
- Conversation history with opt-in E2E encryption (SP6+)
- Jeli proactive alerts (budget breach, big portfolio moves)

