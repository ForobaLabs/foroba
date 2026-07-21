import { fetchJson } from './fetchJson';

const BASE = '/foroba-api/reports/monthly';

export interface MonthlyReport {
  id: number;
  yearMonth: string;
  trigger: 'scheduled' | 'manual';
  status: 'pending' | 'generating' | 'success' | 'failed';
  narrativeText: string | null;
  errorMessage: string | null;
  attemptCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface MonthlyReportList {
  items: MonthlyReport[];
  quota: { used: number; limit: number };
}

interface RawReport {
  id: number; year_month: string; trigger: 'scheduled' | 'manual';
  status: 'pending' | 'generating' | 'success' | 'failed';
  narrative_text: string | null; error_message: string | null;
  attempt_count: number; created_at: string; updated_at: string;
}

function reportFromApi(raw: RawReport): MonthlyReport {
  return {
    id: raw.id, yearMonth: raw.year_month, trigger: raw.trigger, status: raw.status,
    narrativeText: raw.narrative_text, errorMessage: raw.error_message,
    attemptCount: raw.attempt_count, createdAt: raw.created_at, updatedAt: raw.updated_at,
  };
}

export async function listMonthlyReports(yearMonth?: string): Promise<MonthlyReportList> {
  const qs = yearMonth ? `?year_month=${encodeURIComponent(yearMonth)}` : '';
  const raw = await fetchJson<{ items: RawReport[]; quota: { used: number; limit: number } }>(
    `${BASE}/${qs}`, { credentials: 'include', timeoutMs: 5000 },
  );
  return { items: raw.items.map(reportFromApi), quota: raw.quota };
}

export async function generateMonthlyReport(yearMonth: string): Promise<MonthlyReport> {
  const raw = await fetchJson<RawReport>(`${BASE}/generate`, {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ year_month: yearMonth }), timeoutMs: 60000,
  });
  return reportFromApi(raw);
}

export async function retryMonthlyReport(id: number): Promise<MonthlyReport> {
  const raw = await fetchJson<RawReport>(`${BASE}/${id}/retry`, {
    method: 'POST', credentials: 'include', timeoutMs: 60000,
  });
  return reportFromApi(raw);
}

export async function downloadMonthlyReportPdf(id: number, yearMonth: string): Promise<void> {
  const resp = await fetch(`${BASE}/${id}/pdf`, { credentials: 'include' });
  if (!resp.ok) throw new Error(`PDF download failed: ${resp.status}`);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `report-${yearMonth}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}
