/**
 * Legal content for the in-app Legal page.
 * Source: foroba/legal/ (CL-1 compliance drafts, 2026-08-09).
 * DRAFT — pending final review by a qualified lawyer before public launch.
 *
 * These strings are kept here (not in foroba-ui) so they can be updated
 * independently of the design system.
 */

export const PRIVACY_POLICY = {
  title: 'Privacy Policy',
  lastUpdated: '2026-08-09',
  content: `DRAFT — Pending final review by a qualified lawyer before public launch.

WHO WE ARE
The controller of your personal data is the organisation or individual operating this instance of Personal Finance HUB.
Contact: [COMPANY NAME / SUPPORT EMAIL — to be inserted before launch].

In self-hosted mode, the controller is the person running the server. This software project is the software supplier only.

WHAT DATA WE COLLECT AND WHY

Account and authentication data
What: Email address, display name, and security credentials (password stored as a one-way argon2 hash; multi-factor authentication secrets).
Why: To create and manage your account, authenticate you, and protect your account.
Legal basis: Performance of a contract (GDPR art.6(1)(b)).

Bank account data (Pazuru — if you connect a bank)
What: Bank transaction history, account balances, and account identifiers retrieved from your bank via Enable Banking, a regulated Account Information Service Provider.
Why: Spending analysis, budgeting, recurring-payment detection, and financial forecasting.
Legal basis: Performance of a contract.
Note: We do not store your bank login credentials. Your bank connection is managed through Enable Banking's OAuth consent flow, which gives us a read-only access token.

Portfolio and market data (Tsumi — if you use the portfolio feature)
What: Portfolio positions (ETFs, crypto, equities) and trade history you enter or import.
Why: To compute returns, run analysis, and display your portfolio.
Legal basis: Performance of a contract.
Note: Market data (prices, tickers) is fetched from public sources. No personal data is included in these API calls.

AI assistant data (Jeli — if you use the chat feature)
What: Your chat messages and, internally, embeddings of your transaction descriptions.
Why: To provide the Jeli AI assistant feature.
Legal basis: Performance of a contract.
Important: Jeli runs entirely on our server using a local AI model (Ollama). Your financial data and chat messages are never sent to an external AI provider.

Security monitoring data
What: Login timestamps, failed-login counts, and application error logs (pseudonymous — linked to your internal user ID, not your email, where possible). Error logs are captured by GlitchTip, which runs self-hosted on our server.
Why: To detect and prevent unauthorised access and protect the security of the service.
Legal basis: Legitimate interests (GDPR art.6(1)(f)).

HOW LONG WE KEEP YOUR DATA

Bank transactions and balances: retained while your account is active; deleted on account deletion.
AI chat history: 90 days from creation (rolling deletion); deleted immediately on account deletion.
Security / auth logs: 12 months from event.
Session tokens: deleted on logout or expiry (short-lived).
Account data: deleted within 30 days of account deletion.

When you delete your account, your personal data is removed from our live databases immediately. Because we keep encrypted backups on a 30-day rolling window, deleted data will be absent from all backups within 30 days of deletion.

WHO WE SHARE YOUR DATA WITH

Enable Banking Oy — bank account connection (Account Information Service Provider); EU-based (Finland).
Brevo SAS — transactional email (pending); EU-based (France).

GlitchTip error monitoring runs self-hosted on our own server — no data is sent to a third party.
Market data providers (Twelve Data, iTick, Binance, CoinGecko, ECB) receive only public ticker symbols — no personal data.

We do not sell your personal data. We do not share your data with advertisers.

INTERNATIONAL TRANSFERS
Your personal data is processed within the European Union. The AI assistant (Jeli) runs locally on our server — your data is never sent to a US-based or external AI provider. GlitchTip is self-hosted on our EU server. Cloudflare R2 backup storage uses an EU-region bucket.

COOKIES
We use two types of cookies, both strictly necessary:
• suite_session — authentication; keeps you logged in across the app.
• stepup_pazuru / stepup_tsumi — step-up authentication; required for sensitive operations such as managing bank connections.
No advertising or analytics cookies are used.

YOUR RIGHTS
Under GDPR you have the right to: access your data (art.15); correct inaccurate data (art.16); delete your account and all associated data (art.17 — available directly in Settings → Security → Delete account); restrict processing (art.18); export your data in CSV format (art.20 — available in Pazuru); object to processing based on legitimate interests (art.21).

To exercise any right, contact: [SUPPORT EMAIL — to be inserted before launch].

You also have the right to lodge a complaint with your national data protection authority:
• France: CNIL (cnil.fr)
• Italy: Garante (garanteprivacy.it)

AGE RESTRICTION
This service is restricted to users aged 18 and older.

CHANGES TO THIS POLICY
We will notify you of material changes via in-app notification or email before the changes take effect.`,
};

export const TERMS_OF_SERVICE = {
  title: 'Terms of Service',
  lastUpdated: '2026-08-09',
  content: `DRAFT — Pending final review by a qualified lawyer before public launch.

WHO PROVIDES THIS SERVICE
This service is provided by: [COMPANY NAME / REGISTERED ADDRESS — to be inserted before launch].
By creating an account and using this service, you agree to these Terms of Service.

AGE RESTRICTION
This service is for adults aged 18 and older. By creating an account, you confirm you are at least 18 years old.

NOT FINANCIAL ADVICE
Personal Finance HUB is a personal finance management tool, not a financial adviser or regulated financial service (other than in relation to account information as addressed in our regulatory disclosures).

The portfolio analysis, market data, backtesting, AI assistant (Jeli), and any other analytical outputs are for informational and organisational purposes only.

Nothing in this service constitutes investment advice, financial advice, legal advice, or tax advice. Past performance data and backtesting results do not predict or guarantee future performance. Market data may be delayed and may not reflect real-time prices. Do not rely on this data to make financial decisions without verifying with your broker or other authoritative source.

YOUR ACCOUNT
• You are responsible for maintaining the confidentiality of your account credentials.
• You must enable multi-factor authentication as prompted during registration.
• You must not share your account with other people.
• Notify us immediately if you suspect unauthorised access to your account.

YOUR DATA
• You retain ownership of your personal financial data.
• We process your data as described in the Privacy Policy.
• You may export your data at any time (CSV export in Pazuru).
• You may delete your account and all associated data at any time via Settings → Security → Delete account.

BANK CONNECTIONS (PAZURU)
When you connect a bank account, you grant Enable Banking (a regulated Account Information Service Provider) read-only access to your bank data. We do not store your bank login credentials. You can disconnect at any time in Pazuru settings, which revokes access. Bank data accuracy depends on what your bank provides via the Open Banking API — we cannot guarantee completeness or accuracy of imported data.

ACCEPTABLE USE
You must not use this service to: violate any applicable law or regulation; attempt to gain unauthorised access to other users' accounts or data; reverse-engineer or copy the software for commercial use; or upload malicious files.

SERVICE AVAILABILITY
We aim to provide reliable service but do not guarantee 100% uptime. We may perform maintenance that temporarily affects availability.

LIABILITY
[USER ACTION: lawyer — liability limitation clause to be completed before launch in compliance with applicable consumer protection law.]

To the extent permitted by applicable law, we are not liable for decisions you make based on information provided by this service, nor for inaccuracies in market data or bank data provided by third-party sources.

GOVERNING LAW
[USER ACTION: lawyer — governing law and jurisdiction clause to be completed before launch.]

CHANGES TO THESE TERMS
We will notify you of material changes via in-app notification or email at least 30 days before they take effect.

CONTACT
For questions about these terms: [SUPPORT EMAIL — to be inserted before launch].`,
};

export const FISCAL_DISCLAIMER = {
  title: 'Fiscal Disclaimer',
  lastUpdated: '2026-08-09',
  content: `Tax estimates and fiscal information shown in this application are indicative only.

They are NOT tax advice. They are NOT a substitute for professional tax counsel.

Before filing any tax return or making any tax-related decision, please verify all figures with a qualified tax professional:
• Italy: commercialista or consulente fiscale
• France: expert-comptable or conseiller fiscal
• Other jurisdictions: equivalent local tax professional

Tax laws change frequently. Foroba does not guarantee that its tax estimates are up-to-date or applicable to your specific situation.`,
};
