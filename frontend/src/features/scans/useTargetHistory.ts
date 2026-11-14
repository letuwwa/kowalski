import { useEffect, useState } from 'react';
import type { AuthenticatedRequest } from '../auth/authenticatedRequest';
import { getTargetHistory } from './targetHistoryApi';
import type { TargetHistory } from './targetHistoryApi';
import { scanError } from './scanErrors';

export function useTargetHistory(request: AuthenticatedRequest, target: string, completionKey: string | null) {
  const key = JSON.stringify([target, completionKey]);
  const [page, setPage] = useState<{ key: string; cursor?: string }>({ key });
  const [data, setData] = useState<{ key: string; value: TargetHistory } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadedKey, setLoadedKey] = useState('');

  useEffect(() => {
    if (page.key !== key) setPage({ key });
  }, [key, page.key]);

  useEffect(() => {
    setError('');
    if (!target) { setLoading(false); return; }
    // Wait for the pagination reset. An old target's cursor is never reused,
    // even when returning to a target that was previously paged forward.
    if (page.key !== key) return;
    const controller = new AbortController();
    const cursor = page.cursor;
    setLoading(true);
    void getTargetHistory(request, target, controller.signal, cursor).then((next) => {
      if (controller.signal.aborted) return;
      setData((previous) => ({
        key,
        value: {
          ...next,
          items: cursor && previous?.key === key
            ? [...new Map([...previous.value.items, ...next.items].map((item) => [item.report.id, item])).values()]
            : next.items,
        },
      }));
    }).catch((error) => {
      if (!controller.signal.aborted) setError(scanError(error));
    }).finally(() => {
      if (!controller.signal.aborted) { setLoading(false); setLoadedKey(key); }
    });
    return () => controller.abort();
  }, [request, target, key, page.key, page.cursor, attempt]);

  const value = data?.key === key ? data.value : null;
  return {
    data: value, error, loading: Boolean(target) && (loading || loadedKey !== key),
    reload: () => { setPage({ key }); setAttempt((value) => value + 1); },
    loadMore: () => {
      if (!loading && value?.next_cursor) {
        setPage({ key, cursor: value.next_cursor });
        setAttempt((value) => value + 1);
      }
    },
  };
}
