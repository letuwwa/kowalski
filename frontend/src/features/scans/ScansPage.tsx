import { useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router';
import { useAuth } from '../auth/authContext';
import type { ScanJob } from './scanApi';
import { ScanForm } from './ScanForm';
import { ScanResults } from './ScanResults';
import { PastScansPanel } from './PastScansPanel';
import { ScanFiltersForm } from './ScanFiltersForm';
import type { FilterFields } from './ScanFiltersForm';
import { dateBounds } from './scanFilters';
import { useScanJob } from './useScanJob';
import { useScanList } from './useScanList';

export function ScansPage() {
  const { request } = useAuth();
  const [search, setSearch] = useSearchParams();
  const selectedId = search.get('run');
  const resultPanel = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (selectedId)
      resultPanel.current?.querySelector<HTMLElement>('summary')?.focus();
  }, [selectedId]);
  const fields = {
    target: search.get('target') ?? '',
    status: search.get('status') ?? '',
    from: search.get('from') ?? '',
    to: search.get('to') ?? '',
  };
  let dateError = '';
  let bounds = {};
  try {
    bounds = dateBounds(fields.from, fields.to);
  } catch (error) {
    dateError = (error as Error).message;
  }
  const selected = useScanJob(request, selectedId);
  const history = useScanList(request, {
    target: fields.target,
    status: fields.status,
    ...bounds,
  });

  function selectRun(id: string) {
    setSearch((previous) => {
      const next = new URLSearchParams(previous);
      next.set('run', id);
      return next;
    });
  }
  function handleCreated(job: ScanJob) {
    setSearch({ run: job.id });
    history.reload();
  }
  function applyFilters(fields: FilterFields) {
    const next = new URLSearchParams();
    if (selectedId) next.set('run', selectedId);
    for (const [key, value] of Object.entries(fields))
      if (value) next.set(key, value);
    setSearch(next);
  }
  return (
    <section className="scans-page" aria-labelledby="scans-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Network reconnaissance</p>
          <h1 id="scans-title">Scans</h1>
          <p>Start with a target. Review the evidence. Follow what changes.</p>
        </div>
        <Link className="button-link" to="/history">
          Target history
        </Link>
      </header>
      <section
        className="dashboard-panel new-scan"
        id="new-scan"
        aria-labelledby="new-scan-title"
      >
        <div className="panel-heading">
          <h2 id="new-scan-title">New TCP scan</h2>
          <span className="muted">IPv4 & hostnames</span>
        </div>
        <ScanForm onCreated={handleCreated} />
      </section>
      <section className="dashboard-panel" aria-labelledby="filter-title">
        <h2 id="filter-title">Find a scan</h2>
        <ScanFiltersForm
          key={JSON.stringify(fields)}
          initial={fields}
          onApply={applyFilters}
        />
        {dateError && (
          <p className="error" role="alert">
            {dateError}
          </p>
        )}
      </section>
      {!dateError && (
        <PastScansPanel
          history={history}
          selectedJob={selected.job}
          filtered={Object.values(fields).some(Boolean)}
          onSelect={(id) => selectRun(id)}
        />
      )}
      {selectedId && (
        <details
          ref={resultPanel}
          key={selectedId}
          open
          className="dashboard-panel selected-scan result-expander"
        >
          <summary>
            <span>Selected scan</span>
            <small>{selected.job?.target ?? selectedId.slice(0, 8)}</small>
          </summary>
          <div className="result-body">
            {selected.loading && <p role="status">Loading scan…</p>}
            {selected.error && (
              <div>
                <p className="error" role="alert">
                  {selected.error}
                </p>
                <button type="button" onClick={selected.retry}>
                  Retry status check
                </button>
              </div>
            )}
            {selected.job && (
              <ScanResults
                job={selected.job}
                paused={Boolean(selected.error)}
              />
            )}
          </div>
        </details>
      )}
    </section>
  );
}
