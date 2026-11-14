"""Countries, their currencies, and which payment details make sense there.

A user's country sets their own display currency and which payment fields their profile offers.
A group has one currency (picked when it's created), so members from different countries still
share one set of balances; amounts are never converted.
"""

DEFAULT_COUNTRY = 'CA'

# code: (name, currency)
COUNTRIES = {
    'CA': ('Canada', 'CAD'),
    'US': ('United States', 'USD'),
    'IN': ('India', 'INR'),
    'GB': ('United Kingdom', 'GBP'),
    'AU': ('Australia', 'AUD'),
    'NZ': ('New Zealand', 'NZD'),
    'IE': ('Ireland', 'EUR'),
    'DE': ('Germany', 'EUR'),
    'FR': ('France', 'EUR'),
    'ES': ('Spain', 'EUR'),
    'IT': ('Italy', 'EUR'),
    'NL': ('Netherlands', 'EUR'),
    'PT': ('Portugal', 'EUR'),
    'BE': ('Belgium', 'EUR'),
    'AT': ('Austria', 'EUR'),
    'FI': ('Finland', 'EUR'),
    'MX': ('Mexico', 'MXN'),
    'BR': ('Brazil', 'BRL'),
    'SG': ('Singapore', 'SGD'),
    'AE': ('United Arab Emirates', 'AED'),
    'PH': ('Philippines', 'PHP'),
    'PK': ('Pakistan', 'PKR'),
    'BD': ('Bangladesh', 'BDT'),
    'NG': ('Nigeria', 'NGN'),
    'ZA': ('South Africa', 'ZAR'),
    'JP': ('Japan', 'JPY'),
    'CN': ('China', 'CNY'),
}

CURRENCY_SYMBOLS = {
    'CAD': '$', 'USD': '$', 'AUD': '$', 'NZD': '$', 'SGD': '$', 'MXN': '$',
    'INR': '₹', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CNY': '¥',
    'BRL': 'R$', 'PHP': '₱', 'NGN': '₦', 'ZAR': 'R', 'AED': 'AED ', 'PKR': 'Rs ', 'BDT': '৳',
}

# Which payment-detail fields a person in each country can fill in. PayPal works everywhere.
PAYMENT_FIELDS_BY_COUNTRY = {
    'CA': ('interac_email', 'paypal_username'),
    'IN': ('upi_id', 'paypal_username'),
}
DEFAULT_PAYMENT_FIELDS = ('paypal_username',)

CURRENCIES = sorted({currency for _, currency in COUNTRIES.values()})


def normalize_country(value):
    """The ISO country code if it's one we support, else None."""
    code = (value or '').strip().upper()
    return code if code in COUNTRIES else None


def country_name(code):
    return COUNTRIES.get(code or DEFAULT_COUNTRY, COUNTRIES[DEFAULT_COUNTRY])[0]


def currency_for_country(code):
    return COUNTRIES.get(code or DEFAULT_COUNTRY, COUNTRIES[DEFAULT_COUNTRY])[1]


def normalize_currency(value):
    code = (value or '').strip().upper()
    return code if code in CURRENCIES else None


def currency_symbol(currency):
    return CURRENCY_SYMBOLS.get((currency or '').upper(), f'{(currency or "").upper()} ')


def payment_fields_for(country):
    return PAYMENT_FIELDS_BY_COUNTRY.get(country or DEFAULT_COUNTRY, DEFAULT_PAYMENT_FIELDS)


def countries_payload():
    """For sign-up and profile pickers, sorted by name."""
    return [
        {'code': code, 'name': name, 'currency': currency, 'payment_fields': list(payment_fields_for(code))}
        for code, (name, currency) in sorted(COUNTRIES.items(), key=lambda item: item[1][0])
    ]
