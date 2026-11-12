import type { AuthenticatedRequest } from '../auth/authenticatedRequest.ts';
import type { ScanReport, ServiceResult } from './scanApi.ts';

export type HistoryReport = ScanReport & { id: string; target: string; started_at: string };
type Destination = { ip_address: string; port: number };
export type HistoryItem = {
  report: HistoryReport;
  baseline_id: string | null;
  configuration_changed: boolean;
  changes: (Destination & { previous: string; current: string; kind: string })[];
  service_changes: (Destination & { previous: ServiceResult & { banner?: string | null }; current: ServiceResult & { banner?: string | null }; kind: string })[];
  only_in_previous: Destination[];
  only_in_current: Destination[];
  addresses_added: string[];
  addresses_removed: string[];
};
export type TargetHistory = { target: string; items: HistoryItem[]; next_cursor: string | null };

export function getTargetHistory(request: AuthenticatedRequest, target: string, signal: AbortSignal, cursor?: string): Promise<TargetHistory> {
  const params = new URLSearchParams({ target, limit: '10' });
  if (cursor) params.set('cursor', cursor);
  return request(`/scans/history?${params}`, { signal });
}
