/** Where other members can send this user money. Splitmate only links out; it never holds funds. */
export type PaymentHandles = {
  interac_email?: string;
  paypal_username?: string;
  upi_id?: string;
};

export type User = PaymentHandles & {
  id: number;
  name: string;
  email: string;
  /** Optional, unique per account (stored as +digits). */
  phone?: string;
  is_email_verified: boolean;
  /** Others see the Interac email only once its code has been entered. */
  interac_email_verified?: boolean;
  /** A new Interac email waiting for its code; the old one stays in use until then. */
  pending_interac_email?: string;
  created_at?: string | null;
};

export type GroupMember = {
  id: number;
  name: string;
  nickname: string;
  full_name: string;
  email: string;
};

export type Group = {
  id: number;
  name: string;
  admin_id: number;
  members: GroupMember[];
};

export type Balance = {
  id: number;
  name: string;
  paid: number;
  owes: number;
  net: number;
};

export type SplitSummary = {
  split_id: number;
  expense: string;
  expense_amount: number;
  date: string | null;
  payer_id: number;
  payer: string;
  owed_by_id: number;
  owed_by: string;
  amount_owed: number;
  is_settled: boolean;
  status: string;
  status_label: string;
};

export type Expense = {
  id: number;
  description: string;
  amount: number;
  category: string;
  date: string | null;
  paid_by_id: number;
  paid_by: string;
  receipt_url?: string | null;
  splits: Array<{
    id: number;
    user_id: number;
    user: string;
    amount: number;
    is_settled: boolean;
  }>;
};

export type Task = {
  id: number;
  title: string;
  description: string;
  due_date: string | null;
  reminder_time: string | null;
  priority: 'low' | 'medium' | 'high';
  recurrence: 'none' | 'daily' | 'weekly' | 'monthly';
  is_overdue: boolean;
  is_completed: boolean;
  assigned_to_id?: number | null;
  assigned_to?: string | null;
  created_by: string;
  created_by_id: number;
  /** Only the creator or the group admin may delete a task. */
  can_delete: boolean;
  group_id: number;
  group_name: string;
};

export type Note = {
  id: number;
  title: string;
  description: string;
  content: string;
  is_completed: boolean;
  created_at: string | null;
  created_by: string;
  created_by_id: number;
  /** Only the writer or the group admin may delete a note. */
  can_delete: boolean;
  group_id: number;
  group_name: string;
  can_compare_prices?: boolean;
};

/** Response of POST /receipts/scan: the line items read off a receipt photo. */
/** This month's use of a feature with a free limit; limit and remaining are null on Pro (unlimited). */
export type FeatureUsage = { used: number; limit: number | null; remaining: number | null };

export type ReceiptScan = {
  usage?: FeatureUsage;
  merchant: string;
  currency: string;
  items: Array<{ name: string; quantity: number; price: number }>;
  tax: number;
  total: number;
};

export type Payment = {
  id: number;
  amount: number;
  date: string | null;
  payer_id: number;
  receiver_id: number;
  payer: string;
  receiver: string;
  method: string;
  /** 'pending' until the receiver confirms; then 'recorded'. 'declined' if they say it never arrived. */
  status: string;
  status_label: string;
  can_confirm: boolean;
  can_decline: boolean;
  reward_points_awarded?: number;
};

export type PendingInvite = {
  id: number;
  email: string;
  created_at: string | null;
  expires_at: string | null;
  invited_by: string;
};

export type DefaultSplit = {
  type: 'equal' | 'selected' | 'percentage';
  member_ids: string[];
  percentages: Record<string, string>;
};

export type PaymentMethod = {
  type: 'interac' | 'paypal' | 'upi';
  label: string;
  handle: string;
  /** Interac only: the email with most letters hidden, shown on screen while Copy uses the full one. */
  masked?: string;
  /** null for Interac, which has no universal pay link: the payer copies the email instead. */
  url: string | null;
};

export type PaymentOption = {
  receiver_id: number;
  receiver: string;
  /** What can still be recorded: what's owed minus payments already waiting for confirmation. */
  max_amount: number;
  owed: number;
  pending_amount: number;
  payment_methods: PaymentMethod[];
};

export type Analytics = {
  total: number;
  count: number;
  top_category: string;
  category_totals: Array<{ category: string; total: number }>;
  payer_totals: Array<{ name: string; total: number }>;
  monthly_totals: Array<{ month: string; label: string; total: number }>;
};

export type Transaction = {
  id: number;
  type: 'expense' | 'payment';
  description: string;
  amount: number;
  category?: string;
  date: string | null;
  paid_by?: string;
  payer?: string;
  receiver?: string;
  method?: string;
  status?: string;
};

export type ExpenseSearchResult = {
  id: number;
  description: string;
  amount: number;
  category: string;
  date: string | null;
  paid_by: string;
};

export type GroupActivity = {
  expense_results: Transaction[];
  transactions: Transaction[];
  analytics: Analytics;
};

export type Dashboard = {
  groups: Group[];
  monthly_spending: Array<{ group_id: number; group: string; total: number }>;
  recent_expenses: Array<Expense & { group_id: number; group_name: string }>;
  total_owed_to_user: number;
  total_user_owes: number;
  chart_data: Array<{
    group_id: number;
    group: string;
    data: Array<{ month: string; label: string; total: number }>;
  }>;
  spending_insights: {
    total: number;
    count: number;
    average?: number;
    top_category: string;
    category_totals: Array<{ category: string; total: number }>;
    payer_totals: Array<{ name: string; total: number }>;
    group_totals?: Array<{ name: string; total: number }>;
    monthly_totals?: Array<{ month: string; label: string; total: number }>;
  };
};

export type GroceryLine = {
  requested: { name?: string; raw?: string; quantity?: number; unit?: string };
  status: 'available' | 'unavailable' | 'missing';
  matched_item: string | null;
  brand?: string | null;
  size?: string;
  unit_price: number | null;
  line_total: number;
  /** 'trimcart' = weekly flyer price, 'web' = found on the store's website via Google Search. */
  source?: 'trimcart' | 'web';
  source_url?: string | null;
};

export type GroceryStore = {
  rank: number;
  store_name: string;
  /** Nearest branch found online, or the searched location. */
  location?: string;
  total: number;
  available_count: number;
  unavailable_count?: number;
  missing_count?: number;
  requested_count: number;
  all_items_available: boolean;
  items?: GroceryLine[];
};

export type GroceryComparison = {
  usage?: FeatureUsage;
  note_id?: number;
  currency: string;
  catalog_source?: string;
  location?: string;
  requested_items: Array<{ name?: string; raw?: string; quantity?: number; unit?: string }>;
  top_store?: GroceryStore | null;
  stores: GroceryStore[];
};

export type GroupDetail = {
  group: Group;
  current_user_id: number;
  pending_invites: PendingInvite[];
  default_split: DefaultSplit;
  expense_categories: string[];
  balances: Balance[];
  summaries: SplitSummary[];
  expenses: Expense[];
  tasks: Task[];
  notes: Note[];
  payments: Payment[];
  payment_options: PaymentOption[];
  /** People who owe the current user, with the email to send an Interac "Request money" to. */
  money_requests: MoneyRequest[];
  requests_for_me: RequestForMe[];
};

export type MoneyRequest = {
  payer_id: number;
  payer: string;
  amount: number;
  request_id: number | null;
  request_status: 'none' | 'pending' | 'approved' | 'declined';
  /** Only sent once the payer approves the request. */
  email: string | null;
  masked_email: string | null;
};

/** Someone asking the current user to pay; approving shows them where to send the Interac request. */
export type RequestForMe = {
  id: number;
  requester_id: number;
  requester: string;
  amount: number;
  created_at: string | null;
};

export type PersonBalance = {
  user_id: number;
  name: string;
  net: number;
  groups: { group_id: number; group_name: string; net: number }[];
};

export type AuthResponse = {
  token: string;
  user: User;
  currency_code: string;
};

export type RewardTier = {
  points: number;
  label: string;
  description: string;
};

export type RewardTransactionRow = {
  id: number;
  points: number;
  type: string;
  note: string;
  created_at: string | null;
};

export type MembershipPlan = {
  id: string;
  name: string;
  price: string;
  interval: string;
  badge: string;
  features: string[];
  /** 'month' or 'year' for a Pro plan that can be bought; null for Free. */
  checkout_interval: 'month' | 'year' | null;
  is_current: boolean;
};

export type ProfileQr = {
  payload: string;
  size: number;
  rows: string[];
};

export type MyInvite = {
  id: number;
  group_id: number;
  group_name: string;
  invited_by: string;
  created_at: string | null;
  expires_at: string | null;
};

export type RewardsSummary = {
  points: number;
  progress: {
    balance: number;
    target: number;
    remaining: number;
    percent: number;
    tier: RewardTier;
    redeemable: boolean;
  };
  membership_plan: string;
  membership_status: string;
  membership_interval?: string;
  membership_renews_at?: string | null;
  membership_cancel_at_period_end?: boolean;
  /** False until the Stripe keys are added on the server. */
  billing_enabled?: boolean;
  usage?: { receipt_scan: FeatureUsage; grocery_compare: FeatureUsage };
  tiers?: RewardTier[];
  recent_transactions?: RewardTransactionRow[];
  membership_plans?: MembershipPlan[];
  earning_paused?: boolean;
};

export type MainTabParamList = {
  Home: undefined;
  Split: undefined;
  Tasks: undefined;
  Notes: undefined;
};

export type RootStackParamList = {
  Auth: undefined;
  /** The bottom tabs; named Main so it does not clash with the Home tab inside it. */
  Main: undefined;
  Groups: undefined;
  CreateGroup: undefined;
  QuickSplit: undefined;
  GroupDetail: { groupId: number; groupName: string };
  AddExpense: {
    groupId: number;
    members: GroupMember[];
    currentUserId: number;
    categories: string[];
    defaultSplit: DefaultSplit;
    /** When set, the screen edits this expense instead of creating a new one. */
    expense?: Expense;
  };
  /** Without params (from the Tasks tab) the screen asks which group the task is for. */
  AddTask: { groupId: number; members: GroupMember[] } | undefined;
  Profile: undefined;
  GroupSettings: { groupId: number; groupName: string };
  Insights: { groupId: number; groupName: string; members: GroupMember[]; categories: string[] };
  TaskCalendar: { groupId: number; groupName: string };
  Settings: undefined;
  Membership: undefined;
  HelpChat: undefined;
  Invites: undefined;
};
