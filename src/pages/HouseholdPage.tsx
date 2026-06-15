import { HouseholdManager, PageContainer, SectionHeader, useHousehold } from '@foroba/ui';

export function HouseholdPage() {
  const { household, updateHousehold } = useHousehold();

  return (
    <PageContainer>
      <SectionHeader
        title="Household"
        description="Manage your household members — stored locally on this device"
        className="mb-6"
      />

      <div className="mx-auto max-w-lg">
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
          <HouseholdManager household={household} onUpdate={updateHousehold} />
        </div>

        <p className="mt-4 text-center text-xs text-[var(--color-text-muted)]">
          All data is stored locally on your device. Nothing is sent to any server.
        </p>
      </div>
    </PageContainer>
  );
}
