"""Splitmate points: earned by inviting friends and settling up, spent on Pro time and extra scans.

Points have no cash value and are never paid out, so nothing here costs Splitmate money. Earning
that friends could fake (settling up) is capped per month; friends joining needs a verified email and
is capped too; a friend going Pro is a real Stripe payment.
"""
from datetime import datetime, timedelta

from app import db
from app.models import Referral, RewardTransaction

POINTS_EARNING_PAUSED = False

REFERRAL_JOIN_POINTS = 200
REFERRAL_JOINS_PER_MONTH = 5
REFERRAL_PRO_POINTS = 500
SETTLE_POINTS = 10
SETTLE_POINTS_PER_MONTH = 50

REWARDS = [
    {'id': 'scans_5', 'points': 100, 'label': '5 extra receipt scans',
     'description': 'Added on top of your free scans. They never expire.'},
    {'id': 'compares_5', 'points': 100, 'label': '5 extra grocery comparisons',
     'description': 'Added on top of your free comparisons. They never expire.'},
    {'id': 'pro_week', 'points': 500, 'label': '1 week of Pro',
     'description': 'Unlimited scans and comparisons for 7 days.'},
    {'id': 'pro_month', 'points': 1500, 'label': '1 month of Pro',
     'description': 'Unlimited scans and comparisons for 30 days.'},
]
REWARDS_BY_ID = {reward['id']: reward for reward in REWARDS}

WAYS_TO_EARN = [
    {'points': REFERRAL_JOIN_POINTS, 'label': 'A friend you invited joins Splitmate',
     'limit': f'Up to {REFERRAL_JOINS_PER_MONTH} friends a month'},
    {'points': REFERRAL_PRO_POINTS, 'label': 'A friend you invited goes Pro', 'limit': 'Once per friend'},
    {'points': SETTLE_POINTS, 'label': 'You settle up and the other person confirms',
     'limit': f'Up to {SETTLE_POINTS_PER_MONTH} points a month'},
]


def _month_start():
    now = datetime.utcnow()
    return datetime(now.year, now.month, 1)


def _earned_this_month(user, kind):
    rows = RewardTransaction.query.filter(
        RewardTransaction.user_id == user.id,
        RewardTransaction.type == kind,
        RewardTransaction.created_at >= _month_start(),
    ).all()
    return len(rows), sum(row.points for row in rows)


def _add(user, points, kind, note, source_user=None):
    user.reward_points = int(user.reward_points or 0) + points
    transaction = RewardTransaction(user_id=user.id, points=points, type=kind, note=note,
                                    source_user_id=source_user.id if source_user else None)
    db.session.add(transaction)
    return transaction


def record_referral(inviter, email):
    """Remember who invited this email, once per inviter, so a sign-up can credit them."""
    if not Referral.query.filter_by(inviter_id=inviter.id, email=email).first():
        db.session.add(Referral(inviter_id=inviter.id, email=email))
        db.session.commit()


def tell_inviter(transaction):
    """Email the inviter that they earned points. Best effort, after the caller commits."""
    if transaction is None:
        return
    from flask import current_app
    from app.email_utils import send_points_earned_email
    user = transaction.user
    try:
        send_points_earned_email(user, transaction.points, transaction.note, int(user.reward_points or 0))
    except Exception as exc:
        current_app.logger.exception('Failed to send points email: %s', exc)


def award_referral_join(new_user):
    """The friend who invited this new account gets points. The caller commits."""
    inviter = new_user.referred_by
    if POINTS_EARNING_PAUSED or inviter is None or inviter.id == new_user.id:
        return None
    count, _ = _earned_this_month(inviter, 'referral_join')
    if count >= REFERRAL_JOINS_PER_MONTH:
        return None
    return _add(inviter, REFERRAL_JOIN_POINTS, 'referral_join', f'{new_user.name} joined Splitmate', new_user)


def award_referral_pro(user):
    """The first time someone goes Pro, the friend who invited them gets points. The caller commits."""
    inviter = user.referred_by
    if POINTS_EARNING_PAUSED or inviter is None:
        return None
    already = RewardTransaction.query.filter_by(user_id=inviter.id, type='referral_pro', source_user_id=user.id).first()
    if already:
        return None
    return _add(inviter, REFERRAL_PRO_POINTS, 'referral_pro', f'{user.name} went Pro', user)


def award_settle(payment):
    """The payer gets points once the receiver confirms the money arrived. The caller commits."""
    payer = payment.payer
    if POINTS_EARNING_PAUSED or payer is None or payment.amount is None or payment.amount < 1:
        return None
    _, earned = _earned_this_month(payer, 'settle')
    points = min(SETTLE_POINTS, SETTLE_POINTS_PER_MONTH - earned)
    if points <= 0:
        return None
    payment.reward_points_awarded = points
    return _add(payer, points, 'settle', 'Settled up with a friend', payment.receiver)


def redeem(user, reward_id):
    """Spend points on a reward. Returns an error message, or None when it worked. The caller commits."""
    reward = REWARDS_BY_ID.get(reward_id)
    if reward is None:
        return 'Choose a reward.'
    if int(user.reward_points or 0) < reward['points']:
        return f'You need {reward["points"]} points for {reward["label"]}.'
    if reward_id == 'scans_5':
        user.bonus_receipt_scans = int(user.bonus_receipt_scans or 0) + 5
    elif reward_id == 'compares_5':
        user.bonus_grocery_compares = int(user.bonus_grocery_compares or 0) + 5
    else:
        days = 7 if reward_id == 'pro_week' else 30
        now = datetime.utcnow()
        start = user.points_pro_until if user.points_pro_until and user.points_pro_until > now else now
        user.points_pro_until = start + timedelta(days=days)
    _add(user, -reward['points'], 'redeem', reward['label'])
    return None


def rewards_payload(user):
    balance = int(user.reward_points or 0)
    pro_until = user.points_pro_until if user.points_pro_until and user.points_pro_until > datetime.utcnow() else None
    return {
        'points': balance,
        'rewards': [{**reward, 'affordable': balance >= reward['points']} for reward in REWARDS],
        'ways_to_earn': WAYS_TO_EARN,
        'points_pro_until': pro_until.isoformat() if pro_until else None,
        'bonus_receipt_scans': int(user.bonus_receipt_scans or 0),
        'bonus_grocery_compares': int(user.bonus_grocery_compares or 0),
        'earning_paused': POINTS_EARNING_PAUSED,
    }
