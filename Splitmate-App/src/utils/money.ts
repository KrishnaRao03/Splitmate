import type { Balance } from '@/types';

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

export type Settlement = {
  fromId: number;
  from: string;
  toId: number;
  to: string;
  amount: number;
};

/**
 * Turns per-member net balances into the smallest practical set of payments
 * (greedy: biggest debtor pays biggest creditor). Works in integer cents so
 * rounding never leaves a stray cent behind.
 */
export function suggestSettlements(balances: Balance[]): Settlement[] {
  const debtors = balances
    .map(b => ({ id: b.id, name: b.name, cents: Math.round(-b.net * 100) }))
    .filter(b => b.cents > 0)
    .sort((a, b) => b.cents - a.cents);
  const creditors = balances
    .map(b => ({ id: b.id, name: b.name, cents: Math.round(b.net * 100) }))
    .filter(b => b.cents > 0)
    .sort((a, b) => b.cents - a.cents);

  const result: Settlement[] = [];
  let d = 0;
  let c = 0;
  while (d < debtors.length && c < creditors.length) {
    const cents = Math.min(debtors[d].cents, creditors[c].cents);
    if (cents > 0) {
      result.push({
        fromId: debtors[d].id,
        from: debtors[d].name,
        toId: creditors[c].id,
        to: creditors[c].name,
        amount: cents / 100
      });
    }
    debtors[d].cents -= cents;
    creditors[c].cents -= cents;
    if (debtors[d].cents === 0) d += 1;
    if (creditors[c].cents === 0) c += 1;
  }
  return result;
}
