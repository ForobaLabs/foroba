import { ProfileEditor, useUserProfile, PageContainer, SectionHeader, FinanceLevelBadge } from '@foroba/ui';

export function ProfilePage() {
  const { profile, updateProfile } = useUserProfile();

  // Auto-generate ID on first visit
  if (!profile.id && typeof crypto !== 'undefined') {
    updateProfile({ id: crypto.randomUUID() });
  }

  return (
    <PageContainer>
      <SectionHeader
        title="Profile"
        description="Your personal settings — stored locally on this device"
        className="mb-6"
      />

      <div className="mx-auto max-w-lg">
        <div className="mb-4 flex items-center gap-3">
          {/* Avatar preview */}
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-accent)] text-lg font-bold text-white">
            {profile.name ? profile.name.slice(0, 2).toUpperCase() : '?'}
          </div>
          <div>
            <p className="font-semibold text-[var(--color-text-primary)]">
              {profile.name || 'Your name'}
            </p>
            <FinanceLevelBadge level={profile.financeLevel} />
          </div>
        </div>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
          <ProfileEditor profile={profile} onUpdate={updateProfile} />
        </div>

        <p className="mt-4 text-center text-xs text-[var(--color-text-muted)]">
          All data is stored locally on your device. Nothing is sent to any server.
        </p>
      </div>
    </PageContainer>
  );
}
