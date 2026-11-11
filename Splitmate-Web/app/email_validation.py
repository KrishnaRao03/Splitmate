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

    return normalized_email
