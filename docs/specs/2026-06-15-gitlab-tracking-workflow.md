# GitLab Tracking Workflow — Foroba Suite (all 4 repos)

> Principle: **no black box.** Anyone opening any repo must see what is done, in progress,
> and to do. Mirrors Tsumi's existing `GIT_SETUP.md`, generalized to 4 repos and to JS/TS apps.
> Namespace: `gitlab.com/bambac961`.

## Repos & their GitLab projects
| Repo | GitLab project | State |
|---|---|---|
| `foroba-ui` | `bambac961/foroba-ui` | **to create** (SP1) |
| `pazuru` | `bambac961/pazuru` (verify path) | exists locally; verify/create remote |
| `tsumi` | `bambac961/tsumi` | **rename** from `pfh_finance_asset_dashboard` (SP0) |
| `foroba` | `bambac961/foroba` | **to create** (SP2) |

> NOTE: actually creating/renaming GitLab projects, issues, milestones, MRs is EXECUTION
> work (do it in the Sonnet session via `glab`/UI). Confirm before destructive ops
> (project rename, repo delete). Prefer `glab` CLI; fall back to the GitLab UI.

## Branching (every repo)
`main` (stable) → `develop` (integration) → `feature/*` ; `hotfix/*` for critical main fixes.
Each sub-project (or sprint within it) = a `feature/spX-<name>` branch merged `--no-ff` to develop,
tagged `vX.Y.Z`, then released to `main`.

## Conventional commits (linked to issues)
`feat | fix | refactor | test | docs | style | chore | perf (scope): message — closes #N`
TS scopes: `ui`, `shell`, `dashboard`, `i18n`, `jeli`, `auth`, `household`.
Python scopes: keep existing (`services`, `db`, `tax`, ...).

## Issues — one per task
Title: `[SPx] Task name` · Labels: `spx` + one of `feature|fix|test|docs|chore` (+ `blocked`/`wontfix`).
Milestone: the sub-project. Body template:
```markdown
## Description
## Motivation / context
## Acceptance criteria
- [ ] ...
## Technical notes
- Files: ...   - Depends on: #...
## Tests required
- [ ] ...
```
Create via: `glab issue create --title "[SP0] ..." --label "sp0,chore" --milestone "SP0 — Rename Tsumi" --description "..."`

## Milestones — one per sub-project (all repos that participate)
`SP0 — Rename Tsumi`, `SP1 — Design System`, `SP2 — Foroba Shell`, `SP3 — Adopt @foroba/ui`,
`SP4 — Jeli`, `SP5 — Household`, `SP6 — Gamification`. Tag at completion.

## Labels (create in each repo)
`sp0`…`sp6`, `feature`, `fix`, `test`, `docs`, `chore`, `blocked`, `wontfix`, `a11y`, `i18n`, `security`.

## Wiki (each repo) — mandatory pages
`Home`, `Architecture`, `Tech-Stack`, `Design-System`, `Data-Model`, `Privacy-and-Security`,
`Sprint-Reviews/` (one per SP), `Architecture-Decision-Log/` (ADR-NNN), `Known-Issues`, `Runbook`.
Tsumi also keeps `Data-Sources`, `Database-Schema`, `Fiscal-Disclaimer`.
Update the Wiki at the end of each sub-project (Sprint Review + new ADRs + Known Issues).

## ADRs already decided (write at SP0/SP1 in the relevant repo Wiki)
- ADR — React/TypeScript convergence (Tsumi UI migrates Dash→React).
- ADR — Foroba umbrella brand + new shared palette.
- ADR — Multi-person household data model from day 1.
- ADR — Local-first + optional E2E-encrypted sync.
- ADR — Cloud-ready, config-driven, data minimization.
- ADR — Design system as versioned package `@foroba/ui` (dedicated repo).
- ADR — Unified local LLM "Jeli" (Ollama only).
(Tsumi keeps its existing ADR-001…006.)

## Merge Request template (`.gitlab/merge_request_templates/sprint.md` in each repo)
```markdown
## Sub-project / Sprint
## Closes
Closes #N, #N
## What was done
- [ ] ...
## Acceptance criteria verified
- [ ] ...
## Tests
- [ ] All green (TS: `npm test` / Python: `pytest -m "not integration"`)
## Wiki updated
- [ ] Sprint Review  - [ ] ADR if needed  - [ ] Known Issues
## Screenshots (if UI)
## Notes for reviewer
```

## CI per repo
- Python repos (Tsumi, Pazuru backend): existing `.gitlab-ci.yml` (lint: black/isort/flake8 or ruff; test: pytest `not integration` + coverage).
- TS repos (`foroba-ui`, `foroba`, Pazuru frontend): stages `lint` (eslint + tsc --noEmit), `test` (vitest), `build` (vite/tsup). `foroba-ui` also a `publish` stage to GitLab Package Registry on tags.

## One-time setup checklist (per repo, before coding)
- [ ] Remote configured, `develop` pushed
- [ ] Milestones created (the SPs that touch this repo)
- [ ] Labels created
- [ ] Wiki pages created + relevant ADRs written
- [ ] Issues for the current SP created (one per task)
- [ ] MR template committed
- [ ] CI committed and green
- [ ] README with badges committed
