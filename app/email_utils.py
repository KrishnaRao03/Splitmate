import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(recipient, subject, body):
    sender = current_app.config['MAIL_DEFAULT_SENDER']
    username = current_app.config['MAIL_USERNAME']
    password = current_app.config['MAIL_PASSWORD']

    if not password:
        current_app.logger.warning('MAIL_PASSWORD is not set; email was not sent.')
        return False

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = recipient
    message.set_content(body)

    with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'], timeout=15) as smtp:
        smtp.ehlo()
        if current_app.config['MAIL_USE_TLS']:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(message)

    return True


def send_verification_otp(user, otp):
    return send_email(
        user.email,
        'Your Splitmate verification code',
        f'Hi {user.name},\n\n'
        f'Your Splitmate verification code is {otp}.\n'
        f'This code expires in {current_app.config["OTP_EXPIRY_MINUTES"]} minutes.\n\n'
        'If you did not request this, you can ignore this email.\n'
    )


def send_password_reset_email(user, reset_url):
    expiry_minutes = current_app.config['PASSWORD_RESET_EXPIRY_MINUTES']
    return send_email(
        user.email,
        'Reset your Splitmate password',
        f'Hi {user.name},\n\n'
        'Use the link below to reset your Splitmate password:\n\n'
        f'{reset_url}\n\n'
        f'This link expires in {expiry_minutes} minutes.\n\n'
        'If you did not request this, you can ignore this email.\n'
    )


def send_inactivity_reminder_email(user, days_idle):
    return send_email(
        user.email,
        'Your Splitmate groups miss you',
        f'Hi {user.name},\n\n'
        f'It has been about {days_idle} days since your last Splitmate activity.\n'
        'Open Splitmate to add recent expenses, settle balances, or check what your group still needs.\n\n'
        'If everything is already settled, you can ignore this reminder.\n\n'
        'Thanks,\n'
        'Splitmate\n'
    )
