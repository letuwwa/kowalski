import type { ScanDetails } from './scanApi';
import { scanTiming } from './reportPresentation';

export function RunSummary({ job }: { job: ScanDetails }) {
  const results = job.report?.results.tcp;
  return (
    <>
      <div className="run-heading">
        <strong className="target-name">{job.target}</strong>
        <span className={`status-badge status-${job.status}`} role="status">
          {job.status}
        </span>
      </div>
      <dl className="run-meta">
        <div>
          <dt>Submitted</dt>
          <dd>{new Date(job.created_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt>Started</dt>
          <dd>
            {job.started_at
              ? new Date(job.started_at).toLocaleString()
              : 'Not started'}
          </dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{scanTiming(job)}</dd>
        </div>
      </dl>
      {results && (
        <dl className="scan-metrics" aria-label="Selected scan statistics">
          {[
            ['TCP checks', results.length],
            ['Open', results.filter((row) => row.state === 'open').length],
            ['Closed', results.filter((row) => row.state === 'closed').length],
            [
              'Unknown',
              results.filter((row) => row.state === 'unknown').length,
            ],
          ].map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </>
  );
}
