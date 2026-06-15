import type { NetWorthSnapshot } from '@foroba/ui';
import { fetchPazuruSummary } from './pazuru';
import { fetchTsumiSummary } from './tsumi';

export async function fetchNetWorth(): Promise<NetWorthSnapshot> {
  const [pazuru, tsumi] = await Promise.all([
    fetchPazuruSummary(),
    fetchTsumiSummary(),
  ]);

  const cashEur = pazuru?.totalBalance ?? 0;
  const portfolioEur = tsumi?.totalValueEur ?? 0;

  return {
    date: new Date().toISOString(),
    totalEur: cashEur + portfolioEur,
    cashEur,
    portfolioEur,
  };
}
