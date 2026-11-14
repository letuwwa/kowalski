import { Link, useParams } from 'react-router';
import { useAuth } from '../auth/authContext';
import { useScanJob } from './useScanJob';
import { RunSummary } from './RunSummary';
import { sortedPorts, displayEvidence } from './reportPresentation';

export function ReportPage() {
  const { id } = useParams();
  const { request } = useAuth();
  const { job, error, loading, retry } = useScanJob(request, id ?? null);
  return (
    <section className="scans-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Scan evidence</p>
          <h1>Report details</h1>
          <p>Connection observations and advertised service information.</p>
        </div>
        <Link
          className="button-link"
          to={`/scans?run=${encodeURIComponent(id ?? '')}`}
        >
          Back to scans
        </Link>
      </header>
      {loading && <p role="status">Loading report…</p>}
      {error && (
        <div className="dashboard-panel">
          <p role="alert" className="error">
            {error}
          </p>
          <button onClick={retry}>Retry</button>
        </div>
      )}
      {job && (
        <>
          <section className="dashboard-panel">
            <RunSummary job={job} />
            <p className="scan-note mono">Run ID: {job.id}</p>
            {job.error && (
              <p className="error" role="alert">
                {job.error}
              </p>
            )}
            {!job.report && (
              <p>A report is available only after successful completion.</p>
            )}
          </section>
          {job.report && (
            <>
              <section className="dashboard-panel">
                <h2>Connection evidence</h2>
                <div className="table-scroll">
                  <table>
                    <caption>Observed TCP connection behavior</caption>
                    <thead>
                      <tr>
                        <th>Destination</th>
                        <th>State</th>
                        <th>Evidence</th>
                        <th>OS error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedPorts(job.report.results.tcp).map((row) => (
                        <tr key={`${row.target}:${row.port}`}>
                          <td className="mono">
                            {row.target}:{row.port}
                          </td>
                          <td>{row.state}</td>
                          <td>{row.evidence || 'Not recorded'}</td>
                          <td>{row.error_number ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <section className="dashboard-panel">
                <h2>Service evidence</h2>
                {!job.report.services?.length && (
                  <p>No service identification observations were recorded.</p>
                )}
                {job.report.services?.map((row) => (
                  <article
                    className="evidence-block"
                    key={`${row.ip_address}:${row.port}`}
                  >
                    <h3 className="mono">
                      {row.ip_address}:{row.port}
                    </h3>
                    <dl className="run-meta">
                      <div>
                        <dt>Identification</dt>
                        <dd>{row.status}</dd>
                      </div>
                      <div>
                        <dt>Protocol</dt>
                        <dd>{row.protocol ?? 'Not identified'}</dd>
                      </div>
                      <div>
                        <dt>Confidence</dt>
                        <dd>{row.confidence ?? 'Not assigned'}</dd>
                      </div>
                    </dl>
                    {row.banner && <pre>{row.banner}</pre>}
                    {row.error && <p>{row.error}</p>}
                    <details>
                      <summary>Received bytes (control bytes escaped)</summary>
                      <pre>{displayEvidence(row.evidence_base64)}</pre>
                    </details>
                  </article>
                ))}
                <p className="scan-note">
                  High confidence describes protocol recognition. Advertised
                  software and versions are self-reported, not confirmed
                  vulnerabilities.
                </p>
              </section>
              <section className="dashboard-panel">
                <h2>Scan configuration</h2>
                <pre>
                  {JSON.stringify(job.report.configuration ?? {}, null, 2)}
                </pre>
              </section>
            </>
          )}
        </>
      )}
    </section>
  );
}
