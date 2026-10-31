/** On-demand Jeli AI interpretation button, ported from Tsumi's shared
 * component (tsumi#144 / R5-1) for use on Foroba pages such as the What-If
 * Simulator (Phase 4 Task 16).
 *
 * Posts a compact text summary of the current page's result to Foroba's own
 * `/jeli/chat` endpoint and streams the answer inline. Always renders an
 * AI-disclaimer alongside the answer — this is a generative interpretation,
 * not financial advice.
 */

import { useState } from 'react';
import {
  AiBadge,
  AiNoticeBanner,
  AiProviderToggle,
  Button,
  Spinner,
  type AiMeta,
} from '@foroba/ui';
import { AI_UPGRADE_HREF } from '../ai/aiApi';
import { readAiMeta } from '../ai/aiMeta';

interface JeliInterpretButtonProps {
  /** Short label identifying the page/section, prefixed into the Jeli prompt
   * (e.g. "Foroba What-If Simulator"). */
  contextLabel: string;
  /** Builds the structured result summary sent to Jeli, computed lazily on click. */
  buildContext: () => string;
}

export function JeliInterpretButton({ contextLabel, buildContext }: JeliInterpretButtonProps) {
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [meta, setMeta] = useState<AiMeta | null>(null);

  async function run() {
    setLoading(true);
    setText('');
    setMeta(null);
    try {
      const res = await fetch('/jeli/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `[Context: ${contextLabel}]\n\n${buildContext()}\n\nInterpret these results in plain language for a retail investor: what do they mean, is this promising, and what are the risks?`,
        }),
      });
      if (!res.ok || !res.body) {
        setText(
          res.status === 401
            ? 'Please log in first — Jeli uses your suite-wide session.'
            : 'Jeli is unavailable. Make sure Ollama and the Foroba backend are running.',
        );
        return;
      }
      setMeta(readAiMeta(res.headers));
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acc = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        acc += decoder.decode(value, { stream: true });
        setText(acc);
      }
    } catch {
      setText('Connection error. Is the Foroba backend running?');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <AiProviderToggle app="foroba" feature="jeli" />
      <Button variant="secondary" onClick={() => void run()} disabled={loading}>
        {loading ? 'Asking Jeli…' : 'Interpret with Jeli'}
      </Button>
      {text !== null && (
        <div className="space-y-1">
          <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm whitespace-pre-wrap text-[var(--color-text-primary)]">
            {text || <Spinner />}
          </div>
          <AiBadge meta={meta} />
          <AiNoticeBanner notice={meta?.notice ?? null} platform="web" upgradeHref={AI_UPGRADE_HREF} />
          <p className="text-xs italic text-[var(--color-text-secondary)]">
            AI-generated interpretation — not financial advice. Verify independently.
          </p>
        </div>
      )}
    </div>
  );
}
