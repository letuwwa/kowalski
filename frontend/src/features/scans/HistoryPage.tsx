import { Link, useNavigate, useSearchParams } from 'react-router';
import { TargetHistoryPanel } from './TargetHistoryPanel';

export function HistoryPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  return (
    <section className="scans-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Changes over time</p>
          <h1>Target history</h1>
          <p>Compare each completed run with the one before it.</p>
        </div>
        <Link className="button-link" to="/scans">
          Run a scan
        </Link>
      </header>
      <TargetHistoryPanel
        target={search.get('target') ?? ''}
        completionKey={null}
        onTargetChange={(target) => setSearch({ target })}
        onSelectRun={(id) => {
          navigate(`/scans?run=${encodeURIComponent(id)}`);
        }}
      />
    </section>
  );
}
