// Mirrors Splitmate-Web/app/regions.py. The server checks the code, so this list only drives the picker.

export type Country = { code: string; name: string; currency: string };

export const COUNTRIES: Country[] = [
  { code: 'AU', name: 'Australia', currency: 'AUD' },
  { code: 'AT', name: 'Austria', currency: 'EUR' },
  { code: 'BD', name: 'Bangladesh', currency: 'BDT' },
  { code: 'BE', name: 'Belgium', currency: 'EUR' },
  { code: 'BR', name: 'Brazil', currency: 'BRL' },
  { code: 'CA', name: 'Canada', currency: 'CAD' },
  { code: 'CN', name: 'China', currency: 'CNY' },
  { code: 'FI', name: 'Finland', currency: 'EUR' },
  { code: 'FR', name: 'France', currency: 'EUR' },
  { code: 'DE', name: 'Germany', currency: 'EUR' },
  { code: 'IN', name: 'India', currency: 'INR' },
  { code: 'IE', name: 'Ireland', currency: 'EUR' },
  { code: 'IT', name: 'Italy', currency: 'EUR' },
  { code: 'JP', name: 'Japan', currency: 'JPY' },
  { code: 'MX', name: 'Mexico', currency: 'MXN' },
  { code: 'NL', name: 'Netherlands', currency: 'EUR' },
  { code: 'NZ', name: 'New Zealand', currency: 'NZD' },
  { code: 'NG', name: 'Nigeria', currency: 'NGN' },
  { code: 'PK', name: 'Pakistan', currency: 'PKR' },
  { code: 'PH', name: 'Philippines', currency: 'PHP' },
  { code: 'PT', name: 'Portugal', currency: 'EUR' },
  { code: 'SG', name: 'Singapore', currency: 'SGD' },
  { code: 'ZA', name: 'South Africa', currency: 'ZAR' },
  { code: 'ES', name: 'Spain', currency: 'EUR' },
  { code: 'AE', name: 'United Arab Emirates', currency: 'AED' },
  { code: 'GB', name: 'United Kingdom', currency: 'GBP' },
  { code: 'US', name: 'United States', currency: 'USD' }
];

export const CURRENCIES = Array.from(new Set(COUNTRIES.map(country => country.currency))).sort();

/** Payment-detail fields that make sense in each country; PayPal works everywhere. */
export function paymentFieldsFor(country?: string | null): string[] {
  if (country === 'CA') return ['interac_email', 'paypal_username'];
  if (country === 'IN') return ['upi_id', 'paypal_username'];
  return ['paypal_username'];
}

export function countryByCode(code?: string | null) {
  return COUNTRIES.find(country => country.code === code);
}

/** The device's region (e.g. en-CA -> CA) if it's one we support, else Canada. */
export function deviceCountry() {
  try {
    const locale = Intl.DateTimeFormat().resolvedOptions().locale || '';
    const region = locale.split('-').pop()?.toUpperCase() || '';
    return countryByCode(region) ? region : 'CA';
  } catch {
    return 'CA';
  }
}
