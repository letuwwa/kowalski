import type { PortResult, ScanDetails } from './scanApi.ts';

export function sortedPorts(rows: PortResult[]): PortResult[] {
  return [...rows].sort(
    (a, b) =>
      a.port - b.port ||
      a.target.localeCompare(b.target, undefined, { numeric: true }),
  );
}

export function scanTiming(
  job: Pick<ScanDetails, 'started_at' | 'completed_at'>,
): string {
  if (!job.started_at) return 'Not started';
  if (!job.completed_at) return 'In progress';
  const seconds = Math.max(
    0,
    (Date.parse(job.completed_at) - Date.parse(job.started_at)) / 1000,
  );
  if (!Number.isFinite(seconds)) return 'Unavailable';
  if (seconds < 0.001) return '<1 ms';
  return seconds < 1
    ? `${Math.round(seconds * 1000)} ms`
    : `${seconds.toFixed(1)} seconds`;
}

export function displayEvidence(encoded?: string): string {
  if (!encoded) return 'No bytes recorded';
  try {
    return [...atob(encoded)]
      .map((char) => {
        const byte = char.charCodeAt(0);
        return byte >= 32 && byte <= 126
          ? char
          : `\\x${byte.toString(16).padStart(2, '0')}`;
      })
      .join('');
  } catch {
    return 'Evidence encoding is invalid';
  }
}
