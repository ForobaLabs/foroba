import { useTranslation } from 'react-i18next';

const KEYS = ['spend', 'net', 'save'] as const;

/** Starter prompts for an empty Jeli panel; clicking one sends it as the first message. */
export function JeliPromptChips({ onPick }: { onPick: (text: string) => void }) {
  const { t } = useTranslation();
  return (
    <div role="group" aria-label={t('jeliChips.label')} className="flex flex-col gap-2 p-3">
      <span className="text-xs text-[var(--color-text-muted)]">{t('jeliChips.label')}</span>
      {KEYS.map((k) => {
        const text = t(`jeliChips.${k}`);
        return (
          <button
            key={k}
            type="button"
            onClick={() => { onPick(text); }}
            className="min-h-[44px] cursor-pointer rounded-[var(--radius-md)] border border-[var(--color-bg-border)] px-3 py-2 text-left text-sm text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-accent-subtle)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            {text}
          </button>
        );
      })}
    </div>
  );
}
