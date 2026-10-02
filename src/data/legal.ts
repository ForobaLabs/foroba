/**
 * Legal content for Foroba's in-app Legal page.
 * Foroba: suite authentication hub, dashboard, goals, household, portfolio summary, markets.
 * Source: foroba/legal/ (CL-1 compliance drafts, 2026-08-09).
 * DRAFT — pending final review by a qualified lawyer before public launch.
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
What: Email address, display name, and security credentials (password stored as a one-way argon2 hash; multi-factor authentication secrets — TOTP, passkeys/WebAuthn, recovery codes).
Why: To create and manage your account, authenticate you across the suite, and protect your account.
Legal basis: Performance of a contract (GDPR art.6(1)(b)).

Household and goals data
What: Household configuration (shared-view settings with household members) and financial goals you set.
Why: To display your household's financial overview and track progress against your goals.
Legal basis: Performance of a contract.

Portfolio summary and market data
What: Aggregated portfolio data displayed in Foroba's dashboard (sourced from Naforo and Yiriba). Market data (public tickers, prices) fetched from public providers.
Why: To provide a unified financial overview.
Legal basis: Performance of a contract.
Note: Market data API calls carry only public ticker symbols — no personal data is transmitted to market data providers.

Security monitoring data
What: Login timestamps, failed-login counts, MFA attempt logs, and application error logs (pseudonymous — linked to your internal user ID). Error logs are captured by GlitchTip, which runs self-hosted on our server.
Why: To detect and prevent unauthorised access and protect the security of the suite.
Legal basis: Legitimate interests (GDPR art.6(1)(f)).

Transactional email
What: Your email address is used to send service-critical communications (MFA one-time codes, account security notifications).
Why: For account security and service operation.
Legal basis: Performance of a contract / legitimate interests.

HOW LONG WE KEEP YOUR DATA

Account data (profile, MFA secrets): retained while your account is active; deleted on account deletion.
Household and goal data: retained while account is active; deleted on account deletion.
Security / auth logs: 12 months from event.
Session and step-up tokens: deleted on logout or expiry (short-lived).
Account record: deleted within 30 days of account deletion.

When you delete your account, your personal data is removed from our live databases immediately. Because we keep encrypted backups on a 30-day rolling window, deleted data will be absent from all backups within 30 days of deletion.

WHO WE SHARE YOUR DATA WITH

Brevo SAS — transactional email (pending); EU-based (France).
GlitchTip error monitoring runs self-hosted on our own server — no data is sent to a third party.

We do not sell your personal data. We do not share your data with advertisers.

INTERNATIONAL TRANSFERS
Your personal data is processed within the European Union. GlitchTip is self-hosted on our EU server. Cloudflare R2 backup storage uses an EU-region bucket.

COOKIES
We use two types of cookies, both strictly necessary:
• suite_session — authentication; keeps you logged in across all three apps (Foroba, Naforo, Yiriba).
• stepup_pazuru / stepup_tsumi — step-up authentication tokens, issued by Foroba and consumed by satellite apps for sensitive operations.
No advertising or analytics cookies are used.

YOUR RIGHTS
Under GDPR you have the right to: access your data (art.15); correct inaccurate data (art.16); delete your account and all associated data across the suite (art.17 — available directly in Settings → Security → Delete account); restrict processing (art.18); export your data (art.20 — CSV export available in Naforo); object to processing based on legitimate interests (art.21).

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
Personal Finance HUB (Foroba, Naforo, Yiriba) is a personal finance management suite — it is not a financial adviser or regulated financial service (other than in relation to account information as addressed in our regulatory disclosures).

Market data, portfolio summaries, and any analytical outputs are for informational and organisational purposes only. Nothing in this service constitutes investment advice, financial advice, legal advice, or tax advice. Market data may be delayed and may not reflect real-time prices.

YOUR ACCOUNT
• You are responsible for maintaining the confidentiality of your account credentials.
• You must enable multi-factor authentication as prompted during registration — this is mandatory for all accounts.
• You must not share your account with other people.
• Notify us immediately if you suspect unauthorised access to your account.

ACCOUNT DELETION
You may delete your account and all associated data at any time via Settings → Security → Delete account. Deletion is permanent and covers your data across all three apps (Foroba, Naforo, Yiriba). Bank connections (Enable Banking) are revoked immediately on deletion.

YOUR DATA
• You retain ownership of your personal financial data.
• We process your data as described in the Privacy Policy.
• You may export your data at any time (CSV export in Naforo).

SUITE ARCHITECTURE
Foroba acts as the authentication authority for the suite. Your login, MFA, and session tokens are issued by Foroba and shared with Naforo and Yiriba. Account management (password change, MFA settings, account deletion) is performed in Foroba and applies to the entire suite.

ACCEPTABLE USE
You must not use this service to: violate any applicable law or regulation; attempt to gain unauthorised access to other users' accounts or data; reverse-engineer or copy the software for commercial use.

SERVICE AVAILABILITY
We aim to provide reliable service but do not guarantee 100% uptime. We may perform maintenance that temporarily affects availability.

LIABILITY
[USER ACTION: lawyer — liability limitation clause to be completed before launch in compliance with applicable consumer protection law.]

To the extent permitted by applicable law, we are not liable for decisions you make based on information provided by this service.

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
  content: `Tax estimates and fiscal information shown across the Personal Finance HUB suite are indicative only.

They are NOT tax advice. They are NOT a substitute for professional tax counsel.

Before filing any tax return or making any tax-related decision, please verify all figures with a qualified tax professional:
• Italy: commercialista or consulente fiscale
• France: expert-comptable or conseiller fiscal
• Other jurisdictions: equivalent local tax professional

Tax laws change frequently. Personal Finance HUB does not guarantee that its tax estimates are up-to-date or applicable to your specific situation.`,
};
