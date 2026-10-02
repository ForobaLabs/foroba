import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PremiumGate } from '../components/PremiumGate';
import {
  Badge, Button, Card, CardContent, ErrorState, PageContainer, SectionHeader,
  Spinner, useEntitlement,
} from '@foroba/ui';
import { createApiKey, listApiKeys, revokeApiKey, type ApiKey, type ApiKeyCreated } from '../api/apiKeys';
import {
  createWebhook, deleteWebhook, listWebhooks, reactivateWebhook,
  type Webhook, type WebhookCreated,
} from '../api/webhooks';

const inputCls =
  'mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-2 text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]';

export function DeveloperPage() {
  const { t } = useTranslation();
  const { visible, unlocked } = useEntitlement('platform.public_api');

  if (!visible) return null;

  return (
    <PageContainer>
      <SectionHeader as="h1" title={t('developer.title', 'API & Webhooks')} />
      <PremiumGate visible={visible} unlocked={unlocked} feature={t('developer.title', 'API & Webhooks')} description={t('premium.developer')}>
        <div className="space-y-6">
          <ApiKeysPanel />
          <WebhooksPanel />
        </div>
      </PremiumGate>
    </PageContainer>
  );
}

function ApiKeysPanel() {
  const { t } = useTranslation();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [label, setLabel] = useState('');
  const [revealed, setRevealed] = useState<ApiKeyCreated | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(() => {
    listApiKeys().then(setKeys).catch(() => setError(t('developer.loadError', 'Failed to load API keys')));
  }, [t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function create() {
    if (!label) return;
    setLoading(true);
    setError(null);
    try {
      const created = await createApiKey(label);
      setRevealed(created);
      setLabel('');
      refresh();
    } catch {
      setError(t('developer.createKeyError', 'Failed to create API key'));
    } finally {
      setLoading(false);
    }
  }

  async function revoke(id: number) {
    await revokeApiKey(id);
    refresh();
  }

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <h3 className="text-sm font-semibold">{t('developer.apiKeys', 'API keys')}</h3>
        <p className="text-xs text-[var(--color-text-secondary)]">
          {t(
            'developer.apiKeysHelp',
            'Use an API key to call the read-only public API from your own scripts or automation (n8n, Zapier, Home Assistant).',
          )}
        </p>

        {revealed && (
          <div className="space-y-2 rounded-lg border border-[var(--color-accent)] p-3">
            <p className="text-sm font-medium">
              {t('developer.keyRevealTitle', 'Copy this key now — it will not be shown again')}
            </p>
            <code className="block break-all rounded bg-[var(--color-bg-primary)] p-2 text-xs">
              {revealed.key}
            </code>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => navigator.clipboard.writeText(revealed.key)}>
                {t('developer.copy', 'Copy')}
              </Button>
              <Button size="sm" onClick={() => setRevealed(null)}>
                {t('developer.dismiss', 'Dismiss')}
              </Button>
            </div>
          </div>
        )}

        <div className="flex gap-2">
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className={inputCls}
            placeholder={t('developer.keyLabelPlaceholder', 'e.g. n8n workflow')}
          />
          <Button onClick={() => void create()} disabled={!label || loading}>
            {loading ? <Spinner size="sm" /> : t('developer.createKey', 'Create key')}
          </Button>
        </div>

        {error && <ErrorState message={error} />}

        <ul className="space-y-2">
          {keys.map((k) => (
            <li key={k.id} className="flex items-center justify-between gap-2 text-sm">
              <span>
                {k.label} — <code className="text-xs">{k.keyPrefix}</code>
              </span>
              <div className="flex items-center gap-2">
                <Badge variant={k.isActive ? 'positive' : 'default'}>
                  {k.isActive ? t('developer.active', 'Active') : t('developer.revoked', 'Revoked')}
                </Badge>
                {k.isActive && (
                  <button className="text-[var(--color-negative)]" onClick={() => void revoke(k.id)}>
                    {t('developer.revoke', 'Revoke')}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function WebhooksPanel() {
  const { t } = useTranslation();
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [targetUrl, setTargetUrl] = useState('');
  const [revealed, setRevealed] = useState<WebhookCreated | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(() => {
    listWebhooks().then(setWebhooks).catch(() => setError(t('developer.loadWebhooksError', 'Failed to load webhooks')));
  }, [t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function create() {
    if (!targetUrl) return;
    setLoading(true);
    setError(null);
    try {
      const created = await createWebhook(targetUrl);
      setRevealed(created);
      setTargetUrl('');
      refresh();
    } catch {
      setError(t('developer.createWebhookError', 'Failed to create webhook — target URL must use https://'));
    } finally {
      setLoading(false);
    }
  }

  async function remove(id: number) {
    await deleteWebhook(id);
    refresh();
  }

  async function reactivate(id: number) {
    await reactivateWebhook(id);
    refresh();
  }

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <h3 className="text-sm font-semibold">{t('developer.webhooks', 'Webhooks')}</h3>
        <p className="text-xs text-[var(--color-text-secondary)]">
          {t(
            'developer.webhooksHelp',
            'Register an HTTPS URL to receive a push notification whenever a new alert or monthly report is ready.',
          )}
        </p>

        {revealed && (
          <div className="space-y-2 rounded-lg border border-[var(--color-accent)] p-3">
            <p className="text-sm font-medium">
              {t('developer.secretRevealTitle', 'Copy this signing secret now — it will not be shown again')}
            </p>
            <code className="block break-all rounded bg-[var(--color-bg-primary)] p-2 text-xs">
              {revealed.signingSecret}
            </code>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => navigator.clipboard.writeText(revealed.signingSecret)}>
                {t('developer.copy', 'Copy')}
              </Button>
              <Button size="sm" onClick={() => setRevealed(null)}>
                {t('developer.dismiss', 'Dismiss')}
              </Button>
            </div>
          </div>
        )}

        <div className="flex gap-2">
          <input
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            className={inputCls}
            placeholder="https://example.com/webhook"
          />
          <Button onClick={() => void create()} disabled={!targetUrl || loading}>
            {loading ? <Spinner size="sm" /> : t('developer.createWebhook', 'Add webhook')}
          </Button>
        </div>

        {error && <ErrorState message={error} />}

        <ul className="space-y-2">
          {webhooks.map((w) => (
            <li key={w.id} className="flex items-center justify-between gap-2 text-sm">
              <span className="truncate">{w.targetUrl}</span>
              <div className="flex items-center gap-2">
                {w.isActive ? (
                  <Badge variant={w.consecutiveFailures > 0 ? 'default' : 'positive'}>
                    {t('developer.failures', 'Failures')}: {w.consecutiveFailures}
                  </Badge>
                ) : (
                  <Badge variant="negative">{t('developer.disabled', 'Disabled')}</Badge>
                )}
                {w.isActive ? (
                  <button className="text-[var(--color-negative)]" onClick={() => void remove(w.id)}>
                    {t('developer.delete', 'Delete')}
                  </button>
                ) : (
                  <button className="underline" onClick={() => void reactivate(w.id)}>
                    {t('developer.reactivate', 'Reactivate')}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
