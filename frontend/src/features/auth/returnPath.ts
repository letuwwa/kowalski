export function getReturnPath(from: unknown): string {
  const fallback = '/profile';
  if (typeof from !== 'string' || !from.startsWith('/') || from.includes('\\')) {
    return fallback;
  }

  try {
    const base = 'https://kowalski.invalid';
    const url = new URL(from, base);
    const isAuthPage = /^\/(login|register)\/*$/i.test(url.pathname);
    if (url.origin !== base || url.pathname.startsWith('//') || isAuthPage) return fallback;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return fallback;
  }
}
