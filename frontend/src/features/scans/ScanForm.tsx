import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useAuth } from '../auth/authContext';
import { submitScan } from './scanApi';
import type { ScanJob } from './scanApi';
import { scanPayload, PORT_PRESETS } from './scanForm';
import { submissionError } from './scanErrors';

export function ScanForm({ onCreated }: { onCreated: (job: ScanJob) => void }) {
  const { request } = useAuth();
  const [ports, setPorts] = useState('');
  const [preset, setPreset] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const submission = useRef<AbortController | null>(null);
  useEffect(() => () => submission.current?.abort(), []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    const form = new FormData(event.currentTarget);
    let payload;
    try {
      payload = scanPayload(form);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Check the scan options.');
      return;
    }
    const controller = new AbortController();
    submission.current = controller;
    setError('');
    setSubmitting(true);
    try {
      const job = await submitScan(request, payload, controller.signal);
      if (controller.signal.aborted) return;
      onCreated(job);
    } catch (error) {
      if (!controller.signal.aborted) setError(submissionError(error));
    } finally {
      if (!controller.signal.aborted) setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <fieldset disabled={submitting}>
        <legend className="sr-only">New TCP scan</legend>
        <div className="field">
          <label htmlFor="target">Target</label>
          <input id="target" name="target" type="text" autoCapitalize="none" spellCheck={false} required aria-describedby="target-hint" />
          <small id="target-hint">One authorized IPv4 address or hostname. URLs and IPv6 are not supported yet.</small>
        </div>
        <div className="field">
          <label htmlFor="port-preset">Port preset (optional)</label>
          <select id="port-preset" value={preset} onChange={(event) => {
            const value = event.target.value;
            setPreset(value);
            if (value && value !== 'custom') setPorts(value);
          }}>
            <option value="">Choose a preset</option>
            {PORT_PRESETS.map((item) => <option key={item.label} value={item.ports}>{item.label} ({item.ports})</option>)}
            <option value="custom">Custom ports</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="ports">Ports and ranges</label>
          <input id="ports" name="ports" value={ports} onChange={(event) => { setPorts(event.target.value); setPreset('custom'); }} required placeholder="22,80,8000-8010" aria-describedby="ports-hint" />
          <small id="ports-hint">Choose at most 1024 TCP ports. You can edit any preset.</small>
        </div>
        <details>
          <summary>Advanced settings</summary>
          <div className="advanced-settings">
            <div className="field">
              <label htmlFor="timeout">Timeout (seconds)</label>
              <input id="timeout" name="timeout" type="number" min="0" max="5" step="any" defaultValue="1" required aria-describedby="timeout-hint" />
              <small id="timeout-hint">Time allowed per connection or SSH probe. Greater than 0, at most 5.</small>
            </div>
            <div className="field">
              <label htmlFor="concurrency">Concurrency</label>
              <input id="concurrency" name="concurrency" type="number" min="1" max="20" step="1" defaultValue="20" required aria-describedby="concurrency-hint" />
              <small id="concurrency-hint">Maximum simultaneous TCP connections, from 1 to 20.</small>
            </div>
            <div className="field">
              <label htmlFor="rate_limit">Rate limit (connections/second)</label>
              <input id="rate_limit" name="rate_limit" type="number" min="0" max="100" step="any" defaultValue="100" required aria-describedby="rate-hint" />
              <small id="rate-hint">Maximum connection starts per second. Greater than 0, at most 100.</small>
            </div>
          </div>
        </details>
        <small>SSH identification uses the backend default: open port 22, when included in your TCP scan.</small>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit">{submitting ? 'Submitting…' : 'Run scan'}</button>
      </fieldset>
    </form>
  );
}
