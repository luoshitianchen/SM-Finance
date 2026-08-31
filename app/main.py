"""SM Finance —— 财务管理：总账科目、凭证、发票、预算与财务报表。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app import base

SERVICE = "sm-finance"
VERSION = "2.0.0"
NAME = "SM Finance"
DESCRIPTION = "财务管理：总账科目、凭证、发票、预算与财务报表"
PORT = 8520


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _init() -> None:
    with base.db_ctx() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                type TEXT NOT NULL, balance REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY, account_id TEXT NOT NULL, amount REAL NOT NULL,
                direction TEXT NOT NULL, description TEXT, status TEXT NOT NULL DEFAULT 'posted',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS invoices (
                id TEXT PRIMARY KEY, number TEXT NOT NULL UNIQUE, customer TEXT NOT NULL,
                amount REAL NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
                due_date TEXT NOT NULL, issued_at TEXT, paid_at TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS budgets (
                id TEXT PRIMARY KEY, department TEXT NOT NULL, period TEXT NOT NULL,
                amount REAL NOT NULL, spent REAL NOT NULL DEFAULT 0,
                UNIQUE(department, period)
            );
            CREATE INDEX IF NOT EXISTS idx_tx_account ON transactions(account_id, created_at DESC);
            """
        )


app = base.create_app(
    service=SERVICE, name=NAME, description=DESCRIPTION, version=VERSION, port=PORT,
    dependencies=["sm-iam", "sm-audit-log-center", "sm-workflow-approval"],
    events=["invoice.issued", "invoice.paid", "budget.exceeded"],
    overview_fn=lambda _r: {
        "summary": {
            "accounts": base.get_db().execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
            "outstanding_invoices": base.get_db().execute("SELECT COUNT(*) FROM invoices WHERE status IN ('sent','overdue')").fetchone()[0],
        }
    },
)
_init()


class AccountIn(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=60)
    type: str = Field(pattern=r"^(asset|liability|equity|revenue|expense)$")
    balance: float = Field(default=0)


class TransactionIn(BaseModel):
    account_id: str = Field(min_length=8)
    amount: float = Field(gt=0)
    direction: str = Field(pattern=r"^(debit|credit)$")
    description: str = Field(default="", max_length=300)


class InvoiceIn(BaseModel):
    number: str = Field(min_length=3, max_length=30)
    customer: str = Field(min_length=2, max_length=80)
    amount: float = Field(gt=0)
    due_date: str = Field(min_length=8, max_length=12)


class BudgetIn(BaseModel):
    department: str = Field(min_length=2, max_length=60)
    period: str = Field(min_length=6, max_length=10)
    amount: float = Field(gt=0)


@app.post("/api/finance/accounts", status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    account_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        try:
            conn.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?)", (account_id, payload.code, payload.name, payload.type, payload.balance, _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "科目代码已存在") from exc
    return {"id": account_id, "code": payload.code}


@app.get("/api/finance/accounts")
def list_accounts(type_: str | None = None) -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM accounts WHERE type=? ORDER BY code", (type_,)).fetchall() if type_ else conn.execute("SELECT * FROM accounts ORDER BY code").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/finance/transactions", status_code=status.HTTP_201_CREATED)
def post_transaction(payload: TransactionIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    tx_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        account = conn.execute("SELECT * FROM accounts WHERE id=?", (payload.account_id,)).fetchone()
        if not account:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "科目不存在")
        delta = payload.amount if payload.direction == "debit" else -payload.amount
        conn.execute("INSERT INTO transactions (id, account_id, amount, direction, description, status, created_at) VALUES (?,?,?,?,?,?,?)", (tx_id, payload.account_id, payload.amount, payload.direction, payload.description, "posted", _now()))
        conn.execute("UPDATE accounts SET balance=balance+? WHERE id=?", (delta, payload.account_id))
    return {"id": tx_id, "account_id": payload.account_id, "amount": payload.amount, "direction": payload.direction}


@app.get("/api/finance/transactions")
def list_transactions(account_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(500, limit))
    with base.db_ctx() as conn:
        if account_id:
            rows = conn.execute("SELECT * FROM transactions WHERE account_id=? ORDER BY created_at DESC LIMIT ?", (account_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/finance/invoices", status_code=status.HTTP_201_CREATED)
def create_invoice(payload: InvoiceIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    invoice_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        try:
            conn.execute("INSERT INTO invoices (id, number, customer, amount, status, due_date, issued_at, paid_at, created_at) VALUES (?,?,?,?,?,?,?,?,?)", (invoice_id, payload.number, payload.customer, payload.amount, "draft", payload.due_date, None, None, _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "发票号已存在") from exc
    return {"id": invoice_id, "number": payload.number, "status": "draft"}


@app.get("/api/finance/invoices")
def list_invoices(status_: str | None = None) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if status_:
            rows = conn.execute("SELECT * FROM invoices WHERE status=? ORDER BY created_at DESC", (status_,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM invoices ORDER BY created_at DESC LIMIT 200").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/finance/invoices/{invoice_id}/issue")
def issue_invoice(invoice_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        if conn.execute("UPDATE invoices SET status='sent', issued_at=? WHERE id=? AND status='draft'", (_now(), invoice_id)).rowcount == 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "发票不存在或不可开票")
        base.record_audit("invoice.issued", "internal", f"invoice={invoice_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": invoice_id, "status": "sent"}


@app.post("/api/finance/invoices/{invoice_id}/mark-overdue")
def mark_overdue(invoice_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        if conn.execute("UPDATE invoices SET status='overdue' WHERE id=? AND status='sent' AND due_date<date('now')", (invoice_id,)).rowcount == 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "发票不存在或未逾期")
    return {"id": invoice_id, "status": "overdue"}


@app.post("/api/finance/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        invoice = conn.execute("SELECT * FROM invoices WHERE id=? AND status IN ('sent','overdue')", (invoice_id,)).fetchone()
        if not invoice:
            raise HTTPException(status.HTTP_409_CONFLICT, "发票不存在或不可收款")
        conn.execute("UPDATE invoices SET status='paid', paid_at=? WHERE id=?", (_now(), invoice_id))
        conn.execute("INSERT INTO transactions (id, account_id, amount, direction, description, status, created_at) VALUES (?,?,?,?,?,?,?)", (str(uuid.uuid4()), "invoice-receivable", invoice["amount"], "debit", f"收款 {invoice['number']}", "posted", _now()))
        base.record_audit("invoice.paid", "internal", f"invoice={invoice_id} amount={invoice['amount']}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": invoice_id, "status": "paid"}


@app.post("/api/finance/budgets", status_code=status.HTTP_201_CREATED)
def create_budget(payload: BudgetIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    budget_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        try:
            conn.execute("INSERT INTO budgets VALUES (?,?,?,?,0)", (budget_id, payload.department, payload.period, payload.amount))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "该部门该期间预算已存在") from exc
    return {"id": budget_id, "department": payload.department, "period": payload.period, "amount": payload.amount}


@app.get("/api/finance/budgets")
def list_budgets() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM budgets ORDER BY period DESC").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/finance/reports")
def reports() -> dict[str, Any]:
    with base.db_ctx() as conn:
        assets = conn.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE type='asset'").fetchone()[0]
        liabilities = conn.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE type='liability'").fetchone()[0]
        equity = conn.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE type='equity'").fetchone()[0]
        revenue = conn.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE type='revenue'").fetchone()[0]
        expense = conn.execute("SELECT COALESCE(SUM(balance),0) FROM accounts WHERE type='expense'").fetchone()[0]
        receivable = conn.execute("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE status IN ('sent','overdue')").fetchone()[0]
        budgets = conn.execute("SELECT COALESCE(SUM(spent),0) AS spent, COALESCE(SUM(amount),0) AS amount FROM budgets").fetchone()
    return {
        "balance_sheet": {"assets": assets, "liabilities": liabilities, "equity": equity},
        "income_statement": {"revenue": revenue, "expenses": expense, "net": round(revenue - expense, 2)},
        "receivables_outstanding": receivable,
        "budget_utilization": round(budgets["spent"] / budgets["amount"] * 100, 2) if budgets["amount"] else 0.0,
    }


@app.get("/api/finance/stats")
def stats() -> dict[str, Any]:
    with base.db_ctx() as conn:
        def _count(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]
        return {
            "accounts": _count("SELECT COUNT(*) FROM accounts"),
            "transactions": _count("SELECT COUNT(*) FROM transactions"),
            "invoices_draft": _count("SELECT COUNT(*) FROM invoices WHERE status='draft'"),
            "invoices_sent": _count("SELECT COUNT(*) FROM invoices WHERE status='sent'"),
            "invoices_overdue": _count("SELECT COUNT(*) FROM invoices WHERE status='overdue'"),
            "invoices_paid": _count("SELECT COUNT(*) FROM invoices WHERE status='paid'"),
        }
