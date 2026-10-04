import { useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Button,
  EmptyState,
  ErrorState,
  FormField,
  Input,
  LoadingState,
  PageContainer,
  SectionHeader,
  Switch,
} from '@foroba/ui';
import { useHousehold } from '../auth/useHousehold';

const SHARE_RESOURCE_KEYS = ['accounts', 'goals', 'budgets', 'portfolio'] as const;

export function HouseholdPage() {
  const { t } = useTranslation();
  const { household, join, acceptInvite, leave, toggleShare } = useHousehold();
  const joinInputRef = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState('');
  const [joinError, setJoinError] = useState<string | null>(null);
  const [joinSent, setJoinSent] = useState(false);
  const [inviteToken, setInviteToken] = useState('');
  const [acceptError, setAcceptError] = useState<string | null>(null);

  const handleJoin = async (e: FormEvent) => {
    e.preventDefault();
    setJoinError(null);
    try {
      // FOR-D04: this only sends a consent-requiring invite -- the target
      // must accept it (see "Accept an invite" below) before any merge
      // happens, so there is no household to show here yet.
      await join.mutateAsync(email);
      setEmail('');
      setJoinSent(true);
    } catch {
      // Generic on purpose: the raw server message can reveal whether an address has an account.
      setJoinError(t('household.errors.join'));
    }
  };

  const handleAcceptInvite = async (e: FormEvent) => {
    e.preventDefault();
    setAcceptError(null);
    try {
      await acceptInvite.mutateAsync(inviteToken);
      setInviteToken('');
    } catch {
      setAcceptError(t('household.errors.accept'));
    }
  };

  const inHousehold = !!household.data?.household_id;
  const focusInvite = () => {
    joinInputRef.current?.scrollIntoView?.({ block: 'center' });
    joinInputRef.current?.focus();
  };

  return (
    <PageContainer>
      <SectionHeader
        as="h1"
        title={t('household.title')}
        description={t('household.subtitle')}
        action={
          household.data ? (
            <Button type="button" onClick={focusInvite} className="min-h-11">
              {t('household.invite')}
            </Button>
          ) : undefined
        }
        className="mb-6 flex-wrap"
      />
      <div className="mx-auto max-w-lg">
        {household.isLoading ? (
          <LoadingState message={t('household.loading')} />
        ) : household.isError || !household.data ? (
          <ErrorState
            title={t('household.loadError.title')}
            message={t('household.loadError.message')}
            onRetry={() => household.refetch()}
          />
        ) : (
          <>
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
              {inHousehold ? (
                <>
                  <h2 className="mb-3 text-sm font-medium text-[var(--color-text-primary)]">
                    {t('household.members')}
                  </h2>
                  <ul className="mb-4 flex flex-col gap-2">
                    {household.data.members.map((m) => (
                      <li
                        key={m.id}
                        className="flex flex-wrap items-center justify-between gap-x-3 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm [overflow-wrap:anywhere]"
                      >
                        <span className="text-[var(--color-text-primary)]">{m.name}</span>
                        <span className="text-[var(--color-text-muted)]">{m.email}</span>
                      </li>
                    ))}
                  </ul>
                  <Button
                    variant="secondary"
                    className="min-h-11"
                    onClick={() => leave.mutate()}
                    disabled={leave.isPending}
                  >
                    {leave.isPending ? t('household.leaving') : t('household.leave')}
                  </Button>
                  {leave.isError && (
                    <p className="mt-2 text-xs text-[var(--color-negative)]" role="alert">
                      {t('household.errors.leave')}
                    </p>
                  )}
                </>
              ) : (
                <EmptyState title={t('household.empty.title')} message={t('household.empty.message')} />
              )}

              <form onSubmit={handleJoin} className="mt-6 flex flex-col gap-3">
                <FormField label={t('household.joinLabel')} htmlFor="household-join-email">
                  <Input
                    id="household-join-email"
                    ref={joinInputRef}
                    type="email"
                    className="min-h-11 text-base"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      setJoinSent(false);
                    }}
                    placeholder={t('household.joinPlaceholder')}
                    required
                  />
                </FormField>
                <p className="text-xs text-[var(--color-text-muted)]">{t('household.joinHint')}</p>
                {joinError && (
                  <p className="text-xs text-[var(--color-negative)]" role="alert">
                    {joinError}
                  </p>
                )}
                {joinSent && !joinError && (
                  <p className="text-xs text-[var(--color-positive-text)]" role="status">
                    {t('household.joinSent')}
                  </p>
                )}
                <Button type="submit" className="min-h-11" disabled={join.isPending || !email}>
                  {join.isPending ? t('household.joinSending') : t('household.joinSend')}
                </Button>
              </form>

              <form onSubmit={handleAcceptInvite} className="mt-6 flex flex-col gap-3">
                <FormField label={t('household.acceptLabel')} htmlFor="household-invite-token">
                  <Input
                    id="household-invite-token"
                    type="text"
                    className="min-h-11 text-base"
                    value={inviteToken}
                    onChange={(e) => setInviteToken(e.target.value)}
                    placeholder={t('household.acceptPlaceholder')}
                    required
                  />
                </FormField>
                {acceptError && (
                  <p className="text-xs text-[var(--color-negative)]" role="alert">
                    {acceptError}
                  </p>
                )}
                <Button
                  type="submit"
                  variant="secondary"
                  className="min-h-11"
                  disabled={acceptInvite.isPending || !inviteToken}
                >
                  {acceptInvite.isPending ? t('household.acceptSending') : t('household.acceptSend')}
                </Button>
              </form>
            </div>

            <div className="mt-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
              <h2 className="mb-1 text-sm font-medium text-[var(--color-text-primary)]">
                {t('household.sharing')}
              </h2>
              <p className="mb-4 text-xs text-[var(--color-text-muted)]">
                {inHousehold ? t('household.sharingHint') : t('household.sharingNeedsHousehold')}
              </p>
              <ul className="flex flex-col gap-2">
                {SHARE_RESOURCE_KEYS.map((key) => {
                  const label = t(`household.resources.${key}.label`);
                  return (
                    <li key={key} className="flex min-h-11 items-center justify-between gap-4">
                      <label htmlFor={`share-${key}`} className="min-w-0 flex-1 cursor-pointer">
                        <span className="block text-sm text-[var(--color-text-primary)]">{label}</span>
                        <span className="block text-xs text-[var(--color-text-muted)]">
                          {t(`household.resources.${key}.description`)}
                        </span>
                      </label>
                      <Switch
                        id={`share-${key}`}
                        aria-label={t('household.shareToggle', { label })}
                        checked={household.data.share_preferences[key] ?? false}
                        disabled={!inHousehold || toggleShare.isPending}
                        onCheckedChange={(checked) =>
                          toggleShare.mutate({ resourceType: key, shared: checked })
                        }
                      />
                    </li>
                  );
                })}
              </ul>
              {toggleShare.isError && (
                <p className="mt-3 text-xs text-[var(--color-negative)]" role="alert">
                  {t('household.errors.share')}
                </p>
              )}
            </div>

            <p className="mt-4 text-center text-xs text-[var(--color-text-muted)]">{t('household.footer')}</p>
          </>
        )}
      </div>
    </PageContainer>
  );
}
