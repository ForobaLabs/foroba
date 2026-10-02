import { Link, isRouteErrorResponse, useRouteError } from 'react-router';
import { useTranslation } from 'react-i18next';
import { EmptyState, PageContainer } from '@foroba/ui';

const linkCls =
  'inline-flex min-h-11 items-center justify-center rounded-lg bg-[var(--color-accent)] px-4 text-sm font-semibold text-[var(--color-accent-fg,#fff)] hover:opacity-90';

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <PageContainer>
      <h1 className="sr-only">{t('notFound.title')}</h1>
      <EmptyState
        title={t('notFound.title')}
        message={t('notFound.message')}
        action={<Link to="/" className={linkCls}>{t('notFound.home')}</Link>}
      />
    </PageContainer>
  );
}

/** Router-level errorElement: replaces React Router's developer-facing default screen. */
export function RouteError() {
  const { t } = useTranslation();
  const err = useRouteError();
  const missing = isRouteErrorResponse(err) && err.status === 404;
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-primary)] p-4">
      <div role="alert" className="max-w-sm text-center">
        <h1 className="mb-2 text-xl font-semibold text-[var(--color-text-primary)]">
          {missing ? t('notFound.title') : t('notFound.errorTitle')}
        </h1>
        <p className="mb-6 text-sm text-[var(--color-text-secondary)]">
          {missing ? t('notFound.message') : t('notFound.errorMessage')}
        </p>
        <a href="/" className={linkCls}>{t('notFound.home')}</a>
      </div>
    </div>
  );
}
