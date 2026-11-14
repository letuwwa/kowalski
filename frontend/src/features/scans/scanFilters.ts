export type ScanFilters = {
  target?: string;
  status?: string;
  from?: string;
  to?: string;
};

// Date pickers are local calendar days. The API's upper bound is exclusive.
export function dateBounds(
  from: string,
  to: string,
): Pick<ScanFilters, 'from' | 'to'> {
  function boundary(day: string, nextDay: boolean): string | undefined {
    if (!day) return undefined;
    const date = new Date(`${day}T00:00:00`);
    const [year, month, dayNumber] = day.split('-').map(Number);
    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(day) ||
      !Number.isFinite(date.getTime()) ||
      date.getFullYear() !== year ||
      date.getMonth() !== month - 1 ||
      date.getDate() !== dayNumber
    )
      throw new Error('Choose valid dates.');
    if (nextDay) date.setDate(date.getDate() + 1);
    return date.toISOString();
  }
  const lower = boundary(from, false);
  const upper = boundary(to, true);
  if (lower && upper && lower >= upper)
    throw new Error('The start date must not be after the end date.');
  return { from: lower, to: upper };
}
