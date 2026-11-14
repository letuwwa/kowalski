import { useState } from 'react';
import type { FormEvent } from 'react';

export type FilterFields = {
  target: string;
  status: string;
  from: string;
  to: string;
};
export function ScanFiltersForm({
  initial,
  onApply,
}: {
  initial: FilterFields;
  onApply: (fields: FilterFields) => void;
}) {
  const [error, setError] = useState('');
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const fields = Object.fromEntries(
      ['target', 'status', 'from', 'to'].map((key) => [
        key,
        String(data.get(key) ?? '').trim(),
      ]),
    ) as FilterFields;
    if (fields.from && fields.to && fields.from > fields.to) {
      setError('The start date must not be after the end date.');
      return;
    }
    setError('');
    onApply(fields);
  }
  return (
    <form className="scan-filters" onSubmit={submit}>
      <div className="field">
        <label htmlFor="filter-target">Target (exact)</label>
        <input
          id="filter-target"
          name="target"
          defaultValue={initial.target}
          placeholder="IP address or hostname"
        />
      </div>
      <div className="field">
        <label htmlFor="filter-status">Status</label>
        <select id="filter-status" name="status" defaultValue={initial.status}>
          <option value="">All statuses</option>
          {['queued', 'running', 'completed', 'failed'].map((status) => (
            <option key={status}>{status}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="filter-from">From date</label>
        <input
          id="filter-from"
          type="date"
          name="from"
          defaultValue={initial.from}
        />
      </div>
      <div className="field">
        <label htmlFor="filter-to">Through date</label>
        <input id="filter-to" type="date" name="to" defaultValue={initial.to} />
      </div>
      <button type="submit">Apply filters</button>
      <button
        type="button"
        onClick={() => onApply({ target: '', status: '', from: '', to: '' })}
      >
        Clear
      </button>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </form>
  );
}
