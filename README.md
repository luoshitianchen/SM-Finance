# SM Finance

财务管理：预算、费用、发票、核算和财务审计。

```powershell
git clone https://github.com/luoshitianchen/SM-Finance.git
cd SM-Finance
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8520
```

接口：`/health`、`/readyz`、`/api/overview`、`/api/items`、`/api/ops/metrics`、`/api/crypto/status`。
