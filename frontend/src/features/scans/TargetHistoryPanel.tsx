import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useAuth } from '../auth/authContext';
import { historyDifferences } from './historyDifferences';
import { useTargetHistory } from './useTargetHistory';

type Props = {
  target: string;
  completionKey: string | null;
  onTargetChange: (target: string) => void;
  onSelectRun: (id: string, target: string) => void;
};

export function TargetHistoryPanel({ target, completionKey, onTargetChange, onSelectRun }: Props) {
  const { request } = useAuth();
  const history = useTargetHistory(request, target, completionKey);
  const [draft, setDraft] = useState(target);
  useEffect(() => setDraft(target), [target]);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.trim()) return;
    if (draft.trim() === target) history.reload();
    else onTargetChange(draft.trim());
  }

  return (
    <section className="dashboard-panel target-history" aria-labelledby="target-history-title">
      <div className="panel-heading">
        <h2 id="target-history-title">Target history</h2>
        <button type="button" onClick={history.reload} disabled={!target || history.loading}>Refresh history</button>
      </div>
      <p className="scan-note">Compare consecutive completed scans, oldest first. Failed and pending jobs are excluded.</p>
      <form className="history-search" onSubmit={handleSearch}>
        <div className="field">
          <label htmlFor="history-target">History target</label>
          <input id="history-target" value={draft} onChange={(event) => setDraft(event.target.value)} autoCapitalize="none" spellCheck={false} required />
        </div>
        <button type="submit">Show history</button>
      </form>
      {!target && <p>Select a scan or enter an IPv4 address or hostname to compare its runs.</p>}
      {history.loading && <p role="status">Loading target history…</p>}
      {history.error && <p className="error" role="alert">{history.error}</p>}
      {history.data && <>
        <p className="scan-note">Target: <strong>{history.data.target}</strong></p>
        {!history.loading && !history.data.items.length && <p>No completed scans for this target.</p>}
        <div className="history-timeline">
          {history.data.items.map((item) => {
            const differences = historyDifferences(item);
            const summary = !item.baseline_id ? 'Baseline scan'
              : differences.length ? `${differences.length} recorded difference${differences.length === 1 ? '' : 's'}`
                : item.configuration_changed ? 'Configuration changed' : 'No observed differences';
            return (
              <details key={item.report.id} className="history-entry">
                <summary>
                  <time dateTime={item.report.started_at}>{new Date(item.report.started_at).toLocaleString()}</time>
                  <small className="history-run-id">{item.report.id.slice(0, 8)}</small>
                  <span>{summary}</span>
                </summary>
                <div className="history-entry-body">
                  <p className="scan-note">Run: {item.report.id}</p>
                  {!item.baseline_id ? <p>This is the first completed scan for the target. It establishes a baseline, not newly exposed services.</p>
                    : <p className="scan-note">Compared with run: {item.baseline_id}</p>}
                  {item.configuration_changed && <p className="history-caution">Scan configuration changed. Different ports, timeouts, or identification settings can affect these observations.</p>}
                  {!!differences.length && <div className="table-scroll"><table>
                    <caption>Differences from the previous completed scan</caption>
                    <thead><tr><th scope="col">Observation</th><th scope="col">Destination</th><th scope="col">Previous</th><th scope="col">Current</th><th scope="col">Interpretation</th></tr></thead>
                    <tbody>{differences.map((row) => <tr key={row.key}>
                      <td>{row.observation}</td><td>{row.destination}</td><td>{row.previous}</td><td>{row.current}</td><td>{row.meaning}</td>
                    </tr>)}</tbody>
                  </table></div>}
                  {item.baseline_id && !differences.length && <p>No differences in the observations compared by the API.</p>}
                  <button type="button" onClick={() => onSelectRun(item.report.id, item.report.target)}>View this run</button>
                </div>
              </details>
            );
          })}
        </div>
        {history.data.next_cursor && <button className="panel-action" type="button" onClick={history.loadMore} disabled={history.loading}>Load later scans</button>}
      </>}
      <p className="scan-note">Unknown states are inconclusive. An IP or port missing from a later run does not establish closure. Banner changes do not confirm vulnerabilities.</p>
    </section>
  );
}
