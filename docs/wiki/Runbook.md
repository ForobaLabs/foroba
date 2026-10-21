# Runbook

# Runbook

Operational procedures for running the Personal Finance HUB suite in production. This
page grows as new operational areas are formalized — start with access control (GL-11.6);
Server Provisioning, Disaster Recovery, and Secrets Inventory sections referenced by other
GL items will be appended here as those items are executed.

## Least-Privilege Operator Access Policy (GL-11.6)

**Principle**: encryption at rest and in transit protects user data against outside
attackers and disk theft. It does **not** protect against the one person who technically
*could* look — the operator running the server. This policy is what makes "no one browses
your data" true against that person too, not just against outsiders.

### Rules
1. **No ad-hoc production database queries.** Any direct read/write against a production
   SQLite/DuckDB file (Pazuru, Foroba, Tsumi) outside of the application's own code paths
   requires a **logged reason** — a comment in the terminal session, a note in the
   incident/issue it relates to, or (preferred) a GitLab issue comment made *before*
   running the query, not after.
2. **The admin panel never exposes raw financial data.** Per GL-10.1: no transaction
   lists, no account balances, no payslip contents, no chat history browsing from the
   admin UI — only aggregate/operational metrics (user counts, error rates, entitlement
   flags) and account-lifecycle actions (suspend, tier change). This is enforced in code,
   not just policy — if a future admin feature would expose financial data, it needs a
   new ADR before merging, not silent scope creep.
3. **No impersonation.** The admin role can act on accounts (suspend, reset) but never
   authenticates *as* a user to view their data.
4. **Support/debugging exception**: if a user explicitly asks for help via Service Desk
   and reproducing the issue requires looking at their actual data, get their explicit
   written consent in that same thread first, and note in the Runbook incident log
   (this section, dated entry) that it happened, why, and what was seen — never do this
   silently.
5. **Backups are encrypted** (R2 offsite, TI-E) and follow the same access rule: pulling a
   backup archive to inspect it locally requires the same logged-reason discipline as a
   live DB query.

### Incident log
(Dated entries go here when rule 4 is invoked. Empty as of 2026-07-31 — no such incident
has occurred.)

## Incident Response — Remote Restart (GL-12.11)

Backend containers occasionally need a restart without a full redeploy (crash loop,
memory pressure, hung connection pool). `restart: unless-stopped` + the `autoheal`
container already recover on crash/unhealthy-status automatically — this section is for
the manual case (an operator decides a service needs a bounce).

### Script
`scripts/restart-service.sh <pazuru|tsumi|foroba|all>` (repo root) — runs ONLY
`docker compose restart <service>` against the prod compose files, nothing else. It
never pulls new images, rebuilds, or runs migrations, so it's safe to expose over SSH
without redeploy risk.

### Remote usage
```bash
ssh -i ~/.ssh/pfh_vps_ed25519 <vps-user>@<vps-ip> \
  'cd /path/to/Personal_Finance_HUB && ./scripts/restart-service.sh <app>'
```

### Checking status first
Before restarting, check `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps`
to see which container is actually unhealthy/stopped — don't restart blindly.

### Monitoring
Uptime Kuma (GL-3.2) runs bound to `127.0.0.1:3001` on the VPS — reach it via
`ssh -L 3001:localhost:3001 <vps-user>@<vps-ip>` then browse `http://localhost:3001`.
Configured to monitor each app's `/health` endpoint plus the VPS host itself.

## Incidents — GDPR 72h Data Breach Response (AD-9, foroba#218)

Written calm, not during a crisis. Covers a suspected personal-data breach affecting any
of the 3 apps (Foroba/Pazuru/Tsumi) — unauthorized access, leak, or loss of user data.

### 1. Assess (first 1-2 hours)
- Confirm it's real: check GlitchTip error spikes, Uptime Kuma anomalies, auth logs
  (unexpected admin logins, mass failed-login patterns, unusual IDOR-shaped request
  patterns), and any external report (user, security researcher).
- Scope: which app(s), which data categories (auth credentials, financial transactions,
  connector tokens, chat history), how many users, since when.
- Classify severity: **confirmed breach** (data actually accessed/exfiltrated) vs
  **near-miss/vulnerability found, no evidence of exploitation** — only the former
  triggers the 72h notification clock.

### 2. Isolate (as soon as scope is understood)
- Rotate anything the attacker could have obtained: JWT signing keys (RS256 keypair,
  `foroba#149`), API keys, connector OAuth tokens (Enable Banking etc.), affected users'
  password hashes (force reset).
- If a specific container/service is compromised: `docker compose stop <service>` (see
  "Remote Restart" section above for SSH access) rather than restart — stopping preserves
  forensic state; only restart once the cause is understood and patched.
- Revoke active sessions suite-wide if session/cookie compromise is suspected
  (`suite_session`/`stepup_<app>` — see MFA/session-hardening architecture).

### 3. Preserve evidence (before remediating, where possible)
- Snapshot relevant logs (GlitchTip, nginx/Caddy access logs, auth audit trail) to a
  location outside the compromised system before any cleanup.
- Note exact timestamps of detection, isolation actions taken, and by whom (solo-operator
  today, but write it as if a team will read it later).

### 4. Notify (72h clock starts at confirmed breach, not at detection of a vulnerability)
- **Supervisory authority**: CNIL (France, applicable jurisdiction) — notify within 72h
  of becoming aware of a **confirmed** breach involving personal data, per GDPR Art. 33.
  If in doubt whether it's reportable, report — the bar is deliberately broad.
- **Affected users**: GDPR Art. 34 requires direct notification "without undue delay" if
  the breach is likely to result in high risk to their rights/freedoms (financial data
  qualifies). Plain-language email: what happened, what data, what we did, what they
  should do (e.g. rotate connector credentials, change password).
- Keep a written record of the decision even if notification is judged unnecessary
  (Art. 33(5) requires documenting all breaches, reportable or not).

### 5. Post-mortem (within 1-2 weeks of resolution)
Template — one entry per incident, appended below:
- **Date / detected by**:
- **Scope** (apps, data categories, user count):
- **Root cause**:
- **Timeline** (detection → isolation → notification → resolution):
- **Remediation shipped** (link GitLab issues/commits):
- **Process gap identified** (what would have caught this sooner):

### Incident log
(Dated entries go here when this runbook is invoked. Empty as of 2026-08-06 — no such
incident has occurred.)

