import type { ScanFilters } from './scanFilters';
import { useEffect, useState } from 'react';
import type { AuthenticatedRequest } from '../auth/authenticatedRequest';
import { listScans } from './scanApi';
import type { ScanJob } from './scanApi';
import { scanError } from './scanErrors';

export function useScanList(
  request: AuthenticatedRequest,
  filters: ScanFilters = {},
) {
  const [jobs, setJobs] = useState<ScanJob[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const key = JSON.stringify([
    filters.target,
    filters.status,
    filters.from,
    filters.to,
  ]);
  const [page, setPage] = useState<{ key: string; cursor?: string }>({ key });
  const [loadedKey, setLoadedKey] = useState('');
  useEffect(() => {
    if (page.key !== key) setPage({ key });
  }, [key, page.key]);
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (page.key !== key) return;
    const pageCursor = page.cursor;
    const controller = new AbortController();
    setLoading(true);
    if (!pageCursor) {
      setJobs([]);
      setNextCursor(null);
    }
    setError('');
    void listScans(request, controller.signal, pageCursor, filters)
      .then((page) => {
        if (controller.signal.aborted) return;
        setJobs((previous) => {
          const rows = pageCursor ? [...previous, ...page.items] : page.items;
          return [...new Map(rows.map((row) => [row.id, row])).values()];
        });
        setNextCursor(page.next_cursor);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(scanError(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
          setLoadedKey(key);
        }
      });
    return () => controller.abort();
  }, [request, key, page.key, page.cursor, attempt]);

  function reload() {
    setPage({ key });
    setAttempt((value) => value + 1);
  }

  return {
    jobs: loadedKey === key ? jobs : [],
    loading: loading || loadedKey !== key,
    error: loadedKey === key ? error : '',
    nextCursor: loadedKey === key ? nextCursor : null,
    reload,
    loadMore: () => {
      if (nextCursor && !loading) {
        setPage({ key, cursor: nextCursor });
        setAttempt((value) => value + 1);
      }
    },
  };
}
