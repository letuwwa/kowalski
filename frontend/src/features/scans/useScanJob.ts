import { useEffect, useState } from 'react';
import type { AuthenticatedRequest } from '../auth/authenticatedRequest';
import { getScan } from './scanApi';
import type { ScanDetails } from './scanApi';
import { pollScan } from './pollScan';
import { scanError } from './scanErrors';

export function useScanJob(request: AuthenticatedRequest, id: string | null) {
  const [job, setJob] = useState<ScanDetails | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setJob(null);
    setError('');
    setLoading(Boolean(id));
    if (!id) return;
    const controller = new AbortController();
    void pollScan(
      (signal) => getScan(request, id, signal),
      (result) => { setJob(result); setLoading(false); },
      controller.signal,
    ).catch((error) => {
      if (controller.signal.aborted) return;
      setError(scanError(error));
      setLoading(false);
    });
    return () => controller.abort();
  }, [request, id, attempt]);

  // Never display a previously selected run while the next effect is starting.
  return { job: job?.id === id ? job : null, error, loading, retry: () => setAttempt((value) => value + 1) };
}
