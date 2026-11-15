"""People deleting their own account, from the app or the website. Both app stores require this."""
from app import billing
from app.admin_utils import is_app_admin


def self_delete_error(user, password):
    """Why this account can't be deleted right now, or None when it can."""
    if not password or not user.check_password(password):
        return 'Enter your current password to delete your account.'
    if is_app_admin(user):
        return 'Admin accounts cannot be deleted from here.'
    if billing.is_paid_pro(user) and not user.membership_cancel_at_period_end:
        return 'Cancel Splitmate Pro first with Manage subscription, then delete your account.'
    return None


def delete_own_account(user):
    """Returns 'deleted' or 'anonymized'. The caller commits."""
    from app.routes.admin import audit, remove_account
    user_id, outcome = user.id, remove_account(user)
    audit(f'user.self_delete_{outcome}', 'user', user_id, 'Deleted by the account owner')
    return outcome
