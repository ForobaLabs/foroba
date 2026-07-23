import { fetchJson } from './fetchJson';

const BASE = '/foroba-api/auth/webhooks';

export interface Webhook {
  id: number;
  targetUrl: string;
  isActive: boolean;
  consecutiveFailures: number;
  disabledAt: string | null;
  createdAt: string;
}

export interface WebhookCreated extends Webhook {
  signingSecret: string; // shown once
}

interface RawWebhook {
  id: number;
  target_url: string;
  is_active: boolean;
  consecutive_failures: number;
  disabled_at: string | null;
  created_at: string;
}

function fromApi(raw: RawWebhook): Webhook {
  return {
    id: raw.id, targetUrl: raw.target_url, isActive: raw.is_active,
    consecutiveFailures: raw.consecutive_failures, disabledAt: raw.disabled_at, createdAt: raw.created_at,
  };
}

export async function listWebhooks(): Promise<Webhook[]> {
  const raw = await fetchJson<RawWebhook[]>(BASE, { credentials: 'include', timeoutMs: 5000 });
  return raw.map(fromApi);
}

export async function createWebhook(targetUrl: string): Promise<WebhookCreated> {
  const raw = await fetchJson<RawWebhook & { signing_secret: string }>(BASE, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_url: targetUrl }),
    timeoutMs: 5000,
  });
  return { ...fromApi(raw), signingSecret: raw.signing_secret };
}

export async function deleteWebhook(id: number): Promise<void> {
  await fetchJson<void>(`${BASE}/${id}`, {
    method: 'DELETE', credentials: 'include', timeoutMs: 5000,
  }).catch(() => undefined);
}

export async function reactivateWebhook(id: number): Promise<Webhook> {
  const raw = await fetchJson<RawWebhook>(`${BASE}/${id}/reactivate`, {
    method: 'POST', credentials: 'include', timeoutMs: 5000,
  });
  return fromApi(raw);
}
