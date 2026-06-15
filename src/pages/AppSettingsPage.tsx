import { SettingsPage } from '@foroba/ui';
import { useUserProfile } from '@foroba/ui';

export function AppSettingsPage() {
  const { profile, updateProfile } = useUserProfile();

  return (
    <SettingsPage
      profile={profile}
      onUpdateProfile={updateProfile}
      onExportData={() => {
        const data = {
          profile,
          exportedAt: new Date().toISOString(),
        };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `foroba-export-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }}
      onDeleteData={() => {
        localStorage.clear();
        window.location.reload();
      }}
      appVersion={__APP_VERSION__}
    />
  );
}

declare const __APP_VERSION__: string;
