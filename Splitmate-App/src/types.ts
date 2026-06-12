export type User = {
  id: number;
  name: string;
  email: string;
  is_email_verified: boolean;
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
  is_completed: boolean;
  assigned_to_id?: number | null;
  assigned_to?: string | null;
  created_by: string;
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
  group_id: number;
  group_name: string;
};

export type Payment = {
  id: number;
  amount: number;
  date: string | null;
  payer: string;
  receiver: string;
  method: string;
  status: string;
};

export type GroupDetail = {
  group: Group;
  balances: Balance[];
  summaries: SplitSummary[];
  expenses: Expense[];
  tasks: Task[];
  notes: Note[];
  payments: Payment[];
};

export type AuthResponse = {
  token: string;
  user: User;
  currency_code: string;
};

export type RootStackParamList = {
  Auth: undefined;
  Home: undefined;
  GroupDetail: { groupId: number; groupName: string };
  AddExpense: { groupId: number; members: GroupMember[] };
  AddTask: { groupId: number; members: GroupMember[] };
  Settings: undefined;
};
