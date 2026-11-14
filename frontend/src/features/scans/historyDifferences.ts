import { serviceLabel } from './scanApi.ts';
import type { HistoryItem } from './targetHistoryApi.ts';

export type HistoryDifference = {
  key: string; observation: string; destination: string;
  previous: string; current: string; meaning: string;
};

export function historyDifferences(item: HistoryItem): HistoryDifference[] {
  // The first run establishes evidence; it cannot establish newly exposed ports.
  if (!item.baseline_id) return [];
  const rows: HistoryDifference[] = item.changes.map((change) => ({
    key: `tcp:${change.ip_address}:${change.port}`,
    observation: 'TCP state', destination: `${change.ip_address}:${change.port}`,
    previous: change.previous, current: change.current,
    meaning: change.kind === 'inconclusive' ? 'Inconclusive: includes an unknown state.' : 'Observed state changed.',
  }));
  for (const change of item.service_changes) {
    rows.push({
      key: `service:${change.ip_address}:${change.port}`,
      observation: 'SSH evidence', destination: `${change.ip_address}:${change.port}`,
      previous: change.previous.banner || serviceLabel(change.previous),
      current: change.current.banner || serviceLabel(change.current),
      meaning: change.kind === 'banner_changed' ? 'Advertised banner changed; software identity is self-reported.' : 'Identification changed; service removal is not confirmed.',
    });
  }
  for (const [label, addresses] of [['added', item.addresses_added], ['removed', item.addresses_removed]] as const) {
    for (const address of addresses) rows.push({
      key: `address:${label}:${address}`, observation: 'Address coverage', destination: address,
      previous: label === 'added' ? 'Not represented' : 'Observed',
      current: label === 'added' ? 'Observed' : 'Not represented',
      meaning: 'Destination coverage changed. This is not a closed-port observation.',
    });
  }
  for (const [label, destinations] of [['current', item.only_in_current], ['previous', item.only_in_previous]] as const) {
    for (const destination of destinations) rows.push({
      key: `coverage:${label}:${destination.ip_address}:${destination.port}`,
      observation: 'Port coverage', destination: `${destination.ip_address}:${destination.port}`,
      previous: label === 'current' ? 'Not observed' : 'Observed',
      current: label === 'current' ? 'Observed' : 'Not observed',
      meaning: 'This IP/port was observed in only one run. Missing evidence does not mean closed.',
    });
  }
  return rows;
}
