import { useEffect, useRef, useState } from 'react';
import { Send } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { JeliMessage } from '../../hooks/useJeli';
import { JeliPromptChips } from '../JeliPromptChips';

interface JeliPanelProps {
  messages: JeliMessage[];
  streaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  onReset: () => void;
}

/** Body of the shell's Jeli drawer: messages + composer. The shell supplies the header and close button. */
export function JeliPanel({ messages, streaming, onSend, onStop, onReset }: JeliPanelProps) {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // jsdom (tests) does not implement scrollIntoView
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [messages]);

  const send = () => {
    if (!input.trim() || streaming) return;
    onSend(input);
    setInput('');
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 flex-col gap-2.5 overflow-y-auto p-4" aria-live="polite">
        {messages.length === 0 && (
          <div className="px-4 py-8 text-center text-[var(--color-text-secondary)]">
            <p className="mb-1 text-sm font-semibold text-[var(--color-text-primary)]">{t('jeli.emptyTitle')}</p>
            <p className="text-sm leading-relaxed">{t('jeli.emptyBody')}</p>
          </div>
        )}
        {messages.length === 0 && !streaming && <JeliPromptChips onPick={onSend} />}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-[var(--color-accent)] text-[var(--color-accent-fg)]'
                  : 'border border-[var(--color-bg-border)] bg-[var(--color-bg-primary)] text-[var(--color-text-primary)]'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="border-t border-[var(--color-bg-border)] p-3">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => { setInput(e.target.value); }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            aria-label={t('jeli.inputLabel')}
            placeholder={t('jeli.placeholder')}
            disabled={streaming}
            className="min-h-[44px] flex-1 rounded-lg border border-[var(--color-bg-border)] bg-[var(--color-bg-primary)] px-3 text-base text-[var(--color-text-primary)]"
          />
          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              className="min-h-[44px] cursor-pointer rounded-lg bg-[var(--color-negative)] px-3 text-sm font-semibold text-white"
            >
              {t('jeli.stop')}
            </button>
          ) : (
            <button
              type="button"
              onClick={send}
              disabled={!input.trim()}
              aria-label={t('jeli.send')}
              className="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-lg bg-[var(--color-accent)] text-[var(--color-accent-fg)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send size={16} aria-hidden="true" />
            </button>
          )}
        </div>
        {messages.length > 0 && (
          <button
            type="button"
            onClick={onReset}
            className="mt-2 min-h-[44px] cursor-pointer text-sm text-[var(--color-text-secondary)] underline"
          >
            {t('jeli.newChat')}
          </button>
        )}
      </div>
    </div>
  );
}
