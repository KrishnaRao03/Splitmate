import { parseServerDate } from '@/utils/dates';

export type HistorySort = 'newest' | 'oldest' | 'highest' | 'lowest';
export type HistoryPeriod = 'all' | 'this_month' | 'last_month' | 'last_3_months' | 'this_year';

export const SORT_OPTIONS: Array<{ label: string; value: HistorySort }> = [
  { label: 'Newest', value: 'newest' },
  { label: 'Oldest', value: 'oldest' },
  { label: 'Highest', value: 'highest' },
  { label: 'Lowest', value: 'lowest' }
];

export const PERIOD_OPTIONS: Array<{ label: string; value: HistoryPeriod }> = [
  { label: 'All time', value: 'all' },
  { label: 'This month', value: 'this_month' },
  { label: 'Last month', value: 'last_month' },
  { label: 'Last 3 months', value: 'last_3_months' },
  { label: 'This year', value: 'this_year' }
];

export const HISTORY_PAGE = 10;

function periodStart(period: HistoryPeriod, now: Date): [Date | null, Date | null] {
  const year = now.getFullYear();
  const month = now.getMonth();
  switch (period) {
    case 'this_month':
      return [new Date(year, month, 1), null];
    case 'last_month':
      return [new Date(year, month - 1, 1), new Date(year, month, 1)];
    case 'last_3_months':
      return [new Date(year, month - 2, 1), null];
    case 'this_year':
      return [new Date(year, 0, 1), null];
    default:
      return [null, null];
  }
}

/** Filters rows to a period and sorts them. Rows without a date only show under "All time". */
export function filterHistory<T extends { amount: number; date: string | null }>(rows: T[], sort: HistorySort, period: HistoryPeriod, now = new Date()) {
  const [from, to] = periodStart(period, now);
  const time = (row: T) => parseServerDate(row.date)?.getTime() ?? 0;
  const filtered = rows.filter(row => {
    if (period === 'all') {
      return true;
    }
    const date = parseServerDate(row.date);
    return !!date && (!from || date >= from) && (!to || date < to);
  });
  return [...filtered].sort((a, b) => {
    switch (sort) {
      case 'oldest':
        return time(a) - time(b);
      case 'highest':
        return b.amount - a.amount;
      case 'lowest':
        return a.amount - b.amount;
      default:
        return time(b) - time(a);
    }
  });
}
