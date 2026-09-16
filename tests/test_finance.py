"""财务业务深化测试：科目/凭证/报表全生命周期与业务规则。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

INTERNAL_TOKEN = "test-internal-key-12345"
AUTH_HEADERS = {"X-Internal-Token": INTERNAL_TOKEN}

_counter = {"n": 0}


def uniq(prefix: str) -> str:
    _counter["n"] += 1
    return f"{prefix}-{_counter['n']}"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════
# 会计科目
# ═══════════════════════════════════════════════════════════

class TestAccountManagement:
    def _create_account(self, client, code: str, category: str = "asset") -> dict:
        return client.post("/api/finance/accounts", json={
            "code": code, "name": f"科目{code}", "category": category,
        }, headers=AUTH_HEADERS).json()

    def test_create_account_success(self, client):
        resp = client.post("/api/finance/accounts", json={
            "code": "1001", "name": "库存现金", "category": "asset",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        assert resp.json()["code"] == "1001"

    def test_create_account_require_token(self, client):
        resp = client.post("/api/finance/accounts", json={
            "code": "9999", "name": "无令牌科目", "category": "asset",
        })
        assert resp.status_code in (401, 403)

    def test_create_account_duplicate_code(self, client):
        resp = client.post("/api/finance/accounts", json={
            "code": "1001", "name": "重复", "category": "asset",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 409

    def test_list_accounts(self, client):
        resp = client.get("/api/finance/accounts", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_list_accounts_filter_category(self, client):
        resp = client.get("/api/finance/accounts?category=liability", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert all(i["category"] == "liability" for i in resp.json()["items"])

    def test_get_account(self, client):
        acc = self._create_account(client, "ACC-GET")
        resp = client.get(f"/api/finance/accounts/{acc['id']}", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["id"] == acc["id"]

    def test_get_account_not_found(self, client):
        resp = client.get("/api/finance/accounts/nonexistent", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_update_account(self, client):
        acc = self._create_account(client, "ACC-UPD")
        resp = client.patch(f"/api/finance/accounts/{acc['id']}", json={
            "name": "更新后科目",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["name"] == "更新后科目"

    def test_update_account_status_closed(self, client):
        acc = self._create_account(client, "ACC-CLOSED")
        resp = client.patch(f"/api/finance/accounts/{acc['id']}/status", json={
            "status": "closed",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"


# ═══════════════════════════════════════════════════════════
# 记账凭证
# ═══════════════════════════════════════════════════════════

class TestVoucherManagement:
    def _account_id(self, client, category: str = "asset") -> str:
        resp = client.post("/api/finance/accounts", json={
            "code": uniq("ACC"), "name": f"凭证科目{category}", "category": category,
        }, headers=AUTH_HEADERS)
        return resp.json()["id"]

    def _balanced_voucher(self, client, voucher_no: str) -> dict:
        debit = self._account_id(client)
        credit = self._account_id(client, category="expense")
        return client.post("/api/finance/vouchers", json={
            "voucher_no": voucher_no, "voucher_date": "2026-09-01",
            "summary": "日常报销",
            "entries": [
                {"account_id": debit, "direction": "debit", "amount": 1000, "summary": "差旅费"},
                {"account_id": credit, "direction": "credit", "amount": 1000, "summary": "银行"},
            ],
        }, headers=AUTH_HEADERS)

    def test_create_voucher_balanced(self, client):
        resp = self._balanced_voucher(client, uniq("VCH"))
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["total_debit"] == 1000
        assert data["total_credit"] == 1000
        assert len(data["entries"]) == 2

    def test_create_voucher_require_token(self, client):
        resp = client.post("/api/finance/vouchers", json={
            "voucher_no": "VCH-NOAUTH", "voucher_date": "2026-09-01", "entries": [],
        })
        assert resp.status_code in (401, 403)

    def test_create_voucher_duplicate_no(self, client):
        no = uniq("VCH-DUP")
        first = self._balanced_voucher(client, no)
        assert first.status_code == 201
        second = self._balanced_voucher(client, no)
        assert second.status_code == 409

    def test_create_voucher_unbalanced(self, client):
        debit = self._account_id(client)
        credit = self._account_id(client, category="expense")
        resp = client.post("/api/finance/vouchers", json={
            "voucher_no": uniq("VCH-UNB"), "voucher_date": "2026-09-01",
            "entries": [
                {"account_id": debit, "direction": "debit", "amount": 1000},
                {"account_id": credit, "direction": "credit", "amount": 800},
            ],
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 400

    def test_create_voucher_account_not_exist(self, client):
        resp = client.post("/api/finance/vouchers", json={
            "voucher_no": uniq("VCH-GHOST"), "voucher_date": "2026-09-01",
            "entries": [
                {"account_id": "ghost", "direction": "debit", "amount": 100},
                {"account_id": "ghost2", "direction": "credit", "amount": 100},
            ],
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 400

    def test_list_vouchers(self, client):
        resp = client.get("/api/finance/vouchers", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_get_voucher_with_entries(self, client):
        create = self._balanced_voucher(client, uniq("VCH-GET")).json()
        resp = client.get(f"/api/finance/vouchers/{create['id']}", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()["entries"]) == 2

    def test_update_draft_voucher(self, client):
        create = self._balanced_voucher(client, uniq("VCH-UPD")).json()
        resp = client.patch(f"/api/finance/vouchers/{create['id']}", json={
            "summary": "更新摘要",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["summary"] == "更新摘要"

    def test_post_voucher(self, client):
        create = self._balanced_voucher(client, uniq("VCH-POST")).json()
        resp = client.post(f"/api/finance/vouchers/{create['id']}/post", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["status"] == "posted"

    def test_double_post_rejected(self, client):
        create = self._balanced_voucher(client, uniq("VCH-DBL")).json()
        client.post(f"/api/finance/vouchers/{create['id']}/post", headers=AUTH_HEADERS)
        resp = client.post(f"/api/finance/vouchers/{create['id']}/post", headers=AUTH_HEADERS)
        assert resp.status_code == 409

    def test_edit_posted_voucher_rejected(self, client):
        create = self._balanced_voucher(client, uniq("VCH-EDIT")).json()
        client.post(f"/api/finance/vouchers/{create['id']}/post", headers=AUTH_HEADERS)
        resp = client.patch(f"/api/finance/vouchers/{create['id']}", json={
            "summary": "试图改已过账",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 409

    def test_delete_draft_voucher(self, client):
        create = self._balanced_voucher(client, uniq("VCH-DEL")).json()
        resp = client.delete(f"/api/finance/vouchers/{create['id']}", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_posted_voucher_rejected(self, client):
        create = self._balanced_voucher(client, uniq("VCH-DLP")).json()
        client.post(f"/api/finance/vouchers/{create['id']}/post", headers=AUTH_HEADERS)
        resp = client.delete(f"/api/finance/vouchers/{create['id']}", headers=AUTH_HEADERS)
        assert resp.status_code == 409


# ═══════════════════════════════════════════════════════════
# 财务报表
# ═══════════════════════════════════════════════════════════

class TestReportManagement:
    def test_create_report_success(self, client):
        resp = client.post("/api/finance/reports", json={
            "period": "2026-09", "type": "balance_sheet",
            "title": "2026年9月资产负债表", "data": '{"total_assets": 1000000}',
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    def test_create_report_duplicate_period_type(self, client):
        resp = client.post("/api/finance/reports", json={
            "period": "2026-09", "type": "balance_sheet", "title": "重复",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 409

    def test_list_reports(self, client):
        resp = client.get("/api/finance/reports?type=income_statement", headers=AUTH_HEADERS)
        assert resp.status_code == 200

    def test_get_report_not_found(self, client):
        resp = client.get("/api/finance/reports/nonexistent", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_update_report(self, client):
        create = client.post("/api/finance/reports", json={
            "period": uniq("2026-1"), "type": "cash_flow", "title": "现金流量表",
        }, headers=AUTH_HEADERS).json()
        resp = client.patch(f"/api/finance/reports/{create['id']}", json={
            "title": "更新后的报表名",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["title"] == "更新后的报表名"

    def test_finalize_report(self, client):
        create = client.post("/api/finance/reports", json={
            "period": uniq("2026-2"), "type": "income_statement", "title": "利润表",
        }, headers=AUTH_HEADERS).json()
        resp = client.post(f"/api/finance/reports/{create['id']}/finalize", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["status"] == "finalized"

    def test_edit_finalized_report_rejected(self, client):
        create = client.post("/api/finance/reports", json={
            "period": uniq("2026-3"), "type": "balance_sheet", "title": "待归档",
        }, headers=AUTH_HEADERS).json()
        client.post(f"/api/finance/reports/{create['id']}/finalize", headers=AUTH_HEADERS)
        resp = client.patch(f"/api/finance/reports/{create['id']}", json={
            "title": "试图改已归档",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 409
