export function getReturnPath(from: unknown): string {
  const fallback = '/account';
  if (typeof from !== 'string' || !from.startsWith('/') || from.includes('\\')) {
    return fallback;
  }

  try {
    const base = 'https://kowalski.invalid';
    const url = new URL(from, base);
    const isLogin = /^\/login\/*$/i.test(url.pathname);
    if (url.origin !== base || url.pathname.startsWith('//') || isLogin) return fallback;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return fallback;
  }
}
