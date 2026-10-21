# ADR 004 jeli streaming architecture

# ADR-004: Jeli Streaming Architecture

**Status**: Accepted  
**Date**: 2026-06-15

## Context
Jeli needs to provide real-time, word-by-word streaming responses from Ollama to give the user immediate feedback and a natural conversation feel.

## Decision
- **Backend**: FastAPI `StreamingResponse` with `media_type="text/plain"` proxies Ollama `/api/chat` stream
- **Frontend**: `fetch()` + `ReadableStream` + `getReader()` accumulates chunks, updating React state on each chunk
- **No SSE/WebSocket**: plain streaming text is simpler, avoids CORS complexity, and sufficient for this use case
- **Abort**: `AbortController` lets the user stop generation mid-stream

## Context gathering
Before each Jeli response:
1. `gather_context()` calls `GET /jeli/context` on Pazuru AND Tsumi in parallel (3s timeout each)
2. Offline services return graceful error strings (Jeli acknowledges the gap)
3. Both contexts are formatted into the system prompt

## Consequences
- Responses feel instant (first tokens arrive in <1s on local Ollama)
- If Ollama is not running, the fetch to `/jeli/chat` returns 500 and the panel shows an error
- Privacy maintained: no conversation history stored server-side

