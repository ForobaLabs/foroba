# ADR 003 query intervals

# ADR-003: TanStack Query refetch intervals

**Status**: Accepted  
**Date**: 2026-06-15

## Context
Foroba displays live data from two separate backend services. We need a refresh strategy that stays current without hammering the APIs.

## Decision
| Hook | Interval | Rationale |
|---|---|---|
| `useNetWorth` | 60 seconds | Net worth changes slowly; polling frequently is wasteful |
| `useServiceHealth` | 30 seconds | Need to detect service outages quickly for the status bar |
| `staleTime` (global) | 30 seconds | Default TanStack Query global — prevents redundant refetches |

## Consequences
- Dashboard data is at most 60s stale — acceptable for personal finance.
- If a service goes offline, the user sees the status bar warning within 30s.

