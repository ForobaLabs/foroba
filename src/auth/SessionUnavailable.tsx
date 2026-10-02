import { Button } from '@foroba/ui';
import { useTranslation } from 'react-i18next';

/** Shown when /auth/me cannot be answered (server error, rate limit, offline): not the same as signed out. */
export function SessionUnavailable({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-bg-primary)] p-4">
      <div role="alert" className="flex max-w-sm flex-col items-center gap-3 text-center">
        <h1 className="text-lg font-semibold text-[var(--color-text-primary)]">{t('data.common.sessionUnavailableTitle')}</h1>
        <p className="text-sm text-[var(--color-text-secondary)]">{t('data.common.sessionUnavailableBody')}</p>
        <Button className="min-h-11" onClick={onRetry}>{t('data.common.sessionRetry')}</Button>
      </div>
    </main>
  );
}
