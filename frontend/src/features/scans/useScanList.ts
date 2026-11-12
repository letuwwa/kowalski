import { useEffect, useState } from 'react';
import type { AuthenticatedRequest } from '../auth/authenticatedRequest';
import { listScans } from './scanApi';
import type { ScanJob } from './scanApi';
import { scanError } from './scanErrors';

export function useScanList(request: AuthenticatedRequest) {
  const [jobs, setJobs] = useState<ScanJob[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [pageCursor, setPageCursor] = useState<string | undefined>();
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    void listScans(request, controller.signal, pageCursor).then((page) => {
      if (controller.signal.aborted) return;
      setJobs((previous) => {
        const rows = pageCursor ? [...previous, ...page.items] : page.items;
        return [...new Map(rows.map((row) => [row.id, row])).values()];
      });
      setNextCursor(page.next_cursor);
    }).catch((error) => {
      if (!controller.signal.aborted) setError(scanError(error));
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [request, pageCursor, attempt]);

  function reload() {
    setPageCursor(undefined);
    setAttempt((value) => value + 1);
  }

  return {
    jobs, loading, error, nextCursor, reload,
    loadMore: () => {
      if (nextCursor && !loading) {
        setPageCursor(nextCursor);
        setAttempt((value) => value + 1);
      }
    },
  };
}
