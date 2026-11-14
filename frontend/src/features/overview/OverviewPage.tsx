import { Link } from 'react-router';
import { useAuth } from '../auth/authContext';
import { useScanList } from '../scans/useScanList';
import { useScanJob } from '../scans/useScanJob';
import { RunSummary } from '../scans/RunSummary';

export function OverviewPage() {
  const { user, request } = useAuth();
  const recent = useScanList(request);
  const latest = useScanJob(request, recent.jobs[0]?.id ?? null);
  const jobs = recent.jobs.map((row) =>
    row.id === latest.job?.id ? latest.job : row,
  );
  return (
    <section className="scans-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Your workspace</p>
          <h1>Overview</h1>
          <p>
            Welcome back{user?.first_name ? `, ${user.first_name}` : ''}. Start
            a scan or pick up where you left off.
          </p>
        </div>
        <Link className="button-link primary" to="/scans#new-scan">
          New scan
        </Link>
      </header>
      {recent.loading && <p role="status">Loading recent activity…</p>}
      {recent.error && (
        <div className="dashboard-panel">
          <p role="alert" className="error">
            {recent.error}
          </p>
          <button onClick={recent.reload}>Retry</button>
        </div>
      )}
      {!recent.loading && !recent.error && !jobs.length && (
        <section className="dashboard-panel empty-state">
          <h2>Your first scan starts here</h2>
          <p>
            Choose an authorized IPv4 address or hostname and the TCP ports you
            want to check.
          </p>
          <Link className="button-link primary" to="/scans">
            Create a scan
          </Link>
        </section>
      )}
      {!!jobs.length && (
        <>
          <section className="dashboard-panel">
            <div className="panel-heading">
              <h2>Recent activity</h2>
              <span className="muted">
                Latest {jobs.length} requests · not lifetime totals
              </span>
            </div>
            <dl className="scan-metrics">
              {['queued', 'running', 'completed', 'failed'].map((status) => (
                <div key={status}>
                  <dt>{status}</dt>
                  <dd>{jobs.filter((job) => job.status === status).length}</dd>
                </div>
              ))}
            </dl>
          </section>
          <div className="overview-grid">
            <section className="dashboard-panel">
              <div className="panel-heading">
                <h2>Latest scan</h2>
                <Link to={`/scans?run=${jobs[0].id}`}>Open results</Link>
              </div>
              {latest.loading && <p role="status">Loading scan…</p>}
              {latest.error && (
                <>
                  <p className="error" role="alert">
                    {latest.error}
                  </p>
                  <button onClick={latest.retry}>Retry</button>
                </>
              )}
              {latest.job && <RunSummary job={latest.job} />}
            </section>
            <section className="dashboard-panel">
              <div className="panel-heading">
                <h2>Recent runs</h2>
                <Link to="/scans">View all</Link>
              </div>
              <ul className="recent-runs">
                {jobs.slice(0, 5).map((job) => (
                  <li key={job.id}>
                    <Link to={`/scans?run=${job.id}`}>
                      <strong className="mono">{job.target}</strong>
                      <small>{new Date(job.created_at).toLocaleString()}</small>
                    </Link>
                    <span className={`status-badge status-${job.status}`}>
                      {job.status}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </>
      )}
    </section>
  );
}
