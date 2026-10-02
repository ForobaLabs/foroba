import { useCallback, useEffect, useRef, useState } from 'react';
import { simulateWhatIf, type SimulationResult, type WhatIfParams } from '../../api/whatif';

export const PREVIEW_DEBOUNCE_MS = 250;

interface RunState {
  result: SimulationResult | null;
  baseline: SimulationResult | null;
  loading: boolean;
  failed: boolean;
}

/**
 * Live preview: whenever `params` changes (and is not null), waits 250 ms and runs the scenario
 * plus its no-change baseline. Only the newest request may write state, and a failure keeps the
 * last good result visible. `runNow` skips the debounce (Run button, Retry).
 */
export function useScenarioRun(params: WhatIfParams | null) {
  const [state, setState] = useState<RunState>({ result: null, baseline: null, loading: false, failed: false });
  const latest = useRef(0);
  const [nonce, setNonce] = useState(0);
  const immediate = useRef(false);
  const key = params ? JSON.stringify(params) : null;
  const paramsRef = useRef(params);
  useEffect(() => { paramsRef.current = params; });

  useEffect(() => {
    const p = paramsRef.current;
    if (key === null || !p) return;
    const id = ++latest.current;
    const delay = immediate.current ? 0 : PREVIEW_DEBOUNCE_MS;
    immediate.current = false;
    const timer = setTimeout(async () => {
      setState((s) => ({ ...s, loading: true, failed: false }));
      try {
        // Sequential on purpose: concurrent requests trip a backend session-lookup race (spurious 401s).
        const scenario = await simulateWhatIf(p);
        if (id !== latest.current) return;
        const baseline = await simulateWhatIf({ horizonMonths: p.horizonMonths, includeDebts: p.includeDebts });
        if (id !== latest.current) return;
        setState({ result: scenario, baseline, loading: false, failed: false });
      } catch {
        if (id !== latest.current) return;
        setState((s) => ({ ...s, loading: false, failed: true }));
      }
    }, delay);
    return () => clearTimeout(timer);
  }, [key, nonce]);

  const runNow = useCallback(() => {
    immediate.current = true;
    setNonce((n) => n + 1);
  }, []);

  return { ...state, runNow };
}
