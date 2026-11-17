/** What each action earns. Keep in step with Splitmate-Web/app/rewards.py. */
export const POINTS = {
  friendJoins: 200,
  friendGoesPro: 500,
  settleUp: 10
};

export const INVITE_POINTS_NOTE = `You earn ${POINTS.friendJoins} points if they're new to Splitmate and join.`;
export const SETTLE_POINTS_NOTE = `You earn ${POINTS.settleUp} points once they confirm (up to 50 a month).`;
