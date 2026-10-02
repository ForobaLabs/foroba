import { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  EmptyState,
  GoalCard,
  PageContainer,
  SectionHeader,
  formatCurrency,
  suggestMonthlyContribution,
  suggestTargetDate,
  useGoals,
  useUserProfile,
} from '@foroba/ui';
import { parseDecimal } from '../lib/parseDecimal';
import { usePrivacy } from '../contexts/PrivacyContext';
import { GOAL_TITLE_MAX, validateGoal, type GoalField } from './goals/validateGoal';

const inputCls =
  'mt-1 block min-h-11 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-2 text-base text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] aria-[invalid=true]:border-[var(--color-negative)]';
const labelCls = 'block text-sm font-medium text-[var(--color-text-secondary)]';
const errCls = 'mt-1 text-xs text-[var(--color-negative)]';
const primaryBtn =
  'inline-flex min-h-11 items-center justify-center rounded-lg bg-[var(--color-accent)] px-4 text-sm font-semibold text-[var(--color-accent-fg,#fff)] hover:opacity-90 disabled:opacity-40';
const ghostBtn =
  'inline-flex min-h-11 items-center justify-center rounded-lg border border-[var(--color-border)] px-4 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)]';

const NAFORO_APP_URL = import.meta.env.VITE_NAFORO_APP_URL ?? 'http://localhost:5173';

export function GoalsPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const { goals, addGoal, updateGoal, removeGoal } = useGoals();
  const { profile } = useUserProfile();
  const { isPrivate } = usePrivacy();
  const currency = profile.baseCurrency || 'EUR';

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: '', target: '', current: '0', date: '', contribution: '0' });
  const [touched, setTouched] = useState(false);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const refs = useRef<Partial<Record<GoalField, HTMLInputElement | null>>>({});

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const activeGoals = goals.filter((g) => g.status !== 'completed');
  const doneGoals = goals.filter((g) => g.status === 'completed');

  const validation = useMemo(() => validateGoal(form, lang), [form, lang]);
  const err = (f: GoalField) => (touched ? validation.errors[f] : undefined);

  const money = (n: number) => formatCurrency(n, currency, lang, { hidden: isPrivate });

  // Bidirectional live hints: contribution -> date, or deadline -> monthly amount.
  const suggestion = useMemo(() => {
    const { target: rawTarget, current: rawCurrent, contribution: rawContribution, date } = form;
    const target = parseDecimal(rawTarget, lang);
    const current = parseDecimal(rawCurrent || '0', lang) || 0;
    const contribution = parseDecimal(rawContribution || '0', lang) || 0;
    if (!(target > 0)) return null;
    if (contribution > 0 && !date) {
      const reachBy = suggestTargetDate(target, current, contribution);
      return reachBy ? { type: 'date' as const, value: reachBy, contribution } : null;
    }
    if (date && !(contribution > 0) && date > new Date().toISOString().slice(0, 10)) {
      const monthly = suggestMonthlyContribution(target, current, date);
      return monthly !== null ? { type: 'monthly' as const, value: monthly } : null;
    }
    return null;
  }, [form, lang]);

  const fmtDate = (iso: string) => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(lang, { dateStyle: 'medium' });
  };

  const openForm = () => setShowForm(true);
  const closeForm = () => {
    setShowForm(false);
    setTouched(false);
  };

  // Writes go through Naforo; if it is unreachable the hook rejects, so say so instead of failing silently.
  const guarded = async (fn: () => Promise<unknown>): Promise<boolean> => {
    setSaveFailed(false);
    try {
      await fn();
      return true;
    } catch {
      setSaveFailed(true);
      return false;
    }
  };

  const handleAdd = async () => {
    setTouched(true);
    const { values, firstInvalid } = validation;
    if (!values) {
      if (firstInvalid) refs.current[firstInvalid]?.focus();
      return;
    }
    const ok = await guarded(() => addGoal({
      title: values.title,
      // Pazuru's Goal model has no category field yet — every goal is
      // 'other' until (if ever) the upstream schema grows one; a selector
      // here would silently discard the choice, which would be worse.
      category: 'other',
      targetAmount: values.target,
      currentAmount: values.current,
      currency,
      targetDate: values.date,
      monthlyContribution: values.contribution,
    }));
    if (!ok) return;
    setForm({ title: '', target: '', current: '0', date: '', contribution: '0' });
    closeForm();
  };

  const field = (
    id: GoalField,
    label: string,
    props: React.InputHTMLAttributes<HTMLInputElement>,
  ) => {
    const key = err(id);
    return (
      <div className="min-w-0">
        <label htmlFor={`goal-${id}`} className={labelCls}>{label}</label>
        <input
          id={`goal-${id}`}
          ref={(el) => { refs.current[id] = el; }}
          className={inputCls}
          aria-invalid={key ? true : undefined}
          aria-describedby={key ? `goal-${id}-err` : undefined}
          {...props}
        />
        {key && (
          <p id={`goal-${id}-err`} role="alert" className={errCls}>
            {t(`goals.errors.${key}`, { max: GOAL_TITLE_MAX })}
          </p>
        )}
      </div>
    );
  };

  const newButton = (
    <button type="button" onClick={showForm ? closeForm : openForm} className={primaryBtn}>
      + {t('goals.new')}
    </button>
  );

  const renderGoal = (goal: (typeof goals)[number], completed: boolean) => (
    <div key={goal.id}>
      <div className="[overflow-wrap:anywhere]">
        <GoalCard goal={goal} onUpdate={completed ? undefined : (g) => void guarded(() => updateGoal(g.id, g))} />
      </div>
      {confirmId === goal.id ? (
        <div role="alertdialog" aria-label={t('goals.removeAria', { title: goal.title })} className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-[var(--color-negative)]/40 px-3 py-2">
          <p className="min-w-0 flex-1 text-sm text-[var(--color-text-primary)] [overflow-wrap:anywhere]">
            {t('goals.confirmRemove', { title: goal.title })}
          </p>
          <button type="button" className={`${ghostBtn} text-[var(--color-negative)]`} onClick={() => { void guarded(() => removeGoal(goal.id)); setConfirmId(null); }}>
            {t('goals.confirmYes')}
          </button>
          <button type="button" className={ghostBtn} onClick={() => setConfirmId(null)}>{t('goals.keep')}</button>
        </div>
      ) : (
        <div className="mt-1 flex flex-wrap justify-end gap-1">
          {!completed && (
            <button
              type="button"
              aria-label={t('goals.doneAria', { title: goal.title })}
              onClick={() => void guarded(() => updateGoal(goal.id, { currentAmount: goal.targetAmount }))}
              className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg px-3 text-sm font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive)]/10"
            >
              {t('goals.done')}
            </button>
          )}
          <button
            type="button"
            aria-label={t('goals.removeAria', { title: goal.title })}
            onClick={() => setConfirmId(goal.id)}
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg px-3 text-sm font-medium text-[var(--color-negative)] hover:bg-[var(--color-negative)]/10"
          >
            {t('goals.remove')}
          </button>
        </div>
      )}
    </div>
  );

  return (
    <PageContainer>
      <SectionHeader
        as="h1"
        title={t('goals.title')}
        description={t('goals.subtitle')}
        action={newButton}
        className="mb-6 flex-wrap"
      />

      <p data-testid="goals-separate-note" className="mb-4 text-sm text-[var(--color-text-secondary)]">
        {t('goals.separateNote')}{' '}
        <a href={`${NAFORO_APP_URL}/goals`} className="underline">{t('goals.separateLink')}</a>
      </p>

      {saveFailed && (
        <p role="alert" className="mb-4 rounded-lg border border-[var(--color-negative)]/40 px-3 py-2 text-sm text-[var(--color-negative)]">
          {t('goals.saveError')}
        </p>
      )}

      {showForm && (
        <form
          noValidate
          onSubmit={(e) => { e.preventDefault(); void handleAdd(); }}
          className="mb-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5"
        >
          <h2 className="mb-4 text-sm font-semibold text-[var(--color-text-primary)]">{t('goals.newTitle')}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {field('title', t('goals.fields.title'), {
              value: form.title, onChange: set('title'), maxLength: GOAL_TITLE_MAX + 40,
              placeholder: t('goals.fields.titlePlaceholder'), autoComplete: 'off',
            })}
            {field('target', t('goals.fields.target', { cur: currency }), {
              value: form.target, onChange: set('target'), inputMode: 'decimal', placeholder: '5000',
            })}
            {field('current', t('goals.fields.current', { cur: currency }), {
              value: form.current, onChange: set('current'), inputMode: 'decimal', placeholder: '0',
            })}
            {field('date', t('goals.fields.date'), { type: 'date', value: form.date, onChange: set('date') })}
            {field('contribution', t('goals.fields.monthly', { cur: currency }), {
              value: form.contribution, onChange: set('contribution'), inputMode: 'decimal', placeholder: '200',
            })}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="submit" className={primaryBtn}>{t('goals.save')}</button>
            <button type="button" onClick={closeForm} className={ghostBtn}>{t('goals.cancel')}</button>
          </div>

          {suggestion && (
            <div role="status" className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5 px-3 py-2 text-sm">
              <span className="inline-flex shrink-0 items-center rounded-full bg-[var(--color-accent)] px-2 py-0.5 text-[11px] font-semibold text-white">
                {t('goals.suggest.pill')}
              </span>
              <span className="min-w-0 text-[var(--color-text-primary)]">
                {suggestion.type === 'date'
                  ? t('goals.suggest.byDate', { amount: money(suggestion.contribution), date: fmtDate(suggestion.value) })
                  : t('goals.suggest.byMonthly', { amount: money(suggestion.value), date: fmtDate(form.date) })}
              </span>
            </div>
          )}
        </form>
      )}

      {activeGoals.length === 0 && doneGoals.length === 0 && !showForm && (
        <EmptyState
          title={t('goals.empty.title')}
          message={t('goals.empty.message')}
          action={<button type="button" onClick={openForm} className={primaryBtn}>{t('goals.empty.action')}</button>}
        />
      )}

      <div className="space-y-4">{activeGoals.map((g) => renderGoal(g, false))}</div>

      {doneGoals.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            {t('goals.completed')}
          </h2>
          <div className="space-y-4">{doneGoals.map((g) => renderGoal(g, true))}</div>
        </div>
      )}
    </PageContainer>
  );
}
