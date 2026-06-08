from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

# Association table for group members
group_members = db.Table('group_members',
                         db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
                         db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True),
                         db.Column('nickname', db.String(100))
                         )

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_otp_hash = db.Column(db.String(256))
    email_otp_expires_at = db.Column(db.DateTime)
    email_otp_sent_at = db.Column(db.DateTime)
    stripe_account_id = db.Column(db.String(255))
    stripe_charges_enabled = db.Column(db.Boolean, default=False, nullable=False)
    stripe_payouts_enabled = db.Column(db.Boolean, default=False, nullable=False)

    administered_groups = db.relationship('Group', backref='admin', lazy='dynamic')
    expenses = db.relationship('Expense', backref='added_by', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_email_otp(self, otp, expires_at):
        self.email_otp_hash = generate_password_hash(otp)
        self.email_otp_expires_at = expires_at
        self.email_otp_sent_at = datetime.utcnow()

    def check_email_otp(self, otp):
        if not self.email_otp_hash or not otp:
            return False
        return check_password_hash(self.email_otp_hash, otp)

    def clear_email_otp(self):
        self.email_otp_hash = None
        self.email_otp_expires_at = None
        self.email_otp_sent_at = None

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

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

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
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

    payer = db.relationship('User', foreign_keys=[payer_id], backref='payments_sent')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='payments_received')

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
    is_completed = db.Column(db.Boolean, default=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref='assigned_tasks')
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_tasks')
