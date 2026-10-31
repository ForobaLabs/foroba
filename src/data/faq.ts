import type { FaqItem } from '@foroba/ui';

export const FOROBA_FAQ: FaqItem[] = [
  {
    question: 'What is Kelen?',
    answer:
      'Kelen is your whole-wealth view in the Foroba suite. It brings together your bank accounts (via Naforo), your investment portfolio (via Yiriba), market data, and your AI assistant Jeli in a single place.',
    tags: ['overview', 'about'],
  },
  {
    question: 'How do tiers and audience modes work?',
    answer:
      'Every feature has two independent settings: audience (Base or Expert, controlling how much detail is shown) and tier (Free or Premium, controlling access). You can switch audience mode in Settings, and upgrade your tier from any locked feature.',
    tags: ['tiers', 'premium', 'audience', 'expert'],
  },
  {
    question: 'Why is a feature showing a lock icon?',
    answer:
      'A locked feature requires a Premium tier or Expert audience mode. Hover or click the lock to see which one applies, and use the upgrade button to unlock it.',
    tags: ['locked', 'premium', 'upgrade'],
  },
  {
    question: 'How does Jeli, the AI assistant, work?',
    answer:
      'By default Jeli runs on our own server with a local model (Ollama), so your questions are not sent to any AI provider. In Settings you can choose, per feature, cloud AI (Cloudflare Workers AI) or your own API key; we ask for your consent first and mask names and identifiers before sending. If Jeli appears offline, the local AI model may not be running yet.',
    tags: ['jeli', 'ai', 'assistant', 'privacy'],
  },
  {
    question: 'Is my financial data shared with any external service?',
    answer:
      'No. Foroba, Naforo, and Yiriba are all local-first and self-hosted. Bank sync uses Enable Banking under PSD2; market data comes from public, license-clean sources. AI requests stay on our server unless you opt in to cloud AI or add your own key, per feature, in Settings.',
    tags: ['privacy', 'security', 'data'],
  },
  {
    question: 'How do I switch between light and dark mode?',
    answer:
      'Use the theme toggle in Settings or in the sidebar footer. You can choose Light, Dark, or follow your system preference.',
    tags: ['theme', 'dark mode', 'settings'],
  },
  {
    question: 'What is the Household section for?',
    answer:
      'Household lets you link family members to track shared goals and combined net worth across linked accounts, while keeping each person\'s individual data private by default.',
    tags: ['household', 'family'],
  },
];
