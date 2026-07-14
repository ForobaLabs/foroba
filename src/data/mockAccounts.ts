export interface MockAccount {
  id: string;
  bank: string;
  name: string;
  type: 'Checking' | 'Savings';
  ibanLast4: string;
  balanceEur: number;
}

export interface MockTransaction {
  id: string;
  date: string;
  merchant: string;
  category: string;
  amountEur: number;
}

export interface MonthlyCashflow {
  month: string;
  incomeEur: number;
  expensesEur: number;
}

export const MOCK_ACCOUNTS: MockAccount[] = [
  { id: 'acc-1', bank: 'Revolut', name: 'Main Checking', type: 'Checking', ibanLast4: '4821', balanceEur: 3420.18 },
  { id: 'acc-2', bank: 'BNL', name: 'Savings Account', type: 'Savings', ibanLast4: '7793', balanceEur: 12850.0 },
  { id: 'acc-3', bank: 'Boursorama', name: 'Compte Courant', type: 'Checking', ibanLast4: '0156', balanceEur: 1180.42 },
];

export const MOCK_TRANSACTIONS: MockTransaction[] = [
  { id: 'tx-1', date: '2026-06-28', merchant: 'Carrefour', category: 'Groceries', amountEur: -68.4 },
  { id: 'tx-2', date: '2026-06-27', merchant: 'Salary — Acme Corp', category: 'Income', amountEur: 3200.0 },
  { id: 'tx-3', date: '2026-06-26', merchant: 'EDF', category: 'Utilities', amountEur: -94.1 },
  { id: 'tx-4', date: '2026-06-24', merchant: 'Netflix', category: 'Subscriptions', amountEur: -15.99 },
  { id: 'tx-5', date: '2026-06-22', merchant: 'Trenitalia', category: 'Transport', amountEur: -42.5 },
  { id: 'tx-6', date: '2026-06-20', merchant: 'Ristorante Da Mario', category: 'Dining', amountEur: -56.0 },
  { id: 'tx-7', date: '2026-06-18', merchant: 'Amazon', category: 'Shopping', amountEur: -129.99 },
  { id: 'tx-8', date: '2026-06-15', merchant: 'Rent — Landlord SRL', category: 'Housing', amountEur: -950.0 },
];

export const MOCK_CASHFLOW: MonthlyCashflow[] = [
  { month: '2026-01', incomeEur: 3200, expensesEur: 2450 },
  { month: '2026-02', incomeEur: 3200, expensesEur: 2680 },
  { month: '2026-03', incomeEur: 3450, expensesEur: 2390 },
  { month: '2026-04', incomeEur: 3200, expensesEur: 2510 },
  { month: '2026-05', incomeEur: 3200, expensesEur: 2920 },
  { month: '2026-06', incomeEur: 3200, expensesEur: 2640 },
];
