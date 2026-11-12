import { isPending } from './scanApi.ts';
import type { ScanDetails } from './scanApi.ts';

function wait(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const abort = () => { clearTimeout(timer); reject(signal.reason); };
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', abort);
      resolve();
    }, milliseconds);
    signal.addEventListener('abort', abort, { once: true });
  });
}

export async function pollScan(
  read: (signal: AbortSignal) => Promise<ScanDetails>,
  onResult: (result: ScanDetails) => void,
  signal: AbortSignal,
  interval = 2000,
): Promise<void> {
  while (!signal.aborted) {
    const result = await read(signal);
    if (signal.aborted) return;
    onResult(result);
    if (!isPending(result.status)) return;
    await wait(interval, signal);
  }
}
