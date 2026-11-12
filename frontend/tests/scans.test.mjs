import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parsePorts, scanPayload } from '../src/features/scans/scanForm.ts';
import { getScan, listScans, serviceLabel, submitScan } from '../src/features/scans/scanApi.ts';
import { pollScan } from '../src/features/scans/pollScan.ts';

function validForm() {
  const form = new FormData();
  for (const [key, value] of Object.entries({ target: ' 127.0.0.1 ', ports: '22,80', timeout: '1', concurrency: '20', rate_limit: '100' })) form.set(key, value);
  return form;
}

test('port parsing deduplicates, expands ranges, and sorts numerically', () => {
  assert.deepEqual(parsePorts('443, 80-82,80,22'), [22, 80, 81, 82, 443]);
});

test('port parsing rejects invalid, descending, and oversized selections', () => {
  for (const ports of ['', ' ', '0', '65536', '80-22', '1-65535', '1-1024,2000', '80,', '-1', '1e2', '22.5', 'NaN']) {
    assert.throws(() => parsePorts(ports));
  }
  assert.equal(parsePorts('1-1024').length, 1024);
});

test('submission validates advanced options and leaves SSH defaults to the backend', () => {
  assert.deepEqual(scanPayload(validForm()), { target: '127.0.0.1', ports: [22, 80], timeout: 1, concurrency: 20, rate_limit: 100 });
  for (const [key, value] of [['target', ' '], ['timeout', '0'], ['timeout', '6'], ['concurrency', '1.5'], ['concurrency', '21'], ['rate_limit', '101'], ['rate_limit', 'NaN']]) {
    const form = validForm(); form.set(key, value);
    assert.throws(() => scanPayload(form));
  }
});

test('scan API uses bounded pagination, encodes cursors, and passes cancellation', async () => {
  const calls = [];
  const request = async (...args) => { calls.push(args); return {}; };
  const signal = new AbortController().signal;
  const payload = scanPayload(validForm());
  await submitScan(request, payload, signal);
  assert.deepEqual(JSON.parse(calls[0][1].body), payload);
  assert.equal(calls[0][1].signal, signal);
  await listScans(request, signal, '2026-11-12T12:00:00+00:00|id');
  const url = new URL(calls[1][0], 'http://localhost');
  assert.equal(url.searchParams.get('cursor'), '2026-11-12T12:00:00+00:00|id');
  assert.equal(url.searchParams.get('limit'), '20');
  await getScan(request, 'bad/id', signal);
  assert.equal(calls[2][0], '/scans/bad%2Fid');
});

test('service labels use actual observations, including missing legacy evidence', () => {
  assert.equal(serviceLabel(), 'Not checked');
  assert.equal(serviceLabel({ status: 'timeout' }), 'Not identified (timeout)');
  assert.equal(serviceLabel({ status: 'identified', protocol: 'ssh', advertised_software: 'OpenSSH_test' }), 'SSH · OpenSSH_test');
});

test('polling follows queued and running jobs, then stops on completion', async () => {
  const statuses = ['queued', 'running', 'completed'];
  const seen = [];
  let calls = 0;
  await pollScan(async () => ({ status: statuses[calls++] }), (row) => seen.push(row.status), new AbortController().signal, 0);
  assert.deepEqual(seen, statuses);
  assert.equal(calls, 3);
});

test('polling stops on a failed job and does not retry a failed read', async () => {
  const signal = new AbortController().signal;
  let calls = 0;
  await pollScan(async () => { calls++; return { status: 'failed' }; }, () => {}, signal, 0);
  assert.equal(calls, 1);
  await assert.rejects(pollScan(async () => { throw new Error('disconnected'); }, () => {}, signal, 0), /disconnected/);
});

test('polling cleanup cancels waiting and ignores an in-flight stale result', async () => {
  const controller = new AbortController();
  let calls = 0;
  await assert.rejects(pollScan(async () => { calls++; return { status: 'running' }; }, () => controller.abort(), controller.signal, 60_000));
  assert.equal(calls, 1);
  const stale = new AbortController();
  const seen = [];
  await pollScan(async () => { stale.abort(); return { status: 'completed' }; }, (row) => seen.push(row), stale.signal, 0);
  assert.deepEqual(seen, []);
});
