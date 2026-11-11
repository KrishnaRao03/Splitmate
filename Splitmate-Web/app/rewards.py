# Points were only earned on verified Stripe payments. In-app Stripe collection was removed, and
# confirmed manual payments can't earn points (two friends could confirm fake payments to farm gift
# cards), so earning is paused. Existing balances and history are kept and still shown.
POINTS_EARNING_PAUSED = True
REWARD_TIERS = [
    {
        'points': 500,
        'label': '$5 gift card',
        'description': 'Starter reward for active settlement users.'
    },
    {
        'points': 1000,
        'label': '$10 gift card',
        'description': 'Best first launch milestone.'
    },
    {
        'points': 2500,
        'label': '$25 gift card',
        'description': 'High-trust reward once fraud controls are ready.'
    },
]

MEMBERSHIP_PLANS = [
    {
        'id': 'free',
        'name': 'Free',
        'price': '$0',
        'interval': 'forever',
        'badge': 'Current starter',
        'features': [
            'Split expenses, tasks, and notes',
            'Settle up with Interac, PayPal or UPI links',
            'Basic grocery price compare'
        ]
    },
    {
        'id': 'plus',
        'name': 'Splitmate Plus',
        'price': '$4.99',
        'interval': 'month',
        'badge': 'Recommended',
        'features': [
            'Ad-light experience',
            'Live grocery price history and alerts',
            'Advanced spending insights',
            '2x points promos when profitable',
            'Priority support chat'
        ]
    },
]


def next_reward_tier(points):
    balance = int(points or 0)
    for tier in REWARD_TIERS:
        if balance < tier['points']:
            return tier
    return REWARD_TIERS[-1]


def reward_progress(points):
    balance = int(points or 0)
    tier = next_reward_tier(balance)
    target = tier['points']
    percent = min(100, round((balance / target) * 100)) if target else 100
    return {
        'balance': balance,
        'target': target,
        'remaining': max(0, target - balance),
        'percent': percent,
        'tier': tier,
        'redeemable': balance >= REWARD_TIERS[0]['points'],
    }

