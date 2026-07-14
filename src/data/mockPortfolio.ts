export interface MockPosition {
  id: string;
  symbol: string;
  name: string;
  assetClass: 'ETF' | 'Crypto';
  quantity: number;
  priceEur: number;
  valueEur: number;
  pnlPct: number;
}

export const MOCK_POSITIONS: MockPosition[] = [
  { id: 'pos-1', symbol: 'IE00B4L5Y983', name: 'iShares Core MSCI World', assetClass: 'ETF', quantity: 42, priceEur: 92.18, valueEur: 3871.56, pnlPct: 14.2 },
  { id: 'pos-2', symbol: 'IE00B52MJD48', name: 'iShares MSCI EM', assetClass: 'ETF', quantity: 65, priceEur: 31.4, valueEur: 2041.0, pnlPct: 5.8 },
  { id: 'pos-3', symbol: 'IE00BK5BQT80', name: 'Vanguard FTSE All-World', assetClass: 'ETF', quantity: 28, priceEur: 118.6, valueEur: 3320.8, pnlPct: 9.1 },
  { id: 'pos-4', symbol: 'BTC', name: 'Bitcoin', assetClass: 'Crypto', quantity: 0.045, priceEur: 58200.0, valueEur: 2619.0, pnlPct: 38.6 },
  { id: 'pos-5', symbol: 'ETH', name: 'Ethereum', assetClass: 'Crypto', quantity: 0.92, priceEur: 3120.0, valueEur: 2870.4, pnlPct: 21.3 },
];

export const MOCK_PORTFOLIO_HISTORY: { date: string; valueEur: number }[] = [
  { date: '2026-01-01', valueEur: 11900 },
  { date: '2026-02-01', valueEur: 12150 },
  { date: '2026-03-01', valueEur: 12640 },
  { date: '2026-04-01', valueEur: 13280 },
  { date: '2026-05-01', valueEur: 13905 },
  { date: '2026-06-01', valueEur: 14722.76 },
];
