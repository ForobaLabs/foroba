import { useEffect, useState } from 'react';
import { ProfileEditor, useUserProfile, useSuiteProfile, PageContainer, SectionHeader, FinanceLevelBadge } from '@foroba/ui';

// GL-12: this page only renders within Foroba itself, so nginx's /jeli/*
// proxy (same pattern as src/auth/api.ts) reaches the backend without any
// build-time URL — previously this hardcoded a `localhost:8002` fallback
// that leaked into hosted builds whenever VITE_FOROBA_API_URL wasn't set.

export function ProfilePage() {
  const { profile, updateProfile } = useUserProfile();
  const { profile: suiteProfile, refetch } = useSuiteProfile();
  // Local draft overrides the fetched suite profile while the user is editing;
  // cleared after a successful save so the next render reflects the fresh fetch.
  const [nameDraft, setNameDraft] = useState<{ firstName: string; lastName: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const firstName = nameDraft?.firstName ?? suiteProfile?.firstName ?? '';
  const lastName = nameDraft?.lastName ?? suiteProfile?.lastName ?? '';

  // Auto-generate ID on first visit — must be in useEffect, never in render
  useEffect(() => {
    if (!profile.id) {
      updateProfile({ id: crypto.randomUUID() });
    }
  }, [profile.id, updateProfile]);

  async function saveName() {
    setSaving(true);
    await fetch('/jeli/auth/me/name', {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ first_name: firstName, last_name: lastName }),
    });
    setNameDraft(null);
    await refetch();
    setSaving(false);
  }

  async function uploadAvatar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    await fetch('/jeli/auth/me/avatar', { method: 'POST', credentials: 'include', body: form });
    await refetch();
  }

  return (
    <PageContainer>
      <SectionHeader
        title="Profile"
        description="Your identity is shared across Foroba, Naforo, and Yiriba"
        className="mb-6"
      />

      <div className="mx-auto max-w-lg">
        <div className="mb-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
          <div className="mb-4 flex items-center gap-3">
            {suiteProfile?.avatarUrl ? (
              <img
                src={suiteProfile.avatarUrl}
                alt={suiteProfile.fullName}
                className="h-14 w-14 rounded-full object-cover"
              />
            ) : (
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-accent)] text-lg font-bold text-white">
                {suiteProfile ? `${suiteProfile.firstName.slice(0, 1)}${suiteProfile.lastName.slice(0, 1)}`.toUpperCase() : '?'}
              </div>
            )}
            <label className="text-sm text-[var(--color-accent)] cursor-pointer">
              Change photo
              <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={uploadAvatar} />
            </label>
          </div>
          <div className="flex gap-3">
            <input
              value={firstName}
              onChange={(e) => setNameDraft({ firstName: e.target.value, lastName })}
              placeholder="First name"
              className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
            />
            <input
              value={lastName}
              onChange={(e) => setNameDraft({ firstName, lastName: e.target.value })}
              placeholder="Last name"
              className="w-full rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
            />
          </div>
          <button
            onClick={saveName}
            disabled={saving || !firstName.trim()}
            className="mt-3 rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save name'}
          </button>
        </div>

        <div className="mb-4 flex items-center gap-3">
          <FinanceLevelBadge level={profile.financeLevel} />
        </div>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
          <ProfileEditor profile={profile} onUpdate={updateProfile} />
        </div>

        <p className="mt-4 text-center text-xs text-[var(--color-text-muted)]">
          Preferences below are stored locally on this device. Name and photo above are
          shared across the whole suite.
        </p>
      </div>
    </PageContainer>
  );
}
