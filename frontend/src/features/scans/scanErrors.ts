import { ApiError } from '../../shared/api/client.ts';
import { SessionExpiredError } from '../auth/authenticatedRequest.ts';

export function scanError(error: unknown): string {
  if (error instanceof SessionExpiredError) return error.message;
  if (error instanceof ApiError) {
    if (error.status === 400) return error.message || 'Check the scan options and try again.';
    if (error.status === 404) return 'This scan could not be found.';
    if (error.status === 403) return 'You do not have access to this scan.';
    if (error.status === 429) return error.message || 'Too many requests. Wait before trying again.';
    if (error.status === 503) return 'Scan storage is unavailable. Try again later.';
  }
  return 'Could not load scan data. Check your connection and try again.';
}

export function submissionError(error: unknown): string {
  if (error instanceof ApiError || error instanceof SessionExpiredError) return scanError(error);
  return 'Could not confirm whether the scan was queued. Refresh Past scans before submitting again.';
}
