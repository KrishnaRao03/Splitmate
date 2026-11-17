// Mirrors Splitmate-Web/app/email_validation.py and app/security.py so mistakes show before the request.

const EMAIL_PATTERN = /^[^\s@]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
const SINGLE_DOMAIN_PROVIDERS: Record<string, string> = { gmail: 'gmail.com', googlemail: 'googlemail.com', icloud: 'icloud.com' };
const REGIONAL_PROVIDERS = new Set(['yahoo', 'hotmail', 'outlook', 'live', 'aol', 'msn']);
const MISTYPED_PROVIDERS: Record<string, string> = {
  gmial: 'gmail.com', gmai: 'gmail.com', gamail: 'gmail.com', gamil: 'gmail.com', gnail: 'gmail.com', gmaill: 'gmail.com',
  gmal: 'gmail.com', gmeil: 'gmail.com', gmali: 'gmail.com', hotmial: 'hotmail.com', hotmal: 'hotmail.com',
  hotmil: 'hotmail.com', outlok: 'outlook.com', outllok: 'outlook.com', yaho: 'yahoo.com',
  yahooo: 'yahoo.com', yhoo: 'yahoo.com', iclod: 'icloud.com', icoud: 'icloud.com'
};
const MISTYPED_COM = new Set(['c', 'co', 'cm', 'cmo', 'con', 'om', 'comm', 'coom', 'cpm', 'xom', 'vom']);

export const PASSWORD_RULES = 'At least 8 characters with an uppercase letter, a lowercase letter, a number and a special character (like ! @ # $).';

function suggestedDomain(domain: string) {
  const labels = domain.toLowerCase().split('.');
  const provider = labels[0];
  if (SINGLE_DOMAIN_PROVIDERS[provider]) {
    return domain.toLowerCase() !== SINGLE_DOMAIN_PROVIDERS[provider] ? SINGLE_DOMAIN_PROVIDERS[provider] : null;
  }
  if (MISTYPED_PROVIDERS[provider]) {
    return MISTYPED_PROVIDERS[provider];
  }
  if (REGIONAL_PROVIDERS.has(provider) && labels.length === 2 && MISTYPED_COM.has(labels[1])) {
    return `${provider}.com`;
  }
  return null;
}

/** A message describing what is wrong with the email address, or '' when it looks right. */
export function emailError(value: string) {
  const email = value.trim();
  if (!email) {
    return 'Enter your email address.';
  }
  const at = email.lastIndexOf('@');
  if (at > 0) {
    const suggestion = suggestedDomain(email.slice(at + 1));
    if (suggestion) {
      return `Check the email address. Did you mean ${email.slice(0, at)}@${suggestion}?`;
    }
  }
  const tld = email.slice(email.lastIndexOf('.') + 1);
  if (email.length > 120 || !EMAIL_PATTERN.test(email) || !/^[A-Za-z]{2,}$/.test(tld)) {
    return 'Enter a valid email address, like name@gmail.com.';
  }
  return '';
}

/** The corrected address when the domain looks mistyped (name@gnail.com -> name@gmail.com), else ''. */
export function suggestedEmail(value: string) {
  const email = value.trim();
  const at = email.lastIndexOf('@');
  const suggestion = at > 0 ? suggestedDomain(email.slice(at + 1)) : null;
  return suggestion ? `${email.slice(0, at)}@${suggestion}` : '';
}

/** Mirrors normalize_phone on the server: 10 to 15 digits, with spaces, dashes, dots or brackets allowed. */
export function phoneError(value: string) {
  const phone = value.trim();
  const digits = phone.replace(/\D/g, '');
  if (!/^\+?[\d\s().-]+$/.test(phone) || digits.length < 10 || digits.length > 15) {
    return `"${phone}" is not a valid email or phone number. Use a full email like name@gmail.com or a phone number like 416 555 0123.`;
  }
  return '';
}

/** How strong a new password is, for the coloured border and meter while typing. */
export function passwordStrength(password: string): { level: 0 | 1 | 2 | 3 | 4; label: string; color: string } {
  if (!password) {
    return { level: 0, label: '', color: '' };
  }
  const rules = [password.length >= 8, /[A-Z]/.test(password), /[a-z]/.test(password), /[0-9]/.test(password), /[^A-Za-z0-9]/.test(password)];
  const met = rules.filter(Boolean).length;
  if (met === 5 && password.length >= 12) return { level: 4, label: 'Very strong', color: '#10b981' };
  if (met === 5) return { level: 3, label: 'Strong', color: '#22c55e' };
  if (met >= 4) return { level: 2, label: 'Almost there', color: '#f59e0b' };
  return { level: 1, label: 'Weak', color: '#e11d48' };
}

/** What a new password is missing, or '' when it meets every rule. */
export function passwordError(password: string) {
  const missing: string[] = [];
  if (password.length < 8) missing.push('at least 8 characters');
  if (!/[A-Z]/.test(password)) missing.push('an uppercase letter');
  if (!/[a-z]/.test(password)) missing.push('a lowercase letter');
  if (!/[0-9]/.test(password)) missing.push('a number');
  if (!/[^A-Za-z0-9]/.test(password)) missing.push('a special character (like ! @ # $)');
  if (!missing.length) {
    return '';
  }
  if (missing.length === 1) {
    return `Password needs ${missing[0]}.`;
  }
  return `Password needs ${missing.slice(0, -1).join(', ')} and ${missing[missing.length - 1]}.`;
}
