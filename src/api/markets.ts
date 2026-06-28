const BASE = '/foroba-api';

export type AssetClass = 'crypto' | 'equity';

export interface MarketRating {
  label: string;
  score: number;
}

export interface MarketSnapshot {
  symbol: string;
  asset_class: AssetClass;
  rating: MarketRating | null;
  sentiment: { sentiment?: string; headlines?: unknown[] } | null;
  movers: Array<{ symbol: string; change_pct: number }> | null;
  degraded: boolean;
  disclaimer: string;
}

export async function fetchMarketSnapshot(
  symbol: string,
  assetClass: AssetClass,
): Promise<MarketSnapshot | null> {
  try {
    const url = `${BASE}/markets/snapshot?symbol=${encodeURIComponent(symbol)}&asset_class=${assetClass}`;
    const res = await fetch(url, { credentials: 'include', signal: AbortSignal.timeout(8000) });
    if (!res.ok) return null;
    return (await res.json()) as MarketSnapshot;
  } catch {
    return null;
  }
}
