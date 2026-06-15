# SP0 — Cleanup & Rename to Tsumi (Spec)

> Status: Approved (2026-06-15). First sub-project. Mechanical but foundational.
> Execution: run in a Sonnet session via `superpowers:executing-plans`.
> Repo affected: `pfh_finance_asset_dashboard` → `tsumi` (GitLab `bambac961`).
> Also: remove the duplicate `etf-dashboard/` folder.

## Goal
1. Remove the stale duplicate `etf-dashboard/` (kept: `pfh_finance_asset_dashboard`).
2. Rename the project to **Tsumi** (積み) everywhere: folder, code, docs, DB filename, badges.
3. Rename the GitLab project + path and update remotes/links.
4. Keep CI lint + tests green throughout. No behavior change, no UI migration (that's SP3).

## Out of scope (do NOT do here)
- No Dash→React migration (SP3). No new design system (SP1). No new features.
- Do not touch business logic in `services/`, `analytics/`, DB schema, or fiscal calculations.

## Brand decision for the rename
- Product name: **Tsumi** (積み, "stacking/accumulation" — wealth that builds up over time).
- Keep the existing fiscal disclaimer verbatim. Keep all functionality identical.
- DB default path: `data/etf_dashboard.duckdb` → `data/tsumi.duckdb` (gitignored, regenerated
  from seed; optionally move the existing local file — see Phase 3 note).

---

## Phase 1 — Remove the duplicate `etf-dashboard/` (SAFETY-GATED)
1. Verify it really is a stale duplicate: diff the two trees excluding `.git/.venv/node_modules`.
   Confirm `etf-dashboard` has **no GitLab remote** (`git -C etf-dashboard remote -v`) and no
   unique uncommitted work.
2. **STOP and ask the user to confirm deletion** (destructive, user already pre-approved but
   reconfirm because it's irreversible). Show the diff summary.
3. On confirm: delete `etf-dashboard/`. (Move to Trash if possible rather than `rm -rf`.)

## Phase 2 — Local folder rename
1. Ensure the working tree is clean (`git -C pfh_finance_asset_dashboard status`); commit/stash first.
2. Rename folder `pfh_finance_asset_dashboard` → `tsumi` (use `git mv` at repo level is N/A for the
   repo root; rename the directory on disk; git remote/history are unaffected).
3. Recreate the venv path reference if any tooling hardcodes it (the `.venv` is gitignored; user
   may recreate it). Note in README that `.venv` must be recreated after the rename.

## Phase 3 — In-repo text/code rename (16 known files + DB filename)
Replace stale identifiers. Distinguish three identifier classes:
- **GitLab project path** `pfh_finance_asset_dashboard` → `tsumi` (URLs, badges, clone cmds).
- **Product/display name** `ETF Dashboard` / `PFH Finance Asset Dashboard` → `Tsumi` (UI titles,
  README H1, FastAPI `title=`, page headers). Keep a subtitle like "ETF & Crypto portfolio".
- **DB filename** `etf_dashboard.duckdb` → `tsumi.duckdb`.

Files to update (from grep on 2026-06-15; re-grep before editing to catch new ones):
- `config.py` (line ~29): default `data/etf_dashboard.duckdb` → `data/tsumi.duckdb`.
- `docker-compose.yml` (~16), `docker-compose.prod.yml` (~27): `DUCKDB_PATH` value.
- `.env.example`, `env.example` (~17): `DUCKDB_PATH`.
- `frontend/app.py`: FastAPI `title=` / Dash title → "Tsumi".
- `frontend/pages/home.py`: page header/branding text.
- `assets/style.css`: any name in comments/branding.
- `tests/test_e2e_smoke.py`: expected title/strings.
- `nginx.conf`: server_name/comments if they reference the old name.
- `README.md`, `CLAUDE.md`, `START_HERE.md`, `GIT_SETUP.md`: product name, repo URL, badges,
  clone commands, structure tree header (`etf-dashboard/` → `tsumi/`).
- `.claude/settings.local.json`, `.claude/launch.json`: any path/name references.

Re-run the grep after edits to confirm zero remaining matches (except where intentionally kept,
e.g. the word "ETF" as a domain term is fine; only the *project identifiers* must change).

> Note: renaming `DUCKDB_PATH` means a fresh empty DB on next start (then seeded). If the user
> wants to keep existing local data, instruct them to `mv data/etf_dashboard.duckdb data/tsumi.duckdb`.
> `.duckdb` is gitignored, so nothing to commit there.

## Phase 4 — GitLab project rename (SAFETY-GATED, shared state)
1. **STOP and ask the user to confirm** the GitLab project rename (changes the URL; existing
   clones/links break until remotes are updated).
2. Rename via `glab` or GitLab UI: Project Settings → General → Advanced →
   - Change **project name** to `Tsumi`.
   - Change **project path/slug** `pfh_finance_asset_dashboard` → `tsumi`
     (GitLab sets up a redirect, but update everything anyway).
3. Update local remote: `git -C tsumi remote set-url origin https://gitlab.com/bambac961/tsumi.git`.
4. Update README badges and all doc links to the new path.
5. Update Wiki Home title and any links.

## Phase 5 — Docs & metadata polish
- README H1 → `# Tsumi` (keep the 積み wordmark optionally), update feature table intro.
- `CLAUDE.md` header + repo URL line → Tsumi.
- Add a short note in `CLAUDE.md` that Tsumi will adopt `@foroba/ui` and migrate Dash→React in SP3
  (forward reference; no action now).
- Keep `pyproject.toml` tooling config; update any `name =` metadata if present.

## Phase 6 — GitLab tracking for SP0 (per the suite workflow)
- Create Milestone **"SP0 — Rename Tsumi"** in the `tsumi` project.
- Create labels if missing: `sp0`, `chore`, `docs`.
- Create the issues below (one per task). Work on branch `feature/sp0-rename-tsumi`.
- Conventional commits closing issues; open an MR using the template; merge `--no-ff` to develop;
  tag (e.g. `v0.x.1`); update Wiki Sprint Review for SP0.

### Issue backlog (create these)
1. `[SP0] Verify and remove duplicate etf-dashboard` (chore) — Phase 1.
2. `[SP0] Rename local folder to tsumi` (chore) — Phase 2.
3. `[SP0] Rename DB path and product identifiers in code/config` (chore) — Phase 3.
4. `[SP0] Rename GitLab project + update remotes/badges/links` (chore) — Phase 4.
5. `[SP0] Update README/CLAUDE/docs to Tsumi branding` (docs) — Phase 5.
6. `[SP0] SP0 Wiki Sprint Review + ADR (React convergence forward-note)` (docs) — Phase 6.

## Acceptance criteria
- [ ] `etf-dashboard/` removed (after user confirm); only `tsumi/` remains.
- [ ] Folder is `tsumi/`; app starts: `uvicorn frontend.app:api --port 8050 --reload`.
- [ ] DB path is `data/tsumi.duckdb`; app boots seeded and navigable.
- [ ] Re-grep shows no stale **project identifiers** (`pfh_finance_asset_dashboard`,
      `etf_dashboard.duckdb`, "PFH Finance Asset Dashboard", "ETF Dashboard" as the product name).
- [ ] GitLab project renamed to `tsumi`; local remote updated; badges/links resolve.
- [ ] CI green; `pytest -m "not integration"` green; lint clean.
- [ ] SP0 Milestone + issues created and closed via the MR; Wiki Sprint Review written.

## Risks / notes
- GitLab rename is shared-state + breaks links → gated on explicit confirm.
- Deleting `etf-dashboard` is irreversible → gated on explicit confirm + diff review.
- Do NOT commit `.env` or `*.duckdb`.
