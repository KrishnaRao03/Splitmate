/** Formats an amount with the workspace currency, e.g. "CA$12.50" / "$12.50". */
export function formatMoney(amount: number, currencyCode = 'CAD') {
  const value = Number.isFinite(amount) ? amount : 0;
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: currencyCode }).format(value);
  } catch {
    return `${currencyCode} ${value.toFixed(2)}`;
  }
}

/** Parses user-typed money ("12", "12.5", "1,234.50"). Returns null when invalid. */
export function parseAmount(input: string): number | null {
  const cleaned = input.replace(/,/g, '').trim();
  if (!/^\d*\.?\d+$|^\d+\.$/.test(cleaned)) {
    return null;
  }
  const value = Number(cleaned);
  return Number.isFinite(value) ? Math.round(value * 100) / 100 : null;
}
