import React, { useEffect, useState } from 'react';
import {
  AdminFlagsPanel,
  AdminUsersTable,
  KpiCard,
  PageContainer,
  SectionHeader,
  StatusCard,
  useAdminSettings,
  useAdminUsers,
} from '@foroba/ui';
import type { HealthStatus } from '@foroba/ui';
import { fetchForobaHealthDetailed } from '../api/foroba';
import type { DetailedHealth } from '../api/foroba';
import { fetchPazuruHealthDetailed } from '../api/pazuru';
import { fetchTsumiHealthDetailed } from '../api/tsumi';
import { useAuth } from '../auth/AuthProvider';

type Tab = 'flags' | 'users' | 'invites' | 'kpis' | 'backup' | 'status';

const TABS: { id: Tab; label: string }[] = [
  { id: 'flags', label: 'Flags' },
  { id: 'users', label: 'Users' },
  { id: 'invites', label: 'Invites' },
  { id: 'kpis', label: 'KPIs' },
  { id: 'backup', label: 'Backup' },
  { id: 'status', label: 'Status' },
];

export default function AdminPage(): React.ReactElement {
  const [activeTab, setActiveTab] = useState<Tab>('flags');
  const { settings, loading: flagsLoading, toggle } = useAdminSettings();
  const { users, setAccountDisabled } = useAdminUsers();
  const { user } = useAuth();

  return (
    <PageContainer>
      <SectionHeader
        title="Admin Panel"
        description="Manage feature flags and user accounts"
        className="mb-6"
      />

      {/* Tab bar */}
      <div className="flex gap-2 mb-6 border-b border-[var(--color-border)]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
                : 'border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'flags' && (
        <AdminFlagsPanel
          settings={settings}
          onToggle={toggle}
          loading={flagsLoading}
        />
      )}
      {activeTab === 'users' && (
        <AdminUsersTable
          users={users}
          currentUserId={user?.id}
          onSetAccountDisabled={setAccountDisabled}
        />
      )}
      {activeTab === 'invites' && <AdminInvitesPanel />}
      {activeTab === 'kpis' && <AdminKpisPanel />}
      {activeTab === 'backup' && <AdminBackupPanel />}
      {activeTab === 'status' && <AdminStatusPanel />}
    </PageContainer>
  );
}

interface InviteCode {
  id: number;
  code: string;
  note: string | null;
  max_uses: number;
  uses_count: number;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

function AdminInvitesPanel(): React.ReactElement {
  const [codes, setCodes] = useState<InviteCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [note, setNote] = useState('');
  const [maxUses, setMaxUses] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const res = await fetch('/jeli/admin/invite-codes');
    if (res.ok) setCodes(await res.json());
  }

  useEffect(() => {
    fetch('/jeli/admin/invite-codes')
      .then((r) => (r.ok ? r.json() : []))
      .then((data: InviteCode[]) => setCodes(data))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch('/jeli/admin/invite-codes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: note || undefined, max_uses: maxUses }),
      });
      if (!res.ok) throw new Error(`Failed to create invite code (${res.status})`);
      setNote('');
      setMaxUses(1);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create invite code');
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(id: number) {
    setError(null);
    try {
      const res = await fetch(`/jeli/admin/invite-codes/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`Failed to revoke invite code (${res.status})`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke invite code');
    }
  }

  if (loading) return <p>Loading…</p>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="block text-xs text-[var(--color-text-secondary)] mb-1">Note</label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. beta batch 1"
            className="px-3 py-2 rounded border border-[var(--color-border)] bg-transparent text-[var(--color-text-primary)]"
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--color-text-secondary)] mb-1">Max uses</label>
          <input
            type="number"
            min={1}
            value={maxUses}
            onChange={(e) => setMaxUses(Number(e.target.value))}
            className="w-24 px-3 py-2 rounded border border-[var(--color-border)] bg-transparent text-[var(--color-text-primary)]"
          />
        </div>
        <button
          onClick={handleCreate}
          disabled={busy}
          className="px-4 py-2 rounded bg-[var(--color-accent)] text-white text-sm font-medium disabled:opacity-50"
        >
          {busy ? 'Creating…' : 'Generate code'}
        </button>
      </div>
      {error && <p role="alert" className="text-sm text-[var(--color-negative)]">{error}</p>}

      {codes.length === 0 ? (
        <p>No invite codes yet.</p>
      ) : (
        <table aria-label="Invite codes" className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wide text-[var(--color-text-secondary)]">
              <th className="py-2 pr-4">Code</th>
              <th className="py-2 pr-4">Note</th>
              <th className="py-2 pr-4">Uses</th>
              <th className="py-2 pr-4">Expires</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4">Action</th>
            </tr>
          </thead>
          <tbody>
            {codes.map((c) => (
              <tr key={c.id} className="border-b border-[var(--color-border)] text-[var(--color-text-primary)]">
                <td className="py-2 pr-4">
                  <code className="rounded bg-black/20 px-1.5 py-0.5">{c.code}</code>
                </td>
                <td className="py-2 pr-4">{c.note ?? '—'}</td>
                <td className="py-2 pr-4 tabular-nums">{c.uses_count}/{c.max_uses}</td>
                <td className="py-2 pr-4">{c.expires_at ?? 'Never'}</td>
                <td className="py-2 pr-4">
                  <span
                    className={
                      c.revoked_at
                        ? 'text-[var(--color-negative)]'
                        : 'text-[var(--color-positive)]'
                    }
                  >
                    {c.revoked_at ? 'Revoked' : 'Active'}
                  </span>
                </td>
                <td className="py-2 pr-4">
                  {!c.revoked_at && (
                    <button
                      type="button"
                      onClick={() => handleRevoke(c.id)}
                      className="text-[var(--color-negative)] underline underline-offset-2"
                    >
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

interface AdminKpis {
  total_users: number;
  users_by_tier: Record<string, number>;
  users_by_audience: Record<string, number>;
  signups_last_7d: number;
  signups_last_30d: number;
  mfa_enrolled: number;
  mfa_enrollment_pending: number;
  accounts_disabled: number;
  admins: number;
}

function AdminKpisPanel(): React.ReactElement {
  const [kpis, setKpis] = useState<AdminKpis | null>(null);

  useEffect(() => {
    fetch('/jeli/admin/kpis')
      .then((r) => r.json())
      .then(setKpis);
  }, []);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <KpiCard label="Total users" value={String(kpis?.total_users ?? 0)} loading={!kpis} />
      <KpiCard label="Admins" value={String(kpis?.admins ?? 0)} loading={!kpis} />
      <KpiCard label="Signups (7d)" value={String(kpis?.signups_last_7d ?? 0)} loading={!kpis} />
      <KpiCard label="Signups (30d)" value={String(kpis?.signups_last_30d ?? 0)} loading={!kpis} />
      <KpiCard label="MFA enrolled" value={String(kpis?.mfa_enrolled ?? 0)} loading={!kpis} />
      <KpiCard
        label="MFA pending"
        value={String(kpis?.mfa_enrollment_pending ?? 0)}
        loading={!kpis}
      />
      <KpiCard label="Accounts disabled" value={String(kpis?.accounts_disabled ?? 0)} loading={!kpis} />
      <KpiCard
        label="By tier"
        value={
          kpis
            ? Object.entries(kpis.users_by_tier)
                .map(([k, v]) => `${k}: ${v}`)
                .join(', ')
            : '—'
        }
        loading={!kpis}
      />
    </div>
  );
}

function AdminBackupPanel(): React.ReactElement {
  const [exportPassphrase, setExportPassphrase] = useState('');
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const [importPassphrase, setImportPassphrase] = useState('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<Record<string, unknown> | null>(null);

  async function handleExport() {
    setExportBusy(true);
    setExportError(null);
    try {
      const resp = await fetch('/jeli/admin/backup/export-suite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ passphrase: exportPassphrase }),
      });
      if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `pfh-backup-${Date.now()}.pfhbak`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setExportBusy(false);
    }
  }

  async function handleImport() {
    if (!importFile) return;
    const confirmed = window.confirm(
      'This will overwrite live data on all 3 apps (Foroba, Pazuru, Tsumi). Continue?'
    );
    if (!confirmed) return;

    setImportBusy(true);
    setImportError(null);
    setImportResult(null);
    try {
      const form = new FormData();
      form.append('file', importFile);
      form.append('passphrase', importPassphrase);
      const resp = await fetch('/jeli/admin/backup/import-suite', {
        method: 'POST',
        credentials: 'same-origin',
        body: form,
      });
      if (!resp.ok) throw new Error(`Restore failed (${resp.status})`);
      setImportResult(await resp.json());
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Restore failed');
    } finally {
      setImportBusy(false);
    }
  }

  return (
    <div className="space-y-8 max-w-xl">
      <section>
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-2">Export backup</h3>
        <p className="text-sm text-[var(--color-text-secondary)] mb-3">
          Downloads one encrypted file containing Foroba, Pazuru, and Tsumi data.
          The passphrase is never stored anywhere — write it down, you'll need it to restore.
        </p>
        <input
          type="password"
          value={exportPassphrase}
          onChange={(e) => setExportPassphrase(e.target.value)}
          placeholder="Backup passphrase"
          className="w-full mb-2 px-3 py-2 rounded border border-[var(--color-border)] bg-transparent text-[var(--color-text-primary)]"
        />
        <button
          onClick={handleExport}
          disabled={exportBusy || !exportPassphrase}
          className="px-4 py-2 rounded bg-[var(--color-accent)] text-white text-sm font-medium disabled:opacity-50"
        >
          {exportBusy ? 'Exporting…' : 'Export backup'}
        </button>
        {exportError && <p className="text-sm text-[var(--color-negative)] mt-2">{exportError}</p>}
      </section>

      <section>
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-2">Restore backup</h3>
        <p className="text-sm text-[var(--color-text-secondary)] mb-3">
          Overwrites live data on all 3 apps. All 3 backends need a manual restart after restoring.
        </p>
        <input
          type="file"
          accept=".pfhbak"
          onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
          className="w-full mb-2 text-sm text-[var(--color-text-primary)]"
        />
        <input
          type="password"
          value={importPassphrase}
          onChange={(e) => setImportPassphrase(e.target.value)}
          placeholder="Backup passphrase"
          className="w-full mb-2 px-3 py-2 rounded border border-[var(--color-border)] bg-transparent text-[var(--color-text-primary)]"
        />
        <button
          onClick={handleImport}
          disabled={importBusy || !importFile || !importPassphrase}
          className="px-4 py-2 rounded bg-[var(--color-negative)] text-white text-sm font-medium disabled:opacity-50"
        >
          {importBusy ? 'Restoring…' : 'Restore backup'}
        </button>
        {importError && <p className="text-sm text-[var(--color-negative)] mt-2">{importError}</p>}
        {importResult && (
          <pre className="text-xs mt-3 p-3 rounded bg-[var(--color-surface)] border border-[var(--color-border)] overflow-auto">
            {JSON.stringify(importResult, null, 2)}
          </pre>
        )}
      </section>
    </div>
  );
}

function toHealthStatus(backendStatus: string): HealthStatus {
  if (backendStatus === 'ok') return 'ok';
  if (backendStatus === 'degraded') return 'down';
  return 'unreachable';
}

function AdminStatusPanel(): React.ReactElement {
  const [apps, setApps] = useState<
    { name: string; health: DetailedHealth; lastChecked: string }[]
  >([]);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      const [foroba, pazuru, tsumi] = await Promise.allSettled([
        fetchForobaHealthDetailed(),
        fetchPazuruHealthDetailed(),
        fetchTsumiHealthDetailed(),
      ]);
      if (cancelled) return;

      const unavailable: DetailedHealth = { status: 'unavailable', dependencies: {} };
      setApps([
        { name: 'Foroba', health: foroba.status === 'fulfilled' ? foroba.value : unavailable, lastChecked: new Date().toISOString() },
        { name: 'Pazuru', health: pazuru.status === 'fulfilled' ? pazuru.value : unavailable, lastChecked: new Date().toISOString() },
        { name: 'Tsumi', health: tsumi.status === 'fulfilled' ? tsumi.value : unavailable, lastChecked: new Date().toISOString() },
      ]);
    }

    void refresh();
    const id = setInterval(() => void refresh(), 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {apps.map(({ name, health, lastChecked }) => (
        <StatusCard
          key={name}
          name={name}
          status={toHealthStatus(health.status)}
          lastChecked={lastChecked}
        >
          {Object.entries(health.dependencies).map(([depName, dep]) => (
            <div key={depName} className="flex items-center justify-between text-xs">
              <span className="text-[var(--color-text-secondary)] capitalize">{depName}</span>
              <span
                className={
                  dep.status === 'ok'
                    ? 'text-[var(--color-positive)]'
                    : dep.status === 'degraded'
                      ? 'text-[var(--color-warning)]'
                      : 'text-[var(--color-text-muted)]'
                }
              >
                {dep.status}
              </span>
            </div>
          ))}
        </StatusCard>
      ))}
    </div>
  );
}
