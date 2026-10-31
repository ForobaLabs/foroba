import { createAiApi, type AiRequest } from '@foroba/ui';

/** Same-origin JSON request carrying the suite session cookie. */
const request: AiRequest = async (method, path, body) => {
  const res = await fetch(path, {
    method,
    credentials: 'include',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.status === 204 ? undefined : res.json();
};

/** Prefs, consents, BYOK keys and usage all live behind Foroba's own `/ai` proxy. */
export const aiApi = createAiApi(request, { account: '/jeli/ai' });

/** Foroba web's plans live in the billing section of the profile page. */
export const AI_UPGRADE_HREF = '/profile';
