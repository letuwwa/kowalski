import type { ScanSubmission } from './scanApi.ts';

export const PORT_PRESETS = [
  { label: 'Web', ports: '80,443' },
  { label: 'Remote access', ports: '22,3389' },
  { label: 'Common TCP', ports: '22,80,443,3389' },
];

export function parsePorts(value: string): number[] {
  const ports = new Set<number>();
  for (const token of value.split(',')) {
    const item = token.trim();
    if (!/^\d+(?:-\d+)?$/.test(item)) throw new Error('Enter ports and ranges, for example 22,80,8000-8010.');
    const [first, last = first] = item.split('-').map(Number);
    if (!Number.isInteger(first) || !Number.isInteger(last) || first < 1 || last > 65535 || first > last) {
      throw new Error('Ports must be 1–65535, with ranges in ascending order.');
    }
    // Bound expansion before looping over an arbitrary user-supplied range.
    if (last - first + 1 > 1024) throw new Error('Select at most 1024 TCP ports.');
    for (let port = first; port <= last; port++) {
      ports.add(port);
      if (ports.size > 1024) throw new Error('Select at most 1024 TCP ports.');
    }
  }
  return [...ports].sort((a, b) => a - b);
}

export function scanPayload(form: FormData): ScanSubmission {
  const target = String(form.get('target') ?? '').trim();
  if (!target) throw new Error('Enter an IPv4 address or hostname.');
  const ports = parsePorts(String(form.get('ports') ?? ''));
  const timeout = Number(form.get('timeout'));
  const concurrency = Number(form.get('concurrency'));
  const rate_limit = Number(form.get('rate_limit'));
  if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 5) throw new Error('Timeout must be greater than 0 and at most 5 seconds.');
  if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 20) throw new Error('Concurrency must be an integer from 1 to 20.');
  if (!Number.isFinite(rate_limit) || rate_limit <= 0 || rate_limit > 100) throw new Error('Rate limit must be greater than 0 and at most 100 connections per second.');
  return { target, ports, timeout, concurrency, rate_limit };
}
