import json
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


BRAND_BLUE = '#2563eb'
BRAND_DARK = '#0f172a'


def render_email(preheader, heading, paragraphs, code=None, button=None, footnote=None):
    """Branded HTML email. Table layout and inline styles, because many mail apps ignore <style> blocks.

    paragraphs and footnote are plain text (escaped here); button is (label, url).
    """
    paragraph_html = ''.join(
        f'<p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:#334155;">{escape(text)}</p>'
        for text in paragraphs
    )
    code_html = ''
    if code:
        digits = ''.join(
            f'<span style="display:inline-block;width:44px;height:56px;line-height:56px;margin:0 4px;'
            f'border-radius:12px;background:#eff6ff;border:1px solid #bfdbfe;font-size:28px;font-weight:700;'
            f'color:{BRAND_DARK};font-family:Consolas,Menlo,monospace;">{escape(digit)}</span>'
            for digit in str(code)
        )
        code_html = f'<div style="margin:8px 0 24px;text-align:center;white-space:nowrap;">{digits}</div>'
    button_html = ''
    if button:
        label, url = button
        button_html = (
            '<div style="margin:8px 0 24px;text-align:center;">'
            f'<a href="{escape(url, quote=True)}" style="display:inline-block;padding:14px 28px;border-radius:12px;'
            f'background:{BRAND_BLUE};color:#ffffff;font-size:16px;font-weight:600;text-decoration:none;">{escape(label)}</a>'
            f'<p style="margin:16px 0 0;font-size:12px;line-height:1.5;color:#94a3b8;word-break:break-all;">'
            f'Button not working? Paste this link into your browser:<br>{escape(url)}</p>'
            '</div>'
        )
    footnote_html = (
        f'<p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">{escape(footnote)}</p>' if footnote else ''
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(heading)}</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<span style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 12px;">
  <tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 10px 30px rgba(15,23,42,0.08);">
      <tr><td style="background:linear-gradient(135deg,#1d4ed8,#3b82f6 55%,#06b6d4);background-color:{BRAND_BLUE};padding:28px 32px;">
        <table role="presentation" cellpadding="0" cellspacing="0"><tr>
          <td style="width:44px;height:44px;border-radius:12px;background:rgba(255,255,255,0.18);text-align:center;font-size:22px;font-weight:800;color:#ffffff;">S</td>
          <td style="padding-left:12px;font-size:22px;font-weight:800;color:#ffffff;letter-spacing:0.3px;">Splitmate</td>
        </tr></table>
        <p style="margin:12px 0 0;font-size:13px;color:rgba(255,255,255,0.85);">Split bills, not friendships.</p>
      </td></tr>
      <tr><td style="padding:32px;">
        <h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:{BRAND_DARK};">{escape(heading)}</h1>
        {paragraph_html}
        {code_html}
        {button_html}
        {footnote_html}
      </td></tr>
      <tr><td style="padding:20px 32px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:12px;line-height:1.6;color:#94a3b8;text-align:center;">
        Sent by Splitmate &middot; Shared expenses, tasks and notes for your groups.
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
            f'Welcome to Splitmate, {user.name}!',
            ['Enter this code to verify your email and finish setting up your account.'],
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
            [f'Hi {user.name}, we got a request to reset your Splitmate password. Tap the button to choose a new one.'],
            button=('Choose a new password', reset_url),
            footnote=f'This link works once and expires in {expiry_minutes} minutes. '
                     'If you did not ask for this, your password stays the same.',
        ),
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
        'Splitmate\n',
        render_email(
            'Catch up on your shared expenses.',
            f'We miss you, {user.name}!',
            [
                f'It has been about {days_idle} days since you last opened Splitmate.',
                'Add recent expenses, settle up balances, or check what your group still needs.',
            ],
            footnote='If everything is already settled, you can ignore this reminder.',
        ),
    )


def send_group_invite_email(recipient, group, inviter, invite_url):
    expiry_days = current_app.config['GROUP_INVITE_EXPIRY_DAYS']
    return send_email(
        recipient,
        f'{inviter.name} invited you to {group.name} on Splitmate',
        f'Hi,\n\n'
        f'{inviter.name} invited you to join the "{group.name}" group on Splitmate.\n\n'
        f'Accept the invite here:\n{invite_url}\n\n'
        f'This invite expires in {expiry_days} days.\n\n'
        'Thanks,\n'
        'Splitmate\n',
        render_email(
            f'{inviter.name} wants you in {group.name}.',
            f'Join {group.name}',
            [f'{inviter.name} invited you to split expenses, tasks and notes in "{group.name}" on Splitmate.'],
            button=('Accept invite', invite_url),
            footnote=f'This invite expires in {expiry_days} days.',
        ),
    )


def send_splitmate_invite_email(recipient, inviter, join_url):
    return send_email(
        recipient,
        f'{inviter.name} invited you to join Splitmate',
        f'Hi,\n\n'
        f'{inviter.name} invited you to join Splitmate.\n\n'
        'Splitmate helps roommates, friends, and groups track shared expenses, notes, and tasks together.\n\n'
        f'Join here:\n{join_url}\n\n'
        'Thanks,\n'
        'Splitmate\n',
        render_email(
            f'{inviter.name} invited you to Splitmate.',
            'You are invited to Splitmate',
            [
                f'{inviter.name} uses Splitmate to keep shared expenses fair and simple.',
                'Track who paid, see who owes what, and settle up in a tap, with roommates, friends or travel groups.',
            ],
            button=('Join Splitmate', join_url),
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
            footnote='We send this alert every time payment details change, so nobody can redirect your money quietly.',
        ),
    )


def send_money_request_email(payer, requester, group, amount):
    amount_text = f'${amount:,.2f}'
    return send_email(
        payer.email,
        f'{requester.name} asked you to pay {amount_text} on Splitmate',
        f'Hi {payer.name},\n\n{requester.name} asked you to pay {amount_text} for "{group.name}".\n'
        'Open Splitmate to approve or decline. Splitmate never sends payment links; only pay from your own bank app.\n',
        render_email(
            f'{requester.name} asked you to pay {amount_text}.',
            'Payment request',
            [f'{requester.name} asked you to pay {amount_text} for "{group.name}".',
             'Open Splitmate, check the amount matches what you owe, then approve or decline.'],
            footnote='Splitmate never sends payment links. Only send money from your own bank app.',
        ),
    )
