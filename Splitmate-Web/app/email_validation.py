from email_validator import EmailNotValidError, validate_email


MAX_EMAIL_LENGTH = 120


def has_realistic_email_domain(email):
    if '@' not in email:
        return False

    domain = email.rsplit('@', 1)[1].lower()
    labels = domain.split('.')
    if len(labels) < 2:
        return False

    tld = labels[-1]
    if len(tld) < 2 or not tld.isalpha():
        return False

    domain_name_labels = labels[:-1]
    return any(any(char.isalpha() for char in label) for label in domain_name_labels)


# Big providers whose address people mistype or cut short, e.g. name@gmail.c or name@gmial.com.
SINGLE_DOMAIN_PROVIDERS = {'gmail': 'gmail.com', 'googlemail': 'googlemail.com', 'icloud': 'icloud.com'}
REGIONAL_PROVIDERS = {'yahoo', 'hotmail', 'outlook', 'live', 'aol', 'msn'}
MISTYPED_PROVIDERS = {
    'gmial': 'gmail.com', 'gmai': 'gmail.com', 'gamail': 'gmail.com', 'gamil': 'gmail.com', 'gnail': 'gmail.com', 'gmaill': 'gmail.com',
    'gmal': 'gmail.com', 'gmeil': 'gmail.com', 'gmali': 'gmail.com', 'hotmial': 'hotmail.com', 'hotmal': 'hotmail.com',
    'hotmil': 'hotmail.com', 'outlok': 'outlook.com', 'outllok': 'outlook.com', 'yaho': 'yahoo.com',
    'yahooo': 'yahoo.com', 'yhoo': 'yahoo.com', 'iclod': 'icloud.com', 'icoud': 'icloud.com',
}
MISTYPED_COM = {'c', 'co', 'cm', 'cmo', 'con', 'om', 'comm', 'coom', 'cpm', 'xom', 'vom'}


def suggested_email_domain(domain):
    """The domain the person most likely meant, or None if the domain looks right."""
    domain = (domain or '').lower()
    labels = domain.split('.')
    provider = labels[0]
    if provider in SINGLE_DOMAIN_PROVIDERS:
        expected = SINGLE_DOMAIN_PROVIDERS[provider]
        return expected if domain != expected else None
    if provider in MISTYPED_PROVIDERS:
        return MISTYPED_PROVIDERS[provider]
    if provider in REGIONAL_PROVIDERS and len(labels) == 2 and labels[1] in MISTYPED_COM:
        return f'{provider}.com'
    return None


def email_error_message(value):
    """A specific message for an address normalize_email refused."""
    raw_email = (value or '').strip()
    if '@' in raw_email:
        local, _, domain = raw_email.rpartition('@')
        suggestion = suggested_email_domain(domain)
        if suggestion:
            return f'Check the email address. Did you mean {local}@{suggestion}?'
    return 'Enter a valid email address, like name@gmail.com.'


def normalize_email(value):
    raw_email = (value or '').strip()
    if not raw_email:
        return None

    try:
        result = validate_email(raw_email, check_deliverability=False)
    except EmailNotValidError:
        return None

    normalized_email = result.normalized.lower()
    if len(normalized_email) > MAX_EMAIL_LENGTH:
        return None

    if not has_realistic_email_domain(normalized_email):
        return None

    if suggested_email_domain(normalized_email.rsplit('@', 1)[1]):
        return None

    return normalized_email
