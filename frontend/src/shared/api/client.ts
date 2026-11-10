export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function requestJson<T>(path: `/${string}`, options: RequestInit = {}): Promise<T> {
  const timeout = AbortSignal.timeout(12_000);
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: 'omit',
    cache: 'no-store',
    redirect: 'error',
    signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.message ?? body?.msg;
    throw new ApiError(response.status, typeof message === 'string' ? message : '');
  }

  return response.json();
}
