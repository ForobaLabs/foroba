import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Badge, Button, Card, CardContent, ErrorState, LockedFeature, PageContainer, SectionHeader,
  Spinner, useEntitlement,
} from '@foroba/ui';
import {
  downloadMonthlyReportPdf, generateMonthlyReport, listMonthlyReports, retryMonthlyReport,
  type MonthlyReport,
} from '../api/monthlyReport';

const currentYearMonth = () => new Date().toISOString().slice(0, 7);

const statusVariant: Record<MonthlyReport['status'], 'default' | 'positive' | 'negative' | 'info'> = {
  pending: 'default',
  generating: 'info',
  success: 'positive',
  failed: 'negative',
};

export function MonthlyReportPage() {
  const { t } = useTranslation();
  const { visible, unlocked } = useEntitlement('banking.monthly_ai_report');

  if (!visible) return null;

  return (
    <PageContainer>
      <SectionHeader title={t('monthlyReport.title', 'Monthly Report')} />
      <LockedFeature visible={visible} unlocked={unlocked} label={t('monthlyReport.title', 'Monthly Report')}>
        <MonthlyReportBody />
      </LockedFeature>
    </PageContainer>
  );
}

function MonthlyReportBody() {
  const { t } = useTranslation();
  const [items, setItems] = useState<MonthlyReport[]>([]);
  const [quota, setQuota] = useState({ used: 0, limit: 6 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const list = await listMonthlyReports();
      setItems(list.items);
      setQuota(list.quota);
    } catch {
      setError(t('monthlyReport.loadError', 'Failed to load reports'));
    } finally {
      setLoading(false);
    }
  }

  async function generate() {
    setGenerating(true);
    setError(null);
    try {
      await generateMonthlyReport(currentYearMonth());
      await refresh();
    } catch {
      setError(t('monthlyReport.generateError', 'Failed to generate report'));
    } finally {
      setGenerating(false);
    }
  }

  async function retry(id: number) {
    setError(null);
    try {
      await retryMonthlyReport(id);
      await refresh();
    } catch {
      setError(t('monthlyReport.retryError', 'Failed to retry report'));
    }
  }

  const quotaReached = quota.used >= quota.limit;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex items-center justify-between gap-4 p-4">
          <span className="text-sm text-[var(--color-text-secondary)]">
            {t('monthlyReport.quota', 'Reports this month')}: {quota.used} / {quota.limit}
          </span>
          <Button
            onClick={() => void generate()}
            disabled={generating || quotaReached}
            title={quotaReached ? t('monthlyReport.quotaReached', 'Monthly limit reached') : undefined}
          >
            {generating ? <Spinner size="sm" /> : t('monthlyReport.generate', 'Generate')}
          </Button>
        </CardContent>
      </Card>

      {error && <ErrorState message={error} />}

      {loading ? (
        <Spinner size="sm" />
      ) : (
        <div className="space-y-4">
          {items.map((report) => (
            <Card key={report.id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{report.yearMonth}</span>
                  <Badge variant={statusVariant[report.status]}>{report.status}</Badge>
                </div>
                {report.status === 'success' && report.narrativeText && (
                  <p className="text-sm whitespace-pre-wrap">{report.narrativeText}</p>
                )}
                {report.status === 'failed' && report.errorMessage && (
                  <p className="text-sm text-[var(--color-negative)]">{report.errorMessage}</p>
                )}
                <div className="flex gap-2">
                  {report.status === 'failed' && (
                    <Button size="sm" onClick={() => void retry(report.id)}>
                      {t('monthlyReport.retry', 'Retry')}
                    </Button>
                  )}
                  {report.status === 'success' && (
                    <Button
                      size="sm"
                      onClick={() => void downloadMonthlyReportPdf(report.id, report.yearMonth)}
                    >
                      {t('monthlyReport.downloadPdf', 'Download PDF')}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
