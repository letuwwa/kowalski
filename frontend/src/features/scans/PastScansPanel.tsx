import type { ScanDetails } from './scanApi';
import type { useScanList } from './useScanList';

type Props = {
  history: ReturnType<typeof useScanList>;
  selectedJob: ScanDetails | null;
  onSelect: (id: string, target: string) => void;
};

export function PastScansPanel({ history, selectedJob, onSelect }: Props) {
  return (
    <section className="dashboard-panel" aria-labelledby="past-scans-title">
      <h2 id="past-scans-title">Past scans</h2>
      <button type="button" onClick={history.reload} disabled={history.loading}>Refresh past scans</button>
      {history.loading && <p role="status">Loading past scans…</p>}
      {history.error && <p className="error" role="alert">{history.error}</p>}
      {!history.loading && !history.error && !history.jobs.length && <p>No scans yet.</p>}
      {history.jobs.length > 0 && <div className="table-scroll"><table>
        <caption>Scan requests, newest first</caption>
        <thead><tr><th scope="col">Target</th><th scope="col">Status</th><th scope="col">Submitted</th><th scope="col">Result</th></tr></thead>
        <tbody>{history.jobs.map((row) => {
          const job = selectedJob?.id === row.id ? selectedJob : row;
          return <tr key={row.id}>
            <td>{job.target}</td><td>{job.status}</td>
            <td><time dateTime={job.created_at}>{new Date(job.created_at).toLocaleString()}</time></td>
            <td><button type="button" aria-label={`View scan ${job.id}`} onClick={() => onSelect(job.id, job.target)}>View</button></td>
          </tr>;
        })}</tbody>
      </table></div>}
      {history.nextCursor && <button type="button" disabled={history.loading} onClick={history.loadMore}>Load more</button>}
    </section>
  );
}
