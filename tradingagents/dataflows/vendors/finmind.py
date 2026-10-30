"""FinMind vendor: Taiwan-listed data Yahoo does not carry.

Monthly revenue, which TWSE/TPEx companies must publish by the 10th of the
following month, and the daily institutional (foreign, investment trust,
dealer) and margin trading figures the exchanges publish after each close.

FinMind serves these keyless at a lower hourly limit; a free token from
https://finmindtrade.com raises it. Set it as ``FINMIND_API_TOKEN``.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta

import requests

from tradingagents.dataflows.errors import NoMarketDataError, VendorUnavailableError

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"
REQUEST_TIMEOUT = 20

# A Taiwan listing on Yahoo: a TWSE (.TW) or TPEx (.TWO) code such as 2330.TW,
# 00878.TW or 6488.TWO.
_TAIWAN_SYMBOL = re.compile(r"^([0-9A-Z]{4,6})\.(TW|TWO)$")

DEFAULT_REVENUE_MONTHS = 13
DEFAULT_FLOW_LOOKBACK_DAYS = 30


def taiwan_stock_id(symbol: str) -> str | None:
    """The TWSE/TPEx code of a Taiwan-listed Yahoo symbol, else None."""
    match = _TAIWAN_SYMBOL.match(str(symbol).strip().upper())
    return match.group(1) if match else None


def is_taiwan_listed(symbol: str) -> bool:
    return taiwan_stock_id(symbol) is not None


def _not_taiwan(symbol: str, what: str) -> str:
    return (
        f"NOT_APPLICABLE: {what} covers Taiwan-listed stocks only (.TW or .TWO "
        f"symbols); {symbol!r} is not one."
    )


def _fetch(dataset: str, stock_id: str, start_date: str, end_date: str) -> list[dict]:
    """Rows of one FinMind dataset for a stock over ``[start_date, end_date]``."""
    token = os.getenv("FINMIND_API_TOKEN", "").strip()
    # The token goes in a header, so it never appears in a URL an error quotes.
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {"dataset": dataset, "data_id": stock_id,
              "start_date": start_date, "end_date": end_date}
    try:
        response = requests.get(FINMIND_API_URL, params=params, headers=headers,
                                timeout=REQUEST_TIMEOUT)
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise VendorUnavailableError(f"FinMind request failed: {exc}") from None
    # FinMind reports its hourly limit (402) and other refusals in the body.
    status = body.get("status", response.status_code)
    if response.status_code != 200 or status != 200:
        hint = "" if token else " (set FINMIND_API_TOKEN for a higher limit)"
        raise VendorUnavailableError(f"FinMind refused {dataset}: {body.get('msg', status)}{hint}")
    return body.get("data") or []


def _revenue_public_on(year: int, month: int) -> date:
    """When a month's revenue is public: the 10th of the next month, or the
    Monday after when that falls on a weekend."""
    public = date(year + month // 12, month % 12 + 1, 10)
    while public.weekday() >= 5:
        public += timedelta(days=1)
    return public


def _pct(new: float, old: float | None) -> str:
    if not old:
        return "n/a"
    return f"{(new - old) / abs(old) * 100:+.1f}%"


def get_monthly_revenue(symbol: str, curr_date: str, months: int | None = None) -> str:
    """Monthly revenue public by ``curr_date``, with month-over-month and year-over-year change."""
    stock_id = taiwan_stock_id(symbol)
    if stock_id is None:
        return _not_taiwan(symbol, "Monthly revenue")
    months = max(1, min(int(months or DEFAULT_REVENUE_MONTHS), 36))
    as_of_dt = datetime.strptime(curr_date, "%Y-%m-%d").date()
    # Back far enough for each shown month's year-ago figure and for the prior
    # year's January, which the year-to-date comparison starts from.
    start = min(as_of_dt.replace(day=1) - timedelta(days=31 * (months + 13)),
                date(as_of_dt.year - 2, 1, 1)).strftime("%Y-%m-%d")
    rows = _fetch("TaiwanStockMonthRevenue", stock_id, start, curr_date)

    revenue = {}
    for row in rows:
        year, month = int(row["revenue_year"]), int(row["revenue_month"])
        if _revenue_public_on(year, month) <= as_of_dt:
            revenue[(year, month)] = float(row["revenue"])
    if not revenue:
        raise NoMarketDataError(symbol, stock_id, f"no monthly revenue public by {curr_date}")

    def previous(year, month):
        return (year, month - 1) if month > 1 else (year - 1, 12)

    shown = sorted(revenue)[-months:]
    lines = [
        f"# Monthly Revenue for {symbol} (TWSE/TPEx {stock_id})",
        f"# Point-in-time as of: {curr_date}; a month counts once public "
        f"(by the 10th of the next month)",
        "",
        "| Month | Revenue (NT$ million) | MoM | YoY |",
        "|---|---:|---:|---:|",
    ]
    for year, month in reversed(shown):
        value = revenue[(year, month)]
        lines.append(
            f"| {year}-{month:02d} | {value / 1e6:,.0f} | "
            f"{_pct(value, revenue.get(previous(year, month)))} | "
            f"{_pct(value, revenue.get((year - 1, month)))} |"
        )

    latest_year, latest_month = shown[-1]
    ytd = sum(v for (y, m), v in revenue.items() if y == latest_year and m <= latest_month)
    ytd_prior = [revenue.get((latest_year - 1, m)) for m in range(1, latest_month + 1)]
    if all(ytd_prior):
        lines += ["", f"Year-to-date {latest_year} through month {latest_month}: "
                      f"NT$ {ytd / 1e6:,.0f} million, {_pct(ytd, sum(ytd_prior))} year over year."]
    return "\n".join(lines)


# FinMind's investor names, grouped the way Taiwan market reports quote them.
_INVESTOR_GROUPS = {
    "Foreign_Investor": "Foreign",
    "Foreign_Dealer_Self": "Foreign",
    "Investment_Trust": "Investment trust",
    "Dealer_self": "Dealer",
    "Dealer_Hedging": "Dealer",
}
_GROUPS = ("Foreign", "Investment trust", "Dealer")


def _lots(shares: float) -> str:
    """Shares as board lots of 1,000, the unit Taiwan quotes flows in."""
    return f"{shares / 1000:+,.0f}"


def _balance(value) -> str:
    return "n/a" if value is None else f"{float(value):,.0f}"


def get_institutional_trading(symbol: str, curr_date: str, look_back_days: int | None = None) -> str:
    """Daily net buying by institutional investors, and margin and short balances, up to ``curr_date``."""
    stock_id = taiwan_stock_id(symbol)
    if stock_id is None:
        return _not_taiwan(symbol, "Institutional trading")
    look_back_days = max(1, min(int(look_back_days or DEFAULT_FLOW_LOOKBACK_DAYS), 365))
    start = (datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)).strftime("%Y-%m-%d")

    net: dict[str, dict[str, float]] = defaultdict(lambda: dict.fromkeys(_GROUPS, 0.0))
    for row in _fetch("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start, curr_date):
        group = _INVESTOR_GROUPS.get(row.get("name"))
        if group and row["date"] <= curr_date:
            net[row["date"]][group] += float(row["buy"]) - float(row["sell"])
    if not net:
        raise NoMarketDataError(symbol, stock_id, f"no institutional trading {start}..{curr_date}")

    # Margin figures add context; their absence should not cost the flows.
    try:
        margin_rows = _fetch("TaiwanStockMarginPurchaseShortSale", stock_id, start, curr_date)
    except VendorUnavailableError:
        margin_rows = []
    margin = {r["date"]: r for r in margin_rows if r["date"] <= curr_date}

    days = sorted(net)
    lines = [
        f"# Institutional and Margin Trading for {symbol} (TWSE/TPEx {stock_id})",
        f"# {days[0]} .. {days[-1]}; net buy (+) / sell (-) in lots of 1,000 shares; "
        f"margin and short balances in lots",
        "",
        "| Date | Foreign | Investment trust | Dealer | Total | Margin balance | Short balance |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for day in reversed(days):
        flows = net[day]
        m = margin.get(day, {})
        lines.append(
            f"| {day} | " + " | ".join(_lots(flows[g]) for g in _GROUPS)
            + f" | {_lots(sum(flows.values()))}"
            + f" | {_balance(m.get('MarginPurchaseTodayBalance'))} | {_balance(m.get('ShortSaleTodayBalance'))} |"
        )

    lines += ["", "Window totals (lots): " + "; ".join(
        f"{g} {_lots(sum(net[d][g] for d in days))}" for g in _GROUPS)]
    streak = 0
    sign = 1 if net[days[-1]]["Foreign"] > 0 else -1
    for day in reversed(days):
        if net[day]["Foreign"] * sign <= 0:
            break
        streak += 1
    if streak:
        lines.append(f"Foreign investors have been net {'buyers' if sign > 0 else 'sellers'} "
                     f"for {streak} consecutive trading day(s).")
    return "\n".join(lines)
