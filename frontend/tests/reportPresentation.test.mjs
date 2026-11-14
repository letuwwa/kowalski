import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  sortedPorts,
  scanTiming,
  displayEvidence,
} from '../src/features/scans/reportPresentation.ts';
import { dateBounds } from '../src/features/scans/scanFilters.ts';
import { listScans } from '../src/features/scans/scanApi.ts';

test('ports are ordered numerically across addresses without mutating evidence', () => {
  const rows = [
    { target: '127.0.0.10', port: 443 },
    { target: '127.0.0.10', port: 22 },
    { target: '127.0.0.2', port: 22 },
  ];
  assert.deepEqual(
    sortedPorts(rows).map((row) => `${row.target}:${row.port}`),
    ['127.0.0.2:22', '127.0.0.10:22', '127.0.0.10:443'],
  );
  assert.equal(rows[0].port, 443);
});
test('timing distinguishes queued, in-progress, and completed scans', () => {
  assert.equal(
    scanTiming({ started_at: null, completed_at: null }),
    'Not started',
  );
  assert.equal(
    scanTiming({ started_at: '2026-11-14T10:00:00Z', completed_at: null }),
    'In progress',
  );
  assert.equal(
    scanTiming({
      started_at: '2026-11-14T10:00:00Z',
      completed_at: '2026-11-14T10:00:01.500Z',
    }),
    '1.5 seconds',
  );
});
test('binary evidence is displayed without interpreting control bytes', () => {
  assert.equal(
    displayEvidence(btoa('SSH-2.0-Test\r\n\x1b')),
    'SSH-2.0-Test\\x0d\\x0a\\x1b',
  );
  assert.match(displayEvidence('%%%'), /invalid/);
});
test('date filters cover complete local days using an exclusive upper bound', () => {
  assert.deepEqual(dateBounds('2026-11-10', '2026-11-10'), {
    from: new Date('2026-11-10T00:00:00').toISOString(),
    to: new Date('2026-11-11T00:00:00').toISOString(),
  });
  assert.throws(() => dateBounds('2026-02-31', ''));
  assert.throws(() => dateBounds('2026-11-12', '2026-11-10'));
});
test('list filters are encoded and sent to the server, not applied only to a loaded page', async () => {
  let requested;
  await listScans(
    async (url) => {
      requested = new URL(url, 'http://localhost');
    },
    new AbortController().signal,
    'cursor|time',
    {
      target: 'scan.example.test',
      status: 'failed',
      from: '2026-11-10T00:00:00Z',
      to: '2026-11-11T00:00:00Z',
    },
  );
  assert.equal(requested.searchParams.get('target'), 'scan.example.test');
  assert.equal(requested.searchParams.get('status'), 'failed');
  assert.equal(requested.searchParams.get('cursor'), 'cursor|time');
  assert.equal(requested.searchParams.get('to'), '2026-11-11T00:00:00Z');
});
