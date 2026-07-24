import { fetchJson } from './fetchJson';

const BASE = '/foroba-api';

export type AssetClass = 'crypto' | 'equity';

export interface MarketRating {
  label: string;
  score: number;
}

export interface MarketSentiment {
  score: number;
  label: string;
  positive: number;
  neutral: number;
  negative: number;
  count: number;
}

export interface MarketSnapshot {
  symbol: string;
  asset_class: AssetClass;
  rating: MarketRating | null;
  sentiment: { symbol: string; sentiment: MarketSentiment; sample_headlines?: unknown[] } | null;
  movers: Array<{ symbol: string; change_pct: number }> | null;
  degraded: boolean;
  disclaimer: string;
}

export async function fetchMarketSnapshot(
  symbol: string,
  assetClass: AssetClass,
): Promise<MarketSnapshot> {
  // Backend's screener scan leg can legitimately take up to 12s (sequential
  // OHLCV fetches from Binance/Twelve Data — see markets_service._SCREENER_TIMEOUT),
  // gathered in parallel with the other legs, so the client timeout must clear
  // that worst case with margin or every load falsely reports Tsumi as down.
  const url = `${BASE}/markets/snapshot?symbol=${encodeURIComponent(symbol)}&asset_class=${assetClass}`;
  return fetchJson<MarketSnapshot>(url, { credentials: 'include', timeoutMs: 14000 });
}

export interface MarketMover {
  symbol: string;
  change_pct: number;
}

export interface MarketNews {
  symbol: string;
  items: Array<{ title: string; link: string; published: string; source: string }>;
}

export interface MarketOverview {
  asset_class: AssetClass;
  gainers: MarketMover[] | null;
  losers: MarketMover[] | null;
  news: MarketNews | null;
  degraded: boolean;
  disclaimer: string;
}

export async function fetchMarketOverview(assetClass: AssetClass): Promise<MarketOverview> {
  // Backend gathers gainers+losers scans in parallel (each up to 12s worst
  // case) then fetches news sequentially after (up to 4s more) — see
  // markets_service.fetch_overview. Same rationale as fetchMarketSnapshot above.
  const url = `${BASE}/markets/overview?asset_class=${assetClass}`;
  return fetchJson<MarketOverview>(url, { credentials: 'include', timeoutMs: 18000 });
}
