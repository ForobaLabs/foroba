# Privacy Policy

**[USER ACTION: lawyer — final review required before public beta]**

**Version:** 0.1-draft
**Last updated:** 2026-11-12
**Applies to:** Personal Finance HUB (Foroba, Pazuru, Tsumi)

---

## Who we are

**Hosted instance (operator-run):** The controller of your personal data is the organisation or individual operating this instance of Personal Finance HUB. Contact: [USER ACTION: insert controller name, address, and contact email before launch].

**Self-hosted instance:** If you are running your own instance of Personal Finance HUB, the controller is you (the person running the server). This software project (Foroba Labs) is the software supplier — not your data controller in that scenario.

---

## What data we collect and why

We collect only the data necessary to provide the service.

### Account and authentication data

- **What:** Email address, display name, and security credentials (password stored as a one-way hash using argon2; multi-factor authentication secrets).
- **Why:** To create and manage your account, authenticate you, and protect your account.
- **Legal basis:** Performance of a contract (GDPR art.6(1)(b)).

### Bank account data (Pazuru — if you connect a bank)

- **What:** Bank transaction history, account balances, and account identifiers retrieved from your bank via Enable Banking (a regulated Account Information Service Provider).
- **Why:** To provide spending analysis, budgeting, recurring-payment detection, and financial forecasting.
- **Legal basis:** Performance of a contract.
- **Note:** We do not store your bank login credentials. Your bank's connection is managed through Enable Banking's OAuth consent flow, which gives us a read-only access token.

### Portfolio and market data (Tsumi — if you use the portfolio feature)

- **What:** Your portfolio positions (ETFs, crypto, equities) and trade history that you enter or import.
- **Why:** To compute returns, run analysis, and display your portfolio.
- **Legal basis:** Performance of a contract.
- **Note:** Market data (prices, tickers) is fetched from public sources. No personal data is included in these API calls.

### AI assistant data (Jeli — if you use the chat feature)

- **What:** Your chat messages and, internally, embeddings of your transaction descriptions used to provide contextually relevant responses.
- **Why:** To provide the Jeli AI assistant feature.
- **Legal basis:** Performance of a contract.
- **Important:** By default Jeli runs on our own server with a local AI model and nothing leaves it. If you explicitly opt in to cloud AI for a feature (premium), masked prompts are processed by Cloudflare Workers AI, or by the provider whose API key you supply. Names, e-mail addresses, IBANs and similar identifiers are masked before sending. Consent is per feature and can be withdrawn at any time in Settings; withdrawing stops cloud calls immediately.

### Security monitoring data

- **What:** Login timestamps, failed-login counts, and application error logs (pseudonymous — linked to your internal user ID, not your email, where possible).
- **Why:** To detect and prevent unauthorized access, protect the security of the service, and maintain operational reliability. Error logs are captured by GlitchTip (see processors section below).
- **Legal basis:** Legitimate interests (GDPR art.6(1)(f)) — protecting the security of users' financial data.

### Transactional email

- **What:** Your email address is used to send service-critical communications (e.g., account security notifications, multi-factor authentication codes).
- **Why:** For account security and service operation.
- **Legal basis:** Performance of a contract / legitimate interests.

---

## How long we keep your data

| Data | Retention |
|---|---|
| Account data | Retained while your account is active; deleted within 30 days of account deletion |
| Bank transactions and balances | Retained while your account is active; deleted on account deletion |
| AI chat history | 90 days from creation (rolling deletion); deleted immediately on account deletion |
| Security / auth logs | 12 months from event |
| Session tokens | Deleted on logout or expiry (short-lived) |

When you delete your account, your personal data is removed from our live databases immediately. Because we keep encrypted backups on a 30-day rolling window, deleted data will be absent from all backups within 30 days of deletion.

**Fiscal retention note:** Some jurisdictions require financial records to be retained for tax purposes. If applicable, we will retain only the minimum data required and inform you. [USER ACTION: lawyer — confirm and finalise before launch]

Full details: `data-retention-policy.md` (internal).

---

## Who we share your data with

We use the following service providers (processors) who process personal data on our behalf:

| Processor | Purpose | Location |
|---|---|---|
| Enable Banking Oy | Bank account connection (AISP) | EU (Finland) |
| GlitchTip | Error monitoring (pseudonymous) | [USER ACTION: confirm location] |
| Brevo SAS | Transactional email | EU (France) |
| OVH SAS | Server hosting | EU (France) |
| Cloudflare, Inc. | DNS, static sites, inbound email routing, encrypted backup storage (R2), cloud AI inference (opt-in) | EU bucket for backups; global edge otherwise |
| Paddle | Merchant of record for paid subscriptions (only if you subscribe) | See Paddle's terms |
| AI provider of your choice (OpenAI, Google Gemini, OpenRouter…) | Only if you supply your own API key (BYOK) | Provider-defined |

We do not sell your personal data. We do not share your data with advertisers.

Market data providers (Twelve Data, iTick, Binance, CoinGecko, ECB) receive only public ticker symbols — no personal data.

---

## International transfers

Your personal data is processed within the European Union. Exceptions: opt-in cloud AI (Cloudflare Workers AI or your own provider key) and inbound support mail via Cloudflare Email Routing may involve processing outside the EU; we rely on Standard Contractual Clauses or the EU–US Data Privacy Framework for those transfers.

GlitchTip error monitoring is self-hosted on the same EU server. Cloudflare R2 backup storage uses an EU-region bucket. Both confirmed. See ADR-0004.

---

## Cookies

We use two types of cookies, both strictly necessary:

| Cookie | Purpose |
|---|---|
| `suite_session` | Authentication — keeps you logged in across the app |
| `stepup_pazuru`, `stepup_tsumi` | Step-up authentication — required for sensitive operations (e.g., managing bank connections) |

No advertising or analytics cookies are used. No consent banner is required for strictly necessary cookies.

---

## Your rights

Under GDPR, you have the following rights:

- **Access (art.15):** Request a copy of your personal data.
- **Rectification (art.16):** Correct inaccurate data.
- **Erasure (art.17):** Delete your account and all associated data. You can do this directly in the app under Settings → Security → Delete account.
- **Restriction (art.18):** Request restriction of processing in certain circumstances.
- **Portability (art.20):** Export your data in a machine-readable format (CSV export available in Pazuru).
- **Objection (art.21):** Object to processing based on legitimate interests (security monitoring).
- **Withdraw consent:** Where processing is based on consent, you may withdraw it at any time without affecting the lawfulness of prior processing.

To exercise any right, contact: [USER ACTION: insert contact email before launch]

You also have the right to lodge a complaint with your national data protection authority:
- France: CNIL (cnil.fr)
- Italy: Garante (garanteprivacy.it)

---

## Age restriction

This service is restricted to users aged **18 and older**. By creating an account, you confirm that you are at least 18 years old.

---

## Changes to this policy

We will notify you of material changes to this policy via in-app notification or email before the changes take effect.

---

*This is a technical draft. Final version requires legal review before publication.*
