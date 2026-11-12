import { useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { useAuth } from '../auth/authContext';
import type { ScanJob } from './scanApi';
import { ScanForm } from './ScanForm';
import { ScanResults } from './ScanResults';
import { PastScansPanel } from './PastScansPanel';
import { TargetHistoryPanel } from './TargetHistoryPanel';
import { useScanJob } from './useScanJob';
import { useScanList } from './useScanList';

export function ScansPage() {
  const { request } = useAuth();
  const [search, setSearch] = useSearchParams();
  const selectedId = search.get('run');
  const target = search.get('target') ?? '';
  const selected = useScanJob(request, selectedId);
  const history = useScanList(request);

  // Older shared links contain only a run ID; recover their history target.
  useEffect(() => {
    if (!selected.job || target) return;
    const resolvedTarget = selected.job.target;
    setSearch((previous) => {
      if (previous.has('target')) return previous;
      const next = new URLSearchParams(previous);
      next.set('target', resolvedTarget);
      return next;
    }, { replace: true });
  }, [selected.job?.id, selected.job?.target, target, setSearch]);

  function selectRun(id: string, target: string) {
    setSearch({ run: id, target });
  }

  function selectTarget(target: string) {
    setSearch((previous) => {
      const next = new URLSearchParams(previous);
      next.set('target', target);
      return next;
    });
  }

  function handleCreated(job: ScanJob) {
    selectRun(job.id, job.target);
    history.reload();
  }

  return (
    <section className="scans-page" aria-labelledby="scans-title">
      <header className="dashboard-heading">
        <h1 id="scans-title">Scan dashboard</h1>
        <p>Run a TCP scan, review results, and follow changes across a target’s history.</p>
      </header>
      <div className="dashboard-main">
        <section className="dashboard-panel new-scan" aria-labelledby="new-scan-title">
          <h2 id="new-scan-title">New scan</h2>
          <ScanForm onCreated={handleCreated} />
        </section>
        <div className="dashboard-workspace">
          <section className="dashboard-panel selected-scan" aria-labelledby="scan-result-title">
            <h2 id="scan-result-title">Selected scan</h2>
            {!selectedId && <p>Submit a scan or choose View from Past scans to see its status and results.</p>}
            {selected.loading && <p role="status">Loading scan…</p>}
            {selected.error && <div><p className="error" role="alert">{selected.error}</p><button type="button" onClick={selected.retry}>Retry status check</button></div>}
            {selected.job && <ScanResults job={selected.job} paused={Boolean(selected.error)} />}
          </section>
          <TargetHistoryPanel
            target={target}
            completionKey={selected.job?.status === 'completed' ? selected.job.id : null}
            onTargetChange={selectTarget}
            onSelectRun={selectRun}
          />
        </div>
      </div>
      <PastScansPanel history={history} selectedJob={selected.job} onSelect={selectRun} />
    </section>
  );
}
