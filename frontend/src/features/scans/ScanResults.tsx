import { Link } from 'react-router';
import { isPending, serviceLabel } from './scanApi';
import type { ScanDetails } from './scanApi';
import { sortedPorts } from './reportPresentation';
import { RunSummary } from './RunSummary';

export function ScanResults({
  job,
  paused,
}: {
  job: ScanDetails;
  paused: boolean;
}) {
  const results = sortedPorts(job.report?.results.tcp ?? []);
  const services = new Map(
    (job.report?.services ?? []).map((row) => [
      `${row.ip_address}:${row.port}`,
      row,
    ]),
  );
  return (
    <>
      <RunSummary job={job} />
      {isPending(job.status) && (
        <p className="scan-note">
          {paused
            ? 'Status updates paused. Retry the status check to continue.'
            : 'Updating automatically. Queued scans will start when the worker is available.'}
        </p>
      )}
      {job.status === 'failed' && (
        <p className="error" role="alert">
          {job.error || 'The scan failed. No completed report was saved.'}
        </p>
      )}
      {job.status === 'completed' &&
        (job.report ? (
          <>
            <div className="table-scroll">
              <table>
                <caption>TCP results · sorted by port</caption>
                <thead>
                  <tr>
                    <th scope="col">IP address</th>
                    <th scope="col">Port</th>
                    <th scope="col">State</th>
                    <th scope="col">Identified service</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((row) => (
                    <tr key={`${row.target}:${row.port}`}>
                      <td className="mono">{row.target}</td>
                      <td className="mono">{row.port}</td>
                      <td>
                        <span className={`status-badge status-${row.state}`}>
                          {row.state}
                        </span>
                      </td>
                      <td>
                        {serviceLabel(
                          services.get(`${row.target}:${row.port}`),
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!results.length && <p>No TCP results were recorded.</p>}
            <div className="panel-actions">
              <Link className="button-link" to={`/scans/${job.id}/report`}>
                Report details
              </Link>
              <Link to={`/history?target=${encodeURIComponent(job.target)}`}>
                View target history
              </Link>
            </div>
            <p className="scan-note">
              Unknown is inconclusive, not closed. Services are identified from
              advertised evidence, not the port number.
            </p>
          </>
        ) : (
          <p className="error" role="alert">
            The completed report is unavailable.
          </p>
        ))}
    </>
  );
}
