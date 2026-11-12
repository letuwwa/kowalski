import { isPending, serviceLabel } from './scanApi';
import type { ScanDetails } from './scanApi';

export function ScanResults({ job, paused }: { job: ScanDetails; paused: boolean }) {
  const results = job.report?.results.tcp ?? [];
  const services = new Map((job.report?.services ?? []).map((row) => [`${row.ip_address}:${row.port}`, row]));

  return (
    <>
      <p role="status">{job.target} — {job.status}</p>
      <p className="scan-note">Run ID: {job.id}</p>
      {isPending(job.status) && <p className="scan-note">{paused
        ? 'Status updates paused. Retry the status check to continue.'
        : 'Updates automatically. The API worker must be running to process queued scans.'}</p>}
      {job.status === 'failed' && <p className="error" role="alert">{job.error || 'The scan failed. No completed report was saved.'}</p>}
      {job.status === 'completed' && (
        job.report ? <>
          <div className="table-scroll">
            <table>
              <caption>TCP results</caption>
              <thead><tr><th scope="col">IP address</th><th scope="col">Port</th><th scope="col">State</th><th scope="col">Identified service</th></tr></thead>
              <tbody>{results.map((row) => (
                <tr key={`${row.target}:${row.port}`}>
                  <td>{row.target}</td><td>{row.port}</td><td>{row.state}</td>
                  <td>{serviceLabel(services.get(`${row.target}:${row.port}`))}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          {!results.length && <p>No TCP results were recorded.</p>}
          <p className="scan-note">Unknown means a timeout or other network error, not a closed port. Service identity comes from an advertised banner; it does not prove a vulnerability.</p>
        </> : <p className="error" role="alert">The completed report is unavailable.</p>
      )}
    </>
  );
}
