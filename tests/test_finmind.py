"""FinMind vendor: Taiwan symbol detection, point-in-time monthly revenue,
institutional flows, error mapping, and which analysts are offered the tools.

All API access is mocked, so these run without a network connection.
"""

import pytest

from tradingagents.agents.analysts import fundamentals_analyst, market_analyst
from tradingagents.dataflows import router
from tradingagents.dataflows.errors import NoMarketDataError, VendorUnavailableError
from tradingagents.dataflows.vendors import finmind


def _revenue_rows():
    rows = []
    for year in (2024, 2025):
        for month in range(1, 13):
            rows.append({"revenue_year": year, "revenue_month": month,
                         "revenue": (100 if year == 2024 else 150) * 1e6 + month * 1e6})
    return rows


@pytest.fixture
def fetch(monkeypatch):
    """Serve canned datasets; returns the list of datasets requested."""
    requested = []
    data = {
        "TaiwanStockMonthRevenue": _revenue_rows(),
        "TaiwanStockInstitutionalInvestorsBuySell": [
            {"date": "2025-03-03", "name": "Foreign_Investor", "buy": 5000, "sell": 1000},
            {"date": "2025-03-03", "name": "Investment_Trust", "buy": 0, "sell": 2000},
            {"date": "2025-03-04", "name": "Foreign_Investor", "buy": 3000, "sell": 0},
            {"date": "2025-03-04", "name": "Dealer_Hedging", "buy": 1000, "sell": 0},
        ],
        "TaiwanStockMarginPurchaseShortSale": [
            {"date": "2025-03-04", "MarginPurchaseTodayBalance": 12345, "ShortSaleTodayBalance": 67},
        ],
    }

    def _fetch(dataset, stock_id, start, end):
        requested.append((dataset, stock_id))
        return data[dataset]

    monkeypatch.setattr(finmind, "_fetch", _fetch)
    return requested


@pytest.mark.unit
@pytest.mark.parametrize("symbol,stock_id", [
    ("2330.TW", "2330"), ("00878.tw", "00878"), ("6488.TWO", "6488"),
    ("NVDA", None), ("0700.HK", None), ("2330", None),
])
def test_taiwan_stock_id(symbol, stock_id):
    assert finmind.taiwan_stock_id(symbol) == stock_id


@pytest.mark.unit
def test_revenue_is_public_on_the_tenth_or_the_monday_after():
    assert str(finmind._revenue_public_on(2025, 12)) == "2026-01-12"   # the 10th is a Saturday
    assert str(finmind._revenue_public_on(2025, 8)) == "2025-09-10"    # a Wednesday


@pytest.mark.unit
def test_revenue_withholds_a_month_not_yet_public(fetch):
    before = finmind.get_monthly_revenue("2330.TW", "2025-09-09")
    after = finmind.get_monthly_revenue("2330.TW", "2025-09-10")
    assert "2025-08" not in before and "2025-07" in before
    assert "2025-08" in after


@pytest.mark.unit
def test_revenue_reports_mom_yoy_and_year_to_date(fetch):
    out = finmind.get_monthly_revenue("2330.TW", "2025-12-31", months=2)
    # Nov 2025 = 161M; Oct 2025 = 160M; Nov 2024 = 111M.
    assert "| 2025-11 | 161 | +0.6% | +45.0% |" in out
    assert "2025-09" not in out
    assert "Year-to-date 2025 through month 11" in out
    assert fetch == [("TaiwanStockMonthRevenue", "2330")]


@pytest.mark.unit
def test_institutional_flows_net_and_group_by_investor(fetch):
    out = finmind.get_institutional_trading("6488.TWO", "2025-03-04", 10)
    assert "| 2025-03-04 | +3 | +0 | +1 | +4 | 12,345 | 67 |" in out
    assert "| 2025-03-03 | +4 | -2 | +0 | +2 | n/a | n/a |" in out
    assert "net buyers for 2 consecutive" in out


@pytest.mark.unit
def test_institutional_flows_drop_rows_after_the_run_date(fetch):
    out = finmind.get_institutional_trading("6488.TWO", "2025-03-03", 10)
    assert "2025-03-04" not in out


@pytest.mark.unit
def test_a_non_taiwan_symbol_is_not_fetched(fetch):
    assert finmind.get_monthly_revenue("NVDA", "2025-03-04").startswith("NOT_APPLICABLE")
    assert finmind.get_institutional_trading("NVDA", "2025-03-04").startswith("NOT_APPLICABLE")
    assert fetch == []


@pytest.mark.unit
def test_no_rows_is_no_market_data(monkeypatch):
    monkeypatch.setattr(finmind, "_fetch", lambda *a: [])
    with pytest.raises(NoMarketDataError):
        finmind.get_monthly_revenue("2330.TW", "2025-03-04")


@pytest.mark.unit
def test_a_rate_limit_is_vendor_unavailable(monkeypatch):
    class _Response:
        status_code = 402

        def json(self):
            return {"status": 402, "msg": "Requests reach the upper limit"}

    monkeypatch.delenv("FINMIND_API_TOKEN", raising=False)
    monkeypatch.setattr(finmind.requests, "get", lambda *a, **k: _Response())
    with pytest.raises(VendorUnavailableError, match="FINMIND_API_TOKEN"):
        finmind._fetch("TaiwanStockMonthRevenue", "2330", "2025-01-01", "2025-03-01")


@pytest.mark.unit
def test_the_token_goes_in_a_header(monkeypatch):
    seen = {}

    class _Response:
        status_code = 200

        def json(self):
            return {"status": 200, "data": []}

    def _get(url, params, headers, timeout):
        seen.update(params=params, headers=headers)
        return _Response()

    monkeypatch.setenv("FINMIND_API_TOKEN", "secret")
    monkeypatch.setattr(finmind.requests, "get", _get)
    finmind._fetch("TaiwanStockMonthRevenue", "2330", "2025-01-01", "2025-03-01")
    assert seen["headers"] == {"Authorization": "Bearer secret"}
    assert "secret" not in str(seen["params"])


@pytest.mark.unit
def test_a_failed_vendor_degrades_instead_of_ending_the_run(monkeypatch):
    def _fail(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setitem(router.VENDOR_METHODS["get_tw_monthly_revenue"], "finmind", _fail)
    out = router.route_to_vendor("get_tw_monthly_revenue", "2330.TW", "2025-03-04", None)
    assert out.startswith("DATA_UNAVAILABLE")


@pytest.mark.unit
@pytest.mark.parametrize("module", [market_analyst, fundamentals_analyst])
def test_taiwan_tools_are_in_the_tool_node_but_offered_only_to_taiwan_listings(module):
    for t in module.TAIWAN_TOOLS:
        assert t in module.TOOLS
        assert t not in module.BASE_TOOLS
