const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;

/**
 * The Splitmate server stores UTC but serializes naive ISO strings
 * ("2026-06-15T21:30:00"). JavaScript would read those as *local* time and
 * shift every date by the user's UTC offset, so treat zone-less values as UTC.
 */
export function parseServerDate(value: string | null | undefined): Date | null {
  if (!value) {
    return null;
  }
  const normalized = value.includes('T') && !HAS_ZONE.test(value) ? `${value}Z` : value;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(value: string | null | undefined, fallback = '') {
  const date = parseServerDate(value);
  return date ? date.toLocaleString() : fallback;
}

export function formatDate(value: string | null | undefined, fallback = '') {
  const date = parseServerDate(value);
  return date ? date.toLocaleDateString() : fallback;
}

/**
 * Parses what a person types into a date field: "2026-06-15 18:00",
 * "2026-06-15T18:00", or just "2026-06-15" (local time). Returns null if invalid.
 */
export function parseLocalInput(input: string): Date | null {
  const trimmed = input.trim();
  const match = trimmed.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?$/);
  if (match) {
    const [, y, mo, d, h = '9', mi = '0'] = match;
    const date = new Date(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi));
    const valid = date.getFullYear() === Number(y) && date.getMonth() === Number(mo) - 1 && date.getDate() === Number(d);
    return valid ? date : null;
  }
  const fallback = new Date(trimmed);
  return Number.isNaN(fallback.getTime()) ? null : fallback;
}
