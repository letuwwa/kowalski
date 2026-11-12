import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getTargetHistory } from '../src/features/scans/targetHistoryApi.ts';
import { historyDifferences } from '../src/features/scans/historyDifferences.ts';

function item(overrides = {}) {
  return {
    baseline_id: 'previous-report', changes: [], service_changes: [],
    addresses_added: [], addresses_removed: [], only_in_previous: [], only_in_current: [],
    configuration_changed: false, ...overrides,
  };
}

test('history encodes hostname and cursor and retains cancellation', async () => {
  const signal = new AbortController().signal;
  const cursor = '2026-11-12T12:00:00+00:00|report-id';
  const calls = [];
  await getTargetHistory(async (...args) => { calls.push(args); }, 'Scan.Example.test.', signal, cursor);
  const url = new URL(calls[0][0], 'http://localhost');
  assert.equal(url.pathname, '/scans/history');
  assert.equal(url.searchParams.get('target'), 'Scan.Example.test.');
  assert.equal(url.searchParams.get('cursor'), cursor);
  assert.equal(url.searchParams.get('limit'), '10');
  assert.equal(calls[0][1].signal, signal);
});

test('a first completed run establishes a baseline, not newly exposed services', () => {
  assert.deepEqual(historyDifferences(item({ baseline_id: null, addresses_added: ['127.0.0.1'], only_in_current: [{ ip_address: '127.0.0.1', port: 22 }] })), []);
});

test('state changes retain the destination and identify unknown transitions as inconclusive', () => {
  const rows = historyDifferences(item({ changes: [
    { ip_address: '127.0.0.1', port: 22, previous: 'open', current: 'unknown', kind: 'inconclusive' },
    { ip_address: '127.0.0.2', port: 22, previous: 'open', current: 'closed', kind: 'state_changed' },
  ] }));
  assert.equal(rows[0].destination, '127.0.0.1:22');
  assert.match(rows[0].meaning, /Inconclusive/);
  assert.equal(rows[1].destination, '127.0.0.2:22');
  assert.equal(rows[1].current, 'closed');
});

test('missing ports and DNS/address changes never imply closed ports', () => {
  const rows = historyDifferences(item({
    addresses_added: ['127.0.0.2'], addresses_removed: ['127.0.0.1'],
    only_in_previous: [{ ip_address: '127.0.0.1', port: 22 }],
    only_in_current: [{ ip_address: '127.0.0.2', port: 443 }],
  }));
  assert.equal(rows.length, 4);
  assert.ok(rows.every((row) => row.current !== 'closed' && row.previous !== 'closed'));
  assert.equal(new Set(rows.map((row) => row.key)).size, 4);
});

test('banner-only comment changes remain visible and failed identification is not removal', () => {
  const identified = { status: 'identified', protocol: 'ssh', advertised_software: 'TestSSH', banner: 'SSH-2.0-TestSSH comment1' };
  const rows = historyDifferences(item({ service_changes: [
    { ip_address: '127.0.0.1', port: 22, previous: identified, current: { ...identified, banner: 'SSH-2.0-TestSSH comment2' }, kind: 'banner_changed' },
    { ip_address: '127.0.0.1', port: 2222, previous: identified, current: { status: 'timeout' }, kind: 'inconclusive' },
  ] }));
  assert.notEqual(rows[0].previous, rows[0].current);
  assert.match(rows[0].meaning, /self-reported/);
  assert.match(rows[1].meaning, /removal is not confirmed/);
});

test('matching observations have no invented differences', () => {
  assert.deepEqual(historyDifferences(item()), []);
});
