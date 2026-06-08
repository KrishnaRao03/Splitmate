from datetime import datetime, timedelta
import secrets

from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from app import db
from app.email_utils import send_password_reset_email, send_verification_otp
from app.models import User

auth_bp = Blueprint('auth', __name__)

def generate_otp():
    return f'{secrets.randbelow(1000000):06d}'

def generate_password_reset_token(user):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(
        {'user_id': user.id, 'email': user.email},
        salt='password-reset'
    )

def verify_password_reset_token(token):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    max_age = current_app.config['PASSWORD_RESET_EXPIRY_MINUTES'] * 60

    try:
        data = serializer.loads(token, salt='password-reset', max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

    user = User.query.get(data.get('user_id'))
    if not user or user.email != data.get('email'):
        return None

    return user

def send_user_otp(user):
    otp = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=current_app.config['OTP_EXPIRY_MINUTES'])
    user.set_email_otp(otp, expires_at)
    try:
        sent = send_verification_otp(user, otp)
    except Exception:
        user.clear_email_otp()
        db.session.commit()
        raise

    if sent:
        db.session.commit()
    else:
        user.clear_email_otp()
        db.session.commit()

    return sent

def set_pending_verification(user):
    session['pending_verification_user_id'] = user.id
    session['pending_verification_email'] = user.email

def mark_user_logged_in(user):
    now = datetime.utcnow()
    user.last_login_at = now
    user.last_activity_at = now
    db.session.commit()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, go to home
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_email_verified:
                set_pending_verification(user)
                if not user.email_otp_hash or not user.email_otp_expires_at or user.email_otp_expires_at <= datetime.utcnow():
                    try:
                        sent = send_user_otp(user)
                    except Exception as exc:
                        current_app.logger.exception('Failed to send verification OTP: %s', exc)
                        sent = False

                    if sent:
                        flash('A new verification code was sent to your email.', 'info')
                    else:
                        flash('Your email is not verified, but the OTP email could not be sent. Check MAIL_PASSWORD.', 'error')
                else:
                    flash('Please verify your email with the OTP we sent.', 'info')
                return redirect(url_for('auth.verify_email'))

            login_user(user, remember=True)
            mark_user_logged_in(user)
            # Redirect to the page they were trying to access, or home
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('main.home'))

        flash('Invalid email or password', 'error')

    return render_template('login.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first() if email else None

        if user:
            token = generate_password_reset_token(user)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            try:
                sent = send_password_reset_email(user, reset_url)
            except Exception as exc:
                current_app.logger.exception('Failed to send password reset email: %s', exc)
                sent = False

            if not sent:
                flash('Could not send the password reset email. Check MAIL_PASSWORD.', 'error')
                return render_template('forgot_password.html')

        flash('If an account exists for that email, password reset instructions were sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    user = verify_password_reset_token(token)
    if not user:
        flash('That password reset link is invalid or expired. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        errors = []

        if len(password) < 6:
            errors.append('Password must be at least 6 characters')
        if password != confirm_password:
            errors.append('Passwords do not match')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('reset_password.html')

        user.set_password(password)
        db.session.commit()
        flash('Your password has been reset. Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        errors = []
        if not email or '@' not in email:
            errors.append('Valid email is required')
        if not name:
            errors.append('Name is required')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters')
        if password != confirm_password:
            errors.append('Passwords do not match')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')

        # Create user
        user = User(email=email, name=name, is_email_verified=False)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        try:
            sent = send_user_otp(user)
        except Exception as exc:
            current_app.logger.exception('Failed to send verification OTP: %s', exc)
            sent = False

        db.session.commit()
        set_pending_verification(user)

        if sent:
            flash('Registration successful. We sent a 6-digit OTP to your email.', 'success')
        else:
            flash('Account created, but the OTP email could not be sent. Check MAIL_PASSWORD and resend the code.', 'error')
        return redirect(url_for('auth.verify_email'))

    return render_template('register.html')

@auth_bp.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    user_id = session.get('pending_verification_user_id')
    verifying_authenticated_user = False

    if current_user.is_authenticated:
        if not user_id and not current_user.is_email_verified:
            set_pending_verification(current_user)
            user_id = current_user.id

        if not user_id or int(user_id) != current_user.id or current_user.is_email_verified:
            return redirect(url_for('main.home'))

        user = current_user
        verifying_authenticated_user = True
    else:
        if not user_id:
            flash('Please register or log in first.', 'info')
            return redirect(url_for('auth.login'))

        user = User.query.get(user_id)

    if not user:
        session.pop('pending_verification_user_id', None)
        session.pop('pending_verification_email', None)
        flash('Verification session expired. Please register again.', 'error')
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()

        if user.email_otp_expires_at and user.email_otp_expires_at < datetime.utcnow():
            flash('That OTP has expired. Please request a new code.', 'error')
            return render_template('verify_email.html', email=user.email)

        if user.check_email_otp(otp):
            user.is_email_verified = True
            user.clear_email_otp()
            db.session.commit()
            session.pop('pending_verification_user_id', None)
            session.pop('pending_verification_email', None)
            if not current_user.is_authenticated:
                login_user(user, remember=True)
                mark_user_logged_in(user)
            flash('Email verified successfully.', 'success')
            return redirect(url_for('main.profile' if verifying_authenticated_user else 'main.home'))

        flash('Invalid OTP. Please try again.', 'error')

    return render_template('verify_email.html', email=user.email)

@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    user_id = session.get('pending_verification_user_id')
    if current_user.is_authenticated and not user_id and not current_user.is_email_verified:
        set_pending_verification(current_user)
        user_id = current_user.id

    if not user_id:
        flash('Please register or log in first.', 'info')
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user:
        flash('Verification session expired. Please register again.', 'error')
        return redirect(url_for('auth.register'))

    if user.email_otp_sent_at:
        cooldown_until = user.email_otp_sent_at + timedelta(seconds=current_app.config['OTP_RESEND_COOLDOWN_SECONDS'])
        if cooldown_until > datetime.utcnow():
            flash('Please wait a moment before requesting another OTP.', 'info')
            return redirect(url_for('auth.verify_email'))

    try:
        sent = send_user_otp(user)
    except Exception as exc:
        current_app.logger.exception('Failed to resend verification OTP: %s', exc)
        sent = False

    if sent:
        flash('A new OTP was sent to your email.', 'success')
    else:
        flash('Could not send OTP email. Check MAIL_PASSWORD.', 'error')

    return redirect(url_for('auth.verify_email'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('pending_verification_user_id', None)
    session.pop('pending_verification_email', None)
    return redirect(url_for('auth.login'))
