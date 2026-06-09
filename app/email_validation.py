from email_validator import EmailNotValidError, validate_email


MAX_EMAIL_LENGTH = 120


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

    return normalized_email
