import type { AiMeta } from '@foroba/ui';

/** Parse the `X-AI-*` headers Foroba's `/jeli/chat` sets on every reply (null when absent). */
export function readAiMeta(headers: Headers): AiMeta | null {
  const provider = headers.get('X-AI-Provider');
  if (!provider) return null;
  return {
    provider,
    model: headers.get('X-AI-Model') || null,
    notice: headers.get('X-AI-Notice') || null,
  };
}
