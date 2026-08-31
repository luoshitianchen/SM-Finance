"""SM Finance 领域测试：科目、凭证、发票生命周期、预算与报表。"""

import pytest
from fastapi.testclient import TestClient

from app import base
from app.main import VERSION, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(base, "internal_api_key", lambda: "TEST")
    base.reset_state()
    from app.main import _init as init_db
    init_db()
    with TestClient(app) as c:
        c.headers["X-Internal-Token"] = "TEST"
        yield c


def _account(client, code="1001", name="库存现金", type_="asset"):
    return client.post("/api/finance/accounts", json={"code": code, "name": name, "type": type_}).json()["id"]


def _invoice(client, number="INV-001", amount=10000):
    return client.post("/api/finance/invoices", json={"number": number, "customer": "云启科技", "amount": amount, "due_date": "2026-09-30"}).json()["id"]


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION


def test_account_and_transaction(client):
    account_id = _account(client)
    assert client.post("/api/finance/accounts", json={"code": "1001", "name": "xx", "type": "asset"}).status_code == 409
    assert client.post("/api/finance/transactions", json={"account_id": account_id, "amount": 5000, "direction": "debit", "description": "收到货款"}).status_code == 201
    assert client.post("/api/finance/transactions", json={"account_id": "no-such-acct", "amount": 10, "direction": "debit"}).status_code == 404
    assert client.get("/api/finance/accounts").json()["items"][0]["balance"] == 5000


def test_invoice_lifecycle(client):
    invoice_id = _invoice(client)
    assert client.post(f"/api/finance/invoices/{invoice_id}/issue").json()["status"] == "sent"
    assert client.post(f"/api/finance/invoices/{invoice_id}/issue").status_code == 409
    assert client.post(f"/api/finance/invoices/{invoice_id}/pay").json()["status"] == "paid"
    assert client.post(f"/api/finance/invoices/{invoice_id}/pay").status_code == 409


def test_overdue(client):
    invoice_id = _invoice(client, number="INV-002")
    client.post(f"/api/finance/invoices/{invoice_id}/issue")
    # 到期日在过去
    client.post("/api/finance/invoices", json={"number": "INV-OLD", "customer": "cc", "amount": 1, "due_date": "2020-01-01"})
    old_id = client.get("/api/finance/invoices", params={"status_": "draft"}).json()["items"][-1]["id"]
    client.post(f"/api/finance/invoices/{old_id}/issue")
    assert client.post(f"/api/finance/invoices/{old_id}/mark-overdue").json()["status"] == "overdue"


def test_budget(client):
    assert client.post("/api/finance/budgets", json={"department": "市场部", "period": "2026-08", "amount": 100000}).status_code == 201
    assert client.post("/api/finance/budgets", json={"department": "市场部", "period": "2026-08", "amount": 1}).status_code == 409
    assert client.get("/api/finance/budgets").json()["total"] == 1


def test_reports(client):
    account_id = _account(client)
    client.post("/api/finance/transactions", json={"account_id": account_id, "amount": 10000, "direction": "debit", "description": "收入"})
    report = client.get("/api/finance/reports").json()
    assert report["balance_sheet"]["assets"] == 10000


def test_stats(client):
    _invoice(client)
    stats = client.get("/api/finance/stats").json()
    assert stats["invoices_draft"] == 1


def test_manifest_and_crypto(client):
    assert client.get("/api/integration/manifest").json()["version"] == VERSION
    enc = client.post("/api/crypto/encrypt", json={"value": "x"}).json()["ciphertext"]
    assert client.post("/api/crypto/decrypt", json={"value": enc}).json()["plaintext"] == "x"


def test_write_requires_auth(client):
    del client.headers["X-Internal-Token"]
    assert client.post("/api/finance/accounts", json={"code": "c", "name": "n", "type": "asset"}).status_code == 401
