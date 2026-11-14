import type { ScanFilters } from './scanFilters.ts';
import type { AuthenticatedRequest } from '../auth/authenticatedRequest.ts';

export type ScanStatus = 'queued' | 'running' | 'completed' | 'failed';
export type ScanJob = {
  id: string;
  target: string;
  status: ScanStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
};
export type PortResult = {
  target: string;
  port: number;
  state: 'open' | 'closed' | 'unknown';
  evidence?: string;
  error_number?: number | null;
};
export type ServiceResult = {
  ip_address: string;
  port: number;
  status: string;
  protocol: string | null;
  advertised_software: string | null;
  banner?: string | null;
  confidence?: string | null;
  error?: string | null;
  evidence_base64?: string;
};
export type ScanReport = {
  id?: string;
  started_at?: string;
  completed_at?: string;
  configuration?: Record<string, unknown>;
  results: { tcp: PortResult[] };
  services?: ServiceResult[];
};
export type ScanDetails = ScanJob & { report: ScanReport | null };
export type ScanList = { items: ScanJob[]; next_cursor: string | null };
export type ScanSubmission = {
  target: string;
  ports: number[];
  timeout: number;
  concurrency: number;
  rate_limit: number;
};

export function submitScan(
  request: AuthenticatedRequest,
  payload: ScanSubmission,
  signal?: AbortSignal,
): Promise<ScanJob> {
  return request('/scans', {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function getScan(
  request: AuthenticatedRequest,
  id: string,
  signal: AbortSignal,
): Promise<ScanDetails> {
  return request(`/scans/${encodeURIComponent(id)}`, { signal });
}

export function listScans(
  request: AuthenticatedRequest,
  signal: AbortSignal,
  cursor?: string,
  filters: ScanFilters = {},
): Promise<ScanList> {
  const params = new URLSearchParams({ limit: '20' });
  for (const [name, value] of Object.entries(filters))
    if (value) params.set(name, value);
  if (cursor) params.set('cursor', cursor);
  return request(`/scans?${params}`, { signal });
}

export function isPending(status: ScanStatus): boolean {
  return status === 'queued' || status === 'running';
}

export function serviceLabel(service?: ServiceResult): string {
  if (!service) return 'Not checked';
  if (service.status !== 'identified')
    return `Not identified (${service.status})`;
  return [service.protocol?.toUpperCase(), service.advertised_software]
    .filter(Boolean)
    .join(' · ');
}
