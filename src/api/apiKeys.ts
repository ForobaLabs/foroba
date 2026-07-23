import { fetchJson } from './fetchJson';

const BASE = '/foroba-api/auth/api-keys';

export interface ApiKey {
  id: number;
  label: string;
  keyPrefix: string;
  isActive: boolean;
  lastUsedAt: string | null;
  createdAt: string;
}

export interface ApiKeyCreated extends ApiKey {
  key: string; // "prefix.secret" — shown once
}

interface RawApiKey {
  id: number;
  label: string;
  key_prefix: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
}

function fromApi(raw: RawApiKey): ApiKey {
  return {
    id: raw.id, label: raw.label, keyPrefix: raw.key_prefix, isActive: raw.is_active,
    lastUsedAt: raw.last_used_at, createdAt: raw.created_at,
  };
}

export async function listApiKeys(): Promise<ApiKey[]> {
  const raw = await fetchJson<RawApiKey[]>(BASE, { credentials: 'include', timeoutMs: 5000 });
  return raw.map(fromApi);
}

export async function createApiKey(label: string): Promise<ApiKeyCreated> {
  const raw = await fetchJson<RawApiKey & { key: string }>(BASE, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label }),
    timeoutMs: 5000,
  });
  return { ...fromApi(raw), key: raw.key };
}

export async function revokeApiKey(id: number): Promise<void> {
  await fetchJson<void>(`${BASE}/${id}`, {
    method: 'DELETE', credentials: 'include', timeoutMs: 5000,
  }).catch(() => undefined); // 204 has no body
}
