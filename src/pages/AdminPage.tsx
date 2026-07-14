import React, { useEffect, useState } from 'react';
import {
  AdminFlagsPanel,
  AdminUsersTable,
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

type Tab = 'flags' | 'users' | 'backup' | 'status';

export default function AdminPage(): React.ReactElement {
  const [activeTab, setActiveTab] = useState<Tab>('flags');
  const { settings, loading: flagsLoading, toggle } = useAdminSettings();
  const { users } = useAdminUsers();

  return (
    <PageContainer>
      <SectionHeader
        title="Admin Panel"
        description="Manage feature flags and user accounts"
        className="mb-6"
      />

      {/* Tab bar */}
      <div className="flex gap-2 mb-6 border-b border-[var(--color-border)]">
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'flags'
              ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
              : 'border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
          }`}
          onClick={() => setActiveTab('flags')}
        >
          Flags
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'users'
              ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
              : 'border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
          }`}
          onClick={() => setActiveTab('users')}
        >
          Users
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'backup'
              ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
              : 'border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
          }`}
          onClick={() => setActiveTab('backup')}
        >
          Backup
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'status'
              ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
              : 'border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]'
          }`}
          onClick={() => setActiveTab('status')}
        >
          Status
        </button>
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
        <AdminUsersTable users={users} />
      )}
      {activeTab === 'backup' && <AdminBackupPanel />}
      {activeTab === 'status' && <AdminStatusPanel />}
    </PageContainer>
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
