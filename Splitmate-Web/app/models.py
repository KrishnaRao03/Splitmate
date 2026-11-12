from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from app.field_encryption import EncryptedString

# Wrong codes allowed before an emailed OTP stops working and a new one is needed.
MAX_OTP_ATTEMPTS = 5

# Association table for group members
group_members = db.Table('group_members',
                         db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
                         db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True),
                         db.Column('nickname', db.String(100))
                         )

class EmailOtpMixin:
    """Emailed one-time code handling, shared by users and pending sign-ups."""

    def set_email_otp(self, otp, expires_at):
        self.email_otp_hash = generate_password_hash(otp)
        self.email_otp_expires_at = expires_at
        self.email_otp_sent_at = datetime.utcnow()
        self.email_otp_attempts = 0

    def otp_attempts_exhausted(self):
        return (self.email_otp_attempts or 0) >= MAX_OTP_ATTEMPTS

    def check_email_otp(self, otp):
        """Checks the code and counts wrong guesses; after MAX_OTP_ATTEMPTS the code is dead."""
        if not self.email_otp_hash or not otp or self.otp_attempts_exhausted():
            return False
        if check_password_hash(self.email_otp_hash, otp):
            return True
        self.email_otp_attempts = (self.email_otp_attempts or 0) + 1
        return False

    def clear_email_otp(self):
        self.email_otp_hash = None
        self.email_otp_expires_at = None
        self.email_otp_sent_at = None
        self.email_otp_attempts = 0


class User(EmailOtpMixin, UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)
    last_activity_at = db.Column(db.DateTime)
    last_inactivity_email_sent_at = db.Column(db.DateTime)
    is_suspended = db.Column(db.Boolean, default=False, nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_otp_hash = db.Column(db.String(256))
    email_otp_expires_at = db.Column(db.DateTime)
    email_otp_sent_at = db.Column(db.DateTime)
    email_otp_attempts = db.Column(db.Integer, default=0, nullable=False)
    # Bumped on password change/reset and "log out everywhere"; old tokens and links stop working.
    token_version = db.Column(db.Integer, default=0, nullable=False)
    # Where other members can send this user money (the app only links out; it never holds funds).
    # Encrypted in the database with FIELD_ENCRYPTION_KEY; see app/field_encryption.py.
    interac_email = db.Column(EncryptedString)
    paypal_username = db.Column(EncryptedString)
    upi_id = db.Column(EncryptedString)
    stripe_account_id = db.Column(db.String(255))
    stripe_charges_enabled = db.Column(db.Boolean, default=False, nullable=False)
    stripe_payouts_enabled = db.Column(db.Boolean, default=False, nullable=False)
    reward_points = db.Column(db.Integer, default=0, nullable=False)
    membership_plan = db.Column(db.String(30), default='free', nullable=False)
    membership_status = db.Column(db.String(30), default='active', nullable=False)

    administered_groups = db.relationship('Group', backref='admin', lazy='dynamic')
    expenses = db.relationship('Expense', backref='added_by', lazy='dynamic')

    def get_id(self):
        # The web session remembers the token version too, so a password change signs out other browsers.
        return f'{self.id}:{self.token_version or 0}'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.revoke_sessions()

    def revoke_sessions(self):
        self.token_version = (self.token_version or 0) + 1

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(id):
    user_id, _, version = str(id).partition(':')
    try:
        user = db.session.get(User, int(user_id))
    except ValueError:
        return None
    if not user or str(user.token_version or 0) != (version or '0'):
        return None
    return user

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    default_split_type = db.Column(db.String(20), default='equal', nullable=False)
    default_split_config = db.Column(db.Text)

    members = db.relationship('User', secondary=group_members,
                              backref=db.backref('groups', lazy='dynamic'))
    expenses = db.relationship('Expense', backref='group', lazy='dynamic',
                               cascade='all, delete-orphan')
    notes = db.relationship('Note', backref='group', lazy='dynamic',
                            cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='group', lazy='dynamic',
                            cascade='all, delete-orphan')
    histories = db.relationship('ExpenseHistory', backref='group', lazy='dynamic',
                                cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='group', lazy='dynamic',
                               cascade='all, delete-orphan')
    invites = db.relationship('GroupInvite', backref='group', lazy='dynamic',
                              cascade='all, delete-orphan')

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(40), default='General', nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    receipt_url = db.Column(db.String(500))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    paid_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    splits = db.relationship('ExpenseSplit', backref='expense', lazy='dynamic',
                             cascade='all, delete-orphan')

class ExpenseSplit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expense.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount_owed = db.Column(db.Float, nullable=False)
    is_settled = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='owed_splits')

class ExpenseHistory(db.Model):
    """Immutable copy of each expense for transaction history and analytics."""
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(40), default='General', nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    paid_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    method = db.Column(db.String(30), default='manual', nullable=False)
    stripe_checkout_session_id = db.Column(db.String(255), unique=True, index=True)
    status = db.Column(db.String(30), default='recorded', nullable=False)
    reward_points_awarded = db.Column(db.Integer, default=0, nullable=False)

    payer = db.relationship('User', foreign_keys=[payer_id], backref='payments_sent')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='payments_received')

class RewardTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), unique=True)
    points = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(30), default='earn', nullable=False)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('reward_transactions', lazy='dynamic'))
    payment = db.relationship('Payment', backref=db.backref('reward_transaction', uselist=False))

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    created_by = db.relationship('User', backref='notes')

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime, nullable=False)
    reminder_time = db.Column(db.DateTime)
    priority = db.Column(db.String(20), default='medium', nullable=False)
    recurrence = db.Column(db.String(20), default='none', nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref='assigned_tasks')
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_tasks')

class GroupInvite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    invited_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    accepted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime)
    revoked_at = db.Column(db.DateTime)

    invited_by = db.relationship('User', foreign_keys=[invited_by_id], backref='sent_group_invites')
    accepted_by = db.relationship('User', foreign_keys=[accepted_by_id], backref='accepted_group_invites')

class MobileDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expo_push_token = db.Column(db.String(255), nullable=False, unique=True, index=True)
    platform = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='mobile_devices')

class AdminAuditLog(db.Model):
    """Who did what in the admin panel. Rows are only ever added."""
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    admin_email = db.Column(db.String(120))
    action = db.Column(db.String(60), nullable=False)
    target_type = db.Column(db.String(30))
    target_id = db.Column(db.Integer)
    detail = db.Column(db.String(500))
    ip_address = db.Column(db.String(64))


class PendingRegistration(EmailOtpMixin, db.Model):
    """A sign-up waiting for its email code. The User row is created only once the code is verified."""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email_otp_hash = db.Column(db.String(256))
    email_otp_expires_at = db.Column(db.DateTime)
    email_otp_sent_at = db.Column(db.DateTime)
    email_otp_attempts = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def create_user(self):
        """The verified account. The caller deletes this pending row and commits."""
        return User(email=self.email, name=self.name, password_hash=self.password_hash, is_email_verified=True)
