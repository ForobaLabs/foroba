import React, { useState } from 'react';
import { AdminFlagsPanel, AdminUsersTable, PageContainer, SectionHeader, useAdminSettings, useAdminUsers } from '@foroba/ui';

type Tab = 'flags' | 'users';

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
    </PageContainer>
  );
}
