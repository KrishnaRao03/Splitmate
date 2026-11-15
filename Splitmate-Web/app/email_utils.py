import json
import os
from html import escape
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from flask import current_app

BREVO_SEND_URL = 'https://api.brevo.com/v3/smtp/email'

# Brevo's reason for the most recent rejected email (no secrets), shown by /api/mobile/health.
last_email_error = None


def _send_with_brevo(api_key, sender, recipient, subject, body, html=None):
    # HTTPS email API, for hosts that block outbound SMTP (e.g. Render's free plan).
    payload = {
        'sender': {'name': 'Splitmate', 'email': sender},
        'to': [{'email': recipient}],
        'subject': subject,
        'textContent': body,
    }
    if html:
        payload['htmlContent'] = html
    request = urllib.request.Request(
        BREVO_SEND_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'api-key': api_key, 'Content-Type': 'application/json', 'Accept': 'application/json'},
        method='POST',
    )
    global last_email_error
    try:
        with urllib.request.urlopen(request, timeout=15):
            pass
    except urllib.error.HTTPError as exc:
        # Brevo explains rejections (unverified sender, blocked IP, bad key) in the body; log it.
        detail = exc.read().decode('utf-8', 'replace')[:500]
        current_app.logger.error('Brevo rejected the email (HTTP %s): %s', exc.code, detail)
        last_email_error = f'HTTP {exc.code}: {detail}'
        raise
    last_email_error = None
    return True


def send_email(recipient, subject, body, html=None):
    """Send a plain-text email, with an optional HTML version that mail apps show instead."""
    sender = current_app.config['MAIL_DEFAULT_SENDER']
    brevo_api_key = current_app.config.get('BREVO_API_KEY')
    if brevo_api_key:
        return _send_with_brevo(brevo_api_key, sender, recipient, subject, body, html)

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
    if html:
        message.add_alternative(html, subtype='html')

    with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'], timeout=15) as smtp:
        smtp.ehlo()
        if current_app.config['MAIL_USE_TLS']:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(message)

    return True


# Graphite and sunshine yellow, matching the app. No gradients; sentence case; calm wording.
INK = '#1f2023'
MUTED = '#5b5e66'
FAINT = '#8b8e96'
LINE = '#e7e7ea'
PAGE = '#f4f4f5'
YELLOW = '#ffc83d'
YELLOW_SOFT = '#fff6dc'


def app_url(path=''):
    """Where email buttons send people: the Splitmate app (its web build, added to the home screen)."""
    base = (os.environ.get('APP_URL') or 'https://splitmate-app.onrender.com').rstrip('/')
    return f'{base}{path}'


def logo_url():
    web = (os.environ.get('WEB_URL') or 'https://splitmate-web.onrender.com').rstrip('/')
    return f'{web}/static/images/splitmate-logo.png'


def format_amount(amount, currency='CAD'):
    from app.regions import currency_symbol
    code = (currency or 'CAD').upper()
    return f'{currency_symbol(code)}{float(amount):,.2f} {code}'


def render_email(preheader, heading, paragraphs, code=None, button=None, footnote=None, highlight=None, details=None,
                 extra_html=''):
    """Branded HTML email. Table layout and inline styles, because many mail apps ignore <style> blocks.

    paragraphs, highlight and footnote are plain text (escaped here); button is (label, url);
    highlight is a short line shown large (an amount or status); details is a list of (label, value) rows;
    extra_html is already-escaped HTML placed after the button.
    """
    paragraph_html = ''.join(
        f'<p style="margin:0 0 16px;font-size:16px;line-height:24px;color:{MUTED};">{escape(text)}</p>'
        for text in paragraphs
    )
    highlight_html = ''
    if highlight:
        highlight_html = (
            f'<div style="margin:4px 0 24px;padding:16px;border-radius:12px;background:{YELLOW_SOFT};'
            f'border:1px solid {YELLOW};text-align:center;font-size:24px;line-height:32px;font-weight:700;color:{INK};">'
            f'{escape(highlight)}</div>'
        )
    details_html = ''
    if details:
        rows = ''.join(
            f'<tr><td style="padding:8px 0;font-size:14px;line-height:20px;color:{FAINT};">{escape(label)}</td>'
            f'<td style="padding:8px 0;font-size:14px;line-height:20px;color:{INK};font-weight:600;text-align:right;">{escape(value)}</td></tr>'
            for label, value in details
        )
        details_html = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:0 0 24px;border-top:1px solid {LINE};border-bottom:1px solid {LINE};">{rows}</table>'
        )
    code_html = ''
    if code:
        digits = ''.join(
            f'<span style="display:inline-block;width:44px;height:56px;line-height:56px;margin:0 4px;'
            f'border-radius:12px;background:{YELLOW_SOFT};border:1px solid {YELLOW};font-size:28px;font-weight:700;'
            f'color:{INK};font-family:Consolas,Menlo,monospace;">{escape(digit)}</span>'
            for digit in str(code)
        )
        code_html = f'<div style="margin:8px 0 24px;text-align:center;white-space:nowrap;">{digits}</div>'
    button_html = ''
    if button:
        label, url = button
        button_html = (
            '<div style="margin:8px 0 24px;text-align:center;">'
            f'<a href="{escape(url, quote=True)}" style="display:inline-block;padding:12px 24px;border-radius:12px;'
            f'background:{YELLOW};color:{INK};font-size:16px;line-height:24px;font-weight:700;text-decoration:none;">{escape(label)}</a>'
            f'<p style="margin:16px 0 0;font-size:12px;line-height:16px;color:{FAINT};word-break:break-all;">'
            f'Button not working? Paste this link into your browser:<br>{escape(url)}</p>'
            '</div>'
        )
    footnote_html = (
        f'<p style="margin:0;font-size:14px;line-height:20px;color:{FAINT};">{escape(footnote)}</p>' if footnote else ''
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(heading)}</title></head>
<body style="margin:0;padding:0;background:{PAGE};font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<span style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAGE};padding:32px 12px;">
  <tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;">
      <tr><td style="padding:0 8px 16px;">
        <img src="{escape(logo_url(), quote=True)}" alt="Splitmate" width="160" style="display:block;width:160px;max-width:160px;height:auto;border:0;">
      </td></tr>
    </table>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border:1px solid {LINE};border-radius:16px;overflow:hidden;">
      <tr><td style="height:6px;background:{YELLOW};font-size:0;line-height:0;">&nbsp;</td></tr>
      <tr><td style="padding:32px;">
        <h1 style="margin:0 0 16px;font-size:24px;line-height:32px;font-weight:700;color:{INK};">{escape(heading)}</h1>
        {paragraph_html}
        {highlight_html}
        {details_html}
        {code_html}
        {button_html}
        {extra_html}
        {footnote_html}
      </td></tr>
    </table>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;">
      <tr><td style="padding:16px 8px;font-size:12px;line-height:16px;color:{FAINT};text-align:center;">
        Splitmate &middot; Split bills, not friendships.<br>
        Splitmate never asks for your password or bank details by email.
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def send_verification_otp(user, otp):
    expiry = current_app.config['OTP_EXPIRY_MINUTES']
    return send_email(
        user.email,
        f'{otp} is your Splitmate code',
        f'Hi {user.name},\n\n'
        f'Your Splitmate verification code is {otp}.\n'
        f'This code expires in {expiry} minutes.\n\n'
        'If you did not request this, you can ignore this email.\n',
        render_email(
            f'Your code is {otp}. It expires in {expiry} minutes.',
            f'Welcome to Splitmate, {user.name}',
            ['Enter this code in the app to verify your email and finish creating your account.'],
            code=otp,
            footnote=f'The code expires in {expiry} minutes. If you did not sign up for Splitmate, you can ignore this email.',
        ),
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
        'If you did not request this, you can ignore this email.\n',
        render_email(
            'Reset your Splitmate password.',
            'Reset your password',
            [f'Hi {user.name}, we got a request to reset your Splitmate password. '
             'Choose a new one, then sign in to the app with it.'],
            button=('Choose a new password', reset_url),
            footnote=f'This link works once and expires in {expiry_minutes} minutes. '
                     'If you did not ask for this, your password stays the same.',
        ),
    )


def send_inactivity_reminder_email(user, days_idle):
    link = app_url()
    return send_email(
        user.email,
        'Your Splitmate groups miss you',
        f'Hi {user.name},\n\n'
        f'It has been about {days_idle} days since your last Splitmate activity.\n'
        f'Open Splitmate to add recent expenses, settle balances, or check what your group still needs:\n{link}\n\n'
        'If everything is already settled, you can ignore this reminder.\n',
        render_email(
            'Catch up on your shared expenses.',
            f'It has been a while, {user.name}',
            [
                f'It has been about {days_idle} days since you last opened Splitmate.',
                'Add the expenses you have paid for since, settle up balances, or check what your group still needs.',
            ],
            button=('Open Splitmate', link),
            footnote='If everything is already settled, you can ignore this reminder.',
        ),
    )


def send_group_item_email(recipient_email, recipient_name, kind, group_name, author_name, title, description='', details=None):
    """Tells a group member that someone added a task or note to their group."""
    noun = 'task' if kind == 'task' else 'note'
    link = app_url()
    subject = f'{author_name} added a {noun} in {group_name}'
    text = f'Hi {recipient_name},\n\n{author_name} added a {noun} in "{group_name}": {title}\n'
    if description:
        text += f'\n{description}\n'
    for label, value in details or []:
        text += f'{label}: {value}\n'
    text += f'\nOpen Splitmate to see it: {link}\n'
    paragraphs = [f'{author_name} added a {noun} in "{group_name}".']
    if description:
        paragraphs.append(description[:400])
    return send_email(
        recipient_email,
        subject,
        text,
        render_email(
            f'New {noun} in {group_name}: {title}',
            f'New {noun}: {title}',
            paragraphs,
            details=[('Group', group_name), ('Added by', author_name), *(details or [])],
            button=(f'Open {noun}s' if kind == 'task' else 'Open notes', link),
            footnote='You get these because you are in this group on Splitmate.',
        ),
    )


def _invite_token(invite_url):
    return (invite_url or '').rstrip('/').rsplit('/', 1)[-1]


def send_group_invite_email(recipient, group, inviter, invite_url):
    expiry_days = current_app.config['GROUP_INVITE_EXPIRY_DAYS']
    # The app shows this invite on its Invites screen once the person signs in with this email.
    link = app_url(f'/?invite={_invite_token(invite_url)}')
    return send_email(
        recipient,
        f'{inviter.name} invited you to {group.name} on Splitmate',
        f'Hi,\n\n'
        f'{inviter.name} invited you to join the "{group.name}" group on Splitmate.\n\n'
        f'Open the app to accept:\n{link}\n\n'
        f'Sign in or create your account with this email ({recipient}) and the invite is waiting under Invites.\n'
        f'This invite expires in {expiry_days} days.\n',
        render_email(
            f'{inviter.name} wants you in {group.name}.',
            f'Join {group.name}',
            [f'{inviter.name} invited you to split expenses, tasks and notes in "{group.name}" on Splitmate.',
             f'Open the app and sign in or create your account with {recipient}. The invite is waiting under Invites.'],
            button=('Open Splitmate to accept', link),
            footnote=f'This invite expires in {expiry_days} days. Tip: on your phone, add Splitmate to your home screen.',
        ),
    )


def send_splitmate_invite_email(recipient, inviter, join_url):
    link = app_url()
    return send_email(
        recipient,
        f'{inviter.name} invited you to join Splitmate',
        f'Hi,\n\n'
        f'{inviter.name} invited you to join Splitmate.\n\n'
        'Splitmate helps roommates, friends, and groups track shared expenses, notes, and tasks together.\n\n'
        f'Get the app here:\n{link}\n',
        render_email(
            f'{inviter.name} invited you to Splitmate.',
            'You are invited to Splitmate',
            [
                f'{inviter.name} uses Splitmate to keep shared expenses fair and simple.',
                'Track who paid, see who owes what, and settle up in a tap, with roommates, friends or travel groups.',
            ],
            button=('Get Splitmate', link),
            footnote='It is free. On your phone, open the link and add Splitmate to your home screen.',
        ),
    )


def send_interac_verification_code(user, interac_email, otp):
    expiry = current_app.config['OTP_EXPIRY_MINUTES']
    return send_email(
        interac_email,
        f'{otp} is your Splitmate Interac code',
        f'Hi {user.name},\n\n'
        f'Enter {otp} in Splitmate to confirm {interac_email} as your Interac e-Transfer email.\n'
        f'This code expires in {expiry} minutes.\n\n'
        'If you did not ask for this, ignore this email; nothing changes.\n',
        render_email(
            f'Your code is {otp}. It expires in {expiry} minutes.',
            'Confirm your Interac email',
            [f'Enter this code in Splitmate to confirm {interac_email} as the email your friends send Interac '
             'e-Transfers to. Until you do, nobody sees it.'],
            code=otp,
            footnote=f'The code expires in {expiry} minutes. If you did not ask for this, ignore this email; nothing changes.',
        ),
    )


def send_payment_details_changed_email(user, changes):
    """Security alert to the account email whenever payment details change. `changes` are short plain phrases."""
    lines = '\n'.join(f'- {change}' for change in changes)
    return send_email(
        user.email,
        'Your Splitmate payment details changed',
        f'Hi {user.name},\n\nThese payment details on your Splitmate account just changed:\n{lines}\n\n'
        'If this was not you, change your password right away and check your Profile.\n',
        render_email(
            'Your payment details changed.',
            'Payment details changed',
            ['These payment details on your Splitmate account just changed:', *changes,
             'If this was not you, change your password right away and check your Profile.'],
            button=('Review my profile', app_url()),
            footnote='We send this alert every time payment details change, so nobody can redirect your money quietly.',
        ),
    )


# Same list as the app's canadian-banks.json. Interac has no "pay this person" link, so the email links the banks.
CANADIAN_BANK_LINKS = [
    ('RBC', 'https://www.rbcroyalbank.com'),
    ('TD', 'https://www.td.com/ca/en/personal-banking'),
    ('Scotiabank', 'https://www.scotiabank.com'),
    ('BMO', 'https://www.bmo.com'),
    ('CIBC', 'https://www.cibc.com'),
    ('Tangerine', 'https://www.tangerine.ca'),
    ('Desjardins', 'https://www.desjardins.com'),
]


def _pay_directly_html(requester_name, methods, amount_text, memo):
    """The requester's own payment details, so the payer can pay straight from their bank. No money goes through Splitmate."""
    def row(label, value):
        return (f'<tr><td style="padding:8px 0;font-size:14px;line-height:20px;color:{FAINT};">{escape(label)}</td>'
                f'<td style="padding:8px 0;font-size:14px;line-height:20px;color:{INK};font-weight:600;text-align:right;'
                f'word-break:break-all;">{escape(value)}</td></tr>')

    def link(label, url):
        return (f'<a href="{escape(url, quote=True)}" style="display:inline-block;margin:0 8px 8px 0;padding:8px 12px;'
                f'border-radius:12px;border:1px solid {LINE};color:{INK};font-size:14px;line-height:20px;font-weight:600;'
                f'text-decoration:none;">{escape(label)}</a>')

    parts = [f'<h2 style="margin:0 0 8px;font-size:18px;line-height:24px;font-weight:700;color:{INK};">'
             f'Pay {escape(requester_name)} directly</h2>']
    for method in methods:
        if method['type'] == 'interac':
            parts.append(
                f'<p style="margin:0 0 8px;font-size:14px;line-height:20px;color:{MUTED};">'
                'In your bank, choose Send Interac e-Transfer and enter:</p>'
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="margin:0 0 12px;border-top:1px solid {LINE};border-bottom:1px solid {LINE};">'
                f'{row("Interac email", method["handle"])}{row("Amount", amount_text)}{row("Message", memo)}</table>'
                f'<p style="margin:0 0 8px;font-size:14px;line-height:20px;color:{MUTED};">Open your bank:</p>'
                f'<div style="margin:0 0 16px;">{"".join(link(name, url) for name, url in CANADIAN_BANK_LINKS)}</div>')
        elif (method.get('url') or '').startswith('https://'):
            parts.append(f'<div style="margin:0 0 16px;">{link(f"Pay with {method["label"]}", method["url"])}</div>')
        else:
            parts.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px;">'
                         f'{row(method["label"], method["handle"])}</table>')
    parts.append(f'<p style="margin:0 0 24px;font-size:14px;line-height:20px;color:{MUTED};">'
                 'After you pay, tap "I\'ve paid" in Splitmate so it gets settled.</p>')
    return ''.join(parts)


def send_money_request_email(payer, requester, group, amount, pay_methods=None):
    """pay_methods: the requester's own verified ways to be paid (payment_methods_for), shown so the payer can pay directly."""
    amount_text = format_amount(amount, getattr(group, 'currency', None))
    link = app_url()
    memo = f'Splitmate - {group.name}'
    methods = pay_methods or []
    text_lines = ''.join(
        f'{method["label"]}: {method["handle"]}\n' for method in methods
    )
    text_pay = (f'\nPay {requester.name} directly from your bank:\n{text_lines}Amount: {amount_text}\nMessage: {memo}\n'
                if methods else '')
    return send_email(
        payer.email,
        f'{requester.name} asked you to pay {amount_text} on Splitmate',
        f'Hi {payer.name},\n\n{requester.name} asked you to pay {amount_text} for "{group.name}".\n'
        f'{text_pay}'
        f'Open Splitmate to review it or mark it paid: {link}\n'
        'Splitmate never handles the money; only pay from your own bank app.\n',
        render_email(
            f'{requester.name} asked you to pay {amount_text}.',
            'Payment request',
            [f'{requester.name} asked you to pay for your share in "{group.name}".',
             'Check the amount matches what you owe. You can pay them directly from your bank below.'
             if methods else 'Open Splitmate, check the amount matches what you owe, then approve or decline.'],
            highlight=amount_text,
            details=[('From', requester.name), ('Group', group.name)],
            button=('Open in Splitmate', link),
            extra_html=_pay_directly_html(requester.name, methods, amount_text, memo) if methods else '',
            footnote='Splitmate never handles your money or sends payment links of its own. '
                     'Only send money from your own bank app, and only to people you know.',
        ),
    )


def send_payment_recorded_email(receiver, payer, group, amount):
    """To the person being paid: someone says they paid; nothing settles until the receiver confirms."""
    amount_text = format_amount(amount, getattr(group, 'currency', None))
    link = app_url()
    return send_email(
        receiver.email,
        f'{payer.name} says they sent you {amount_text}',
        f'Hi {receiver.name},\n\n{payer.name} says they sent you {amount_text} for "{group.name}".\n'
        f'Confirm it in Splitmate to settle up: {link}\n'
        'Check the money arrived first. Balances only change once you confirm.\n',
        render_email(
            f'{payer.name} says they sent you {amount_text}.',
            f'{payer.name} says they sent you {amount_text}',
            ['Confirm it in Splitmate to settle up.',
             f'Check the money arrived in your account first. The payment is for "{group.name}", '
             'and balances only change once you confirm.'],
            highlight=amount_text,
            details=[('From', payer.name), ('Group', group.name), ('Status', 'Waiting for you to confirm')],
            button=('Confirm in Splitmate', link),
        ),
    )


def send_payment_confirmed_email(user, other_person, group, amount, paid_by_user):
    """Sent to both sides once the receiver confirms: the payment is done and the balance is settled."""
    amount_text = format_amount(amount, getattr(group, 'currency', None))
    headline = f'{amount_text} received and settled'
    if paid_by_user:
        line = f'{other_person.name} confirmed they received your {amount_text} for "{group.name}".'
        counterpart = ('Paid to', other_person.name)
    else:
        line = f'You confirmed receiving {amount_text} from {other_person.name} for "{group.name}".'
        counterpart = ('Paid by', other_person.name)
    return send_email(
        user.email,
        headline,
        f'Hi {user.name},\n\n{headline}.\n{line}\nThe balance is updated.\n\nView it in Splitmate: {app_url()}\n',
        render_email(
            headline + '.',
            headline,
            [line, 'The balance is updated in Splitmate.'],
            highlight=headline,
            details=[counterpart, ('Group', group.name), ('Status', 'Confirmed')],
            button=('View in Splitmate', app_url()),
        ),
    )


def send_membership_confirmation_email(user, plan_label, renews_on=None, amount_text=None):
    """Receipt-style confirmation after Splitmate Pro starts. Stripe sends the formal receipt."""
    details = [('Plan', plan_label), ('Account', user.email)]
    if amount_text:
        details.append(('Price', amount_text))
    if renews_on:
        details.append(('Renews on', renews_on))
    return send_email(
        user.email,
        f'Welcome to {plan_label}',
        f'Hi {user.name},\n\nYour {plan_label} membership is active. Thank you for supporting Splitmate.\n'
        f'Open Splitmate: {app_url()}\n'
        'Manage or cancel any time from your Profile in Splitmate.\n',
        render_email(
            f'Your {plan_label} membership is active.',
            f'Welcome to {plan_label}',
            [f'Thanks, {user.name}. Your membership is active and every Pro feature is unlocked.',
             'Stripe emails you the payment receipt separately.'],
            highlight='Membership active',
            details=details,
            button=('Open Splitmate', app_url()),
            footnote='Manage or cancel any time from your Profile in Splitmate.',
        ),
    )
