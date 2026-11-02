"""Deep-dive data for a few stocks, and how earlier picks have done since.

    python -m daily_scan.deep 3227 6138                 # research data for each
    python -m daily_scan.deep --track 3227:180.5:2026-11-02 6138:239:2026-11-02

Prices come from FinMind (Yahoo throttles shared IPs); monthly revenue and
institutional flows reuse TradingAgents' FinMind tools.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from functools import cache

from daily_scan import sources
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import NoMarketDataError, VendorUnavailableError
from tradingagents.dataflows.vendors import finmind
from tradingagents.default_config import DEFAULT_CONFIG

TAIPEI = timezone(timedelta(hours=8))


@cache
def _twse_listed() -> frozenset[str]:
    return frozenset(sources.twse_shares())


def yahoo_symbol(code: str) -> str:
    """The Yahoo-style symbol for a Taiwan code: listed (.TW) or OTC (.TWO)."""
    if "." in code:
        return code.upper()
    listed = _twse_listed()
    return code + (".TW" if code in listed or not listed else ".TWO")


def _prices(code: str, days: int = 150) -> list[dict]:
    start = (datetime.now(TAIPEI) - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.now(TAIPEI).strftime("%Y-%m-%d")
    rows = finmind._fetch("TaiwanStockPrice", code.split(".")[0], start, end)
    if not rows:
        raise NoMarketDataError(code, detail="no FinMind prices")
    return rows


def _rsi(closes: list[float], n: int = 14) -> float:
    gains = [max(b - a, 0) for a, b in zip(closes[-n - 1:-1], closes[-n:], strict=False)]
    losses = [max(a - b, 0) for a, b in zip(closes[-n - 1:-1], closes[-n:], strict=False)]
    avg_loss = sum(losses) / n
    return 100.0 if avg_loss == 0 else 100 - 100 / (1 + (sum(gains) / n) / avg_loss)


def price_summary(code: str) -> str:
    rows = _prices(code)
    closes = [float(r["close"]) for r in rows]
    vols = [float(r["Trading_Volume"]) for r in rows]
    last = rows[-1]

    def ma(n):
        return sum(closes[-n:]) / min(n, len(closes))
    lines = [
        f"最新 {last['date']}：收 {closes[-1]:g}（高 {last['max']:g} / 低 {last['min']:g}），"
        f"成交 {vols[-1] / 1000:,.0f} 張，20 日均量 {sum(vols[-20:]) / min(20, len(vols)) / 1000:,.0f} 張",
        f"均線：5 日 {ma(5):.2f}、20 日 {ma(20):.2f}、60 日 {ma(60):.2f}；RSI(14) {_rsi(closes):.0f}",
        f"20 日區間 {min(closes[-20:]):g} ~ {max(closes[-20:]):g}；60 日區間 {min(closes[-60:]):g} ~ {max(closes[-60:]):g}",
        f"報酬：5 日 {(closes[-1] / closes[-6] - 1) * 100:+.1f}%、20 日 {(closes[-1] / closes[-21] - 1) * 100:+.1f}%、"
        f"60 日 {(closes[-1] / closes[-61] - 1) * 100:+.1f}%" if len(closes) > 61 else "",
        "近 10 日收盤：" + "、".join(f"{r['date'][5:]} {float(r['close']):g}" for r in rows[-10:]),
    ]
    return "\n".join(line for line in lines if line)


def _section(title: str, fetch) -> str:
    try:
        return f"### {title}\n{fetch()}\n"
    except (NoMarketDataError, VendorUnavailableError, ValueError, KeyError) as exc:
        return f"### {title}\n（無法取得：{exc}）\n"


def research(code: str, today: str) -> str:
    symbol = yahoo_symbol(code)
    parts = [f"## {symbol}"]
    parts.append(_section("價格與技術指標", lambda: price_summary(symbol)))
    parts.append(_section("月營收", lambda: finmind.get_monthly_revenue(symbol, today, 13)))
    parts.append(_section("法人與融資券（近 30 天）", lambda: finmind.get_institutional_trading(symbol, today, 30)))
    return "\n".join(parts)


def track(spec: str) -> str:
    """'CODE:PRICE:DATE' -> how the pick has moved since it was named."""
    code, price, picked = spec.split(":")
    symbol = yahoo_symbol(code)
    try:
        last = float(_prices(code, days=10)[-1]["close"])
    except (NoMarketDataError, VendorUnavailableError):
        return f"| {symbol} | {picked} | {price} | n/a | n/a |"
    return f"| {symbol} | {picked} | {float(price):g} | {last:g} | {(last / float(price) - 1) * 100:+.1f}% |"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("codes", nargs="*", help="stock codes to research, e.g. 3227 6138")
    parser.add_argument("--track", nargs="*", default=[], help="CODE:PRICE:DATE of earlier picks")
    args = parser.parse_args()
    set_config(DEFAULT_CONFIG)
    today = datetime.now(TAIPEI).strftime("%Y-%m-%d")
    if args.track:
        print("| 股票 | 選出日 | 當時價 | 最新價 | 報酬 |\n|---|---|---:|---:|---:|")
        for spec in args.track:
            print(track(spec))
        print()
    for code in args.codes:
        print(research(code, today))


if __name__ == "__main__":
    main()
