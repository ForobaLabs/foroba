import { PageContainer, SectionHeader, StatusCard } from '@foroba/ui';
import { useStatusPage } from '../hooks/useStatusPage';

export function StatusPage() {
  const { apps } = useStatusPage();

  return (
    <PageContainer>
      <SectionHeader
        title="System status"
        description="Live status of all Foroba suite services"
        className="mb-6"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {apps.map((app) => (
          <StatusCard
            key={app.name}
            name={app.name}
            status={app.status}
            lastChecked={app.lastChecked}
          />
        ))}
      </div>
    </PageContainer>
  );
}
