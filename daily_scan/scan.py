"""Daily market scan: what is heating up or cooling, and quiet stocks worth an early look.

Writes a Markdown data pack (and the same figures as JSON) for the report writer
to read. All figures come from free sources; nothing here calls an LLM.

    python -m daily_scan.scan --out out/            # latest trading day
    python -m daily_scan.scan --date 2026-10-30 --out out/
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

from daily_scan import sources

TAIPEI = timezone(timedelta(hours=8))
WINDOW = 10              # trading days of history
MIN_VALUE = 20e6         # NT$ average daily turnover a candidate must clear
HOT_COUNT = 20
HIDDEN_COUNT = 20
MAX_CAP = 60e9           # NT$ market cap above which a name is already well covered
LARGE_CAP_RANK = 100     # fallback when a market cap is unknown: the most-traded names


def _lots(shares: float) -> str:
    return f"{shares / 1000:+,.0f}"


def _streak(values: list[float]) -> int:
    """Consecutive most-recent days with net buying (> 0)."""
    n = 0
    for v in reversed(values):
        if v <= 0:
            break
        n += 1
    return n


def _mentions(news: list[dict], names: dict[str, str]) -> Counter:
    """How often each stock appears in the headlines, by tag, code or name."""
    counts: Counter = Counter()
    by_name = {n: c for c, n in names.items() if len(n) >= 2}
    name_re = re.compile("|".join(sorted(map(re.escape, by_name), key=len, reverse=True))) if by_name else None
    for item in news:
        found = {c for c in item["codes"] if c in names}
        found |= set(re.findall(r"(?<!\d)([1-9]\d{3})(?!\d)", item["title"])) & names.keys()
        if name_re:
            found |= {by_name[m] for m in name_re.findall(item["title"])}
        counts.update(found)
    return counts


def build(end: date) -> dict:
    days = sources.trading_days(end, WINDOW)
    if len(days) < 3:
        raise SystemExit(f"only {len(days)} trading days of data up to {end}; exchanges unreachable?")
    today, latest = days[-1]
    industry = sources.industries()
    twse_shares = sources.twse_shares()
    attention = sources.attention_stocks()
    news = sources.cnyes_news() + sources.yahoo_news() + sources.ptt_titles()
    names = {c: q["name"] for c, q in latest.items() if not c.startswith("_")}
    mentions = _mentions(news, names)

    # Per-stock history over the window.
    stocks = {}
    for code, q in latest.items():
        if code.startswith("_") or q["close"] <= 0:
            continue
        hist = [d.get(code) for _, d in days]
        hist = [h for h in hist if h]
        if len(hist) < 3:
            continue
        prev = hist[:-1]
        avg_vol = sum(h["volume"] for h in prev) / len(prev) or 1
        avg_val = sum(h["value"] for h in prev) / len(prev)
        prev_close = q["close"] - q["change"]
        first_close = hist[0]["close"] - hist[0]["change"]
        shares = q.get("shares") or twse_shares.get(code) or 0
        stocks[code] = {
            "code": code, "name": q["name"], "market": q["market"],
            "industry": industry.get(code, "其他"),
            "close": q["close"], "cap": q["close"] * shares or None,
            "chg_pct": q["change"] / prev_close * 100 if prev_close else 0,
            "ret_window_pct": (q["close"] / first_close - 1) * 100 if first_close else 0,
            "vol_ratio": q["volume"] / avg_vol,
            "value": q["value"], "avg_value": avg_val,
            "high_window": max(h["close"] for h in hist),
            "foreign": [h.get("foreign", 0) for h in hist],
            "trust": [h.get("trust", 0) for h in hist],
            "dealer": [h.get("dealer", 0) for h in hist],
            "avg_volume": avg_vol,
            "mentions": mentions.get(code, 0),
            "attention": attention.get(code, "").split("<br>")[0][:28],
            "value_hist": [h["value"] for h in hist],
        }

    for i, s in enumerate(sorted(stocks.values(), key=lambda s: -s["value"])):
        s["value_rank"] = i + 1
    for i, s in enumerate(sorted(stocks.values(), key=lambda s: -s["avg_value"])):
        s["avg_value_rank"] = i + 1

    # Heat: unusual volume, a big move, a top turnover rank, headlines, an exchange flag.
    for s in stocks.values():
        s["heat"] = round(
            1.5 * max(0.0, math.log2(max(s["vol_ratio"], 1e-6)))
            + 0.25 * min(abs(s["chg_pct"]), 10)
            + 2.0 * max(0.0, 1 - s["value_rank"] / 150)
            + 0.6 * min(s["mentions"], 5)
            + (1.0 if s["attention"] else 0.0), 2)
    liquid = [s for s in stocks.values() if s["avg_value"] >= MIN_VALUE or s["value"] >= 3 * MIN_VALUE]
    hot = sorted(liquid, key=lambda s: -s["heat"])[:HOT_COUNT]
    hot_codes = {s["code"] for s in sorted(liquid, key=lambda s: -s["heat"])[:40]}

    # Heat three trading days ago, to tell newly hot from fading.
    def past_heat(s, back=3):
        if len(s["value_hist"]) <= back + 1:
            return None
        base = s["value_hist"][:-(back + 1)]
        ref = s["value_hist"][-(back + 1)]
        return ref / (sum(base) / len(base) or 1)
    cooling = []
    for s in liquid:
        then = past_heat(s)
        if then and then >= 2.5 and s["vol_ratio"] < 1.0:
            cooling.append({**s, "then_ratio": then})
    cooling.sort(key=lambda s: -s["then_ratio"])

    # Sectors: share of market turnover today against the window average.
    sector_today, sector_avg = defaultdict(float), defaultdict(float)
    for s in stocks.values():
        sector_today[s["industry"]] += s["value"]
        sector_avg[s["industry"]] += s["avg_value"]
    total_today, total_avg = sum(sector_today.values()) or 1, sum(sector_avg.values()) or 1
    sectors = []
    for name in sector_today:
        share, base = sector_today[name] / total_today, sector_avg[name] / total_avg
        if base > 0.002:
            sectors.append({"industry": name, "share": share * 100, "base": base * 100,
                            "change": (share / base - 1) * 100})
    sectors.sort(key=lambda x: -x["change"])
    hot_sectors = {x["industry"] for x in sectors[:5]}

    # Quiet candidates: steady institutional buying before the crowd and the press arrive.
    hidden = []
    for s in liquid:
        if (s["code"] in hot_codes or s["mentions"] >= 3 or s["ret_window_pct"] > 25
                or (s["cap"] or 0) > MAX_CAP
                or (s["cap"] is None and s["avg_value_rank"] <= LARGE_CAP_RANK)):
            continue
        trust_streak, foreign_streak = _streak(s["trust"]), _streak(s["foreign"])
        trust_5d = sum(s["trust"][-5:]) / s["avg_volume"] * 100
        foreign_5d = sum(s["foreign"][-5:]) / s["avg_volume"] * 100
        near_high = s["close"] >= 0.95 * s["high_window"]
        score = (min(trust_streak, 5) + 0.5 * min(foreign_streak, 5)
                 + min(max(trust_5d, 0), 20) / 4 + min(max(foreign_5d, 0), 40) / 10
                 + (1.0 if 1.2 <= s["vol_ratio"] <= 3 else 0.0)
                 + (1.0 if -5 <= s["ret_window_pct"] <= 12 else 0.0)
                 + (0.5 if near_high else 0.0)
                 + (1.0 if s["mentions"] == 0 else 0.0)
                 + (1.0 if s["industry"] in hot_sectors else 0.0))
        if trust_streak >= 2 or foreign_streak >= 3 or trust_5d >= 3:
            hidden.append({**s, "score": round(score, 2), "trust_streak": trust_streak,
                           "foreign_streak": foreign_streak, "trust_5d_pct": trust_5d,
                           "foreign_5d_pct": foreign_5d, "near_high": near_high,
                           "hot_sector": s["industry"] in hot_sectors})
    hidden.sort(key=lambda s: -s["score"])

    up = sum(1 for s in stocks.values() if s["chg_pct"] > 0)
    down = sum(1 for s in stocks.values() if s["chg_pct"] < 0)
    market_value = sum(s["value"] for s in stocks.values())
    market_avg = sum(s["avg_value"] for s in stocks.values())
    news.sort(key=lambda n: n["time"] or datetime.min.replace(tzinfo=UTC), reverse=True)
    return {
        "date": today.isoformat(), "window": [d.isoformat() for d, _ in days],
        "generated": datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M"),
        "index": latest.get("_index"), "up": up, "down": down,
        "market_value": market_value, "market_value_ratio": market_value / (market_avg or 1),
        "hot": hot, "cooling": cooling[:10], "sectors": sectors, "hidden": hidden[:HIDDEN_COUNT],
        "news": news[:80], "missing": list(sources.MISSING),
    }


def _flows(s) -> str:
    return f"{_lots(s['foreign'][-1])} / {_lots(s['trust'][-1])} / {_lots(s['dealer'][-1])}"


def render(scan: dict) -> str:
    idx = scan["index"] or {}
    lines = [
        f"# 台股每日掃描資料包 — 交易日 {scan['date']}",
        f"產生時間 {scan['generated']}（台北）；比較區間 {scan['window'][0]} ~ {scan['window'][-1]}"
        f"（{len(scan['window'])} 個交易日）",
        "",
        *([f"⚠️ 以下資料讀取失敗、未納入計算：{'；'.join(scan['missing'])}", ""] if scan["missing"] else []),
        "## 大盤",
        f"- 加權指數 {idx.get('close', 0):,.2f}（{idx.get('change', 0):+,.2f} 點）",
        f"- 上漲 {scan['up']} 家、下跌 {scan['down']} 家（上市＋上櫃普通股）",
        f"- 成交金額 NT$ {scan['market_value'] / 1e8:,.0f} 億，為區間日均的 {scan['market_value_ratio']:.2f} 倍",
        "",
        "## 產業資金熱度（今日成交占比 vs 區間平均）",
        "| 產業 | 今日占比 | 平均占比 | 變化 |",
        "|---|---:|---:|---:|",
    ]
    for x in scan["sectors"][:8] + [None] + scan["sectors"][-5:]:
        if x is None:
            lines.append("| …（以下為資金流出最多） | | | |")
            continue
        lines.append(f"| {x['industry']} | {x['share']:.1f}% | {x['base']:.1f}% | {x['change']:+.0f}% |")

    lines += [
        "", "## 熱門股（熱度分數 = 量能放大＋漲跌幅＋成交排名＋新聞/PTT 提及＋注意股）",
        "| 代號 | 名稱 | 市場 | 產業 | 收盤 | 漲跌 | 量比 | 成交排名 | 外資/投信/自營(張) | 提及 | 注意股 | 熱度 |",
        "|---|---|---|---|---:|---:|---:|---:|---|---:|---|---:|",
    ]
    for s in scan["hot"]:
        lines.append(
            f"| {s['code']} | {s['name']} | {s['market']} | {s['industry']} | {s['close']:g} | "
            f"{s['chg_pct']:+.1f}% | {s['vol_ratio']:.1f} | {s['value_rank']} | {_flows(s)} | "
            f"{s['mentions']} | {s['attention'] or ''} | {s['heat']} |")

    lines += ["", "## 退燒中（3 個交易日前爆量，今天量能已縮回平均以下）",
              "| 代號 | 名稱 | 產業 | 當時量比 | 今日量比 | 今日漲跌 | 區間報酬 |", "|---|---|---|---:|---:|---:|---:|"]
    for s in scan["cooling"]:
        lines.append(f"| {s['code']} | {s['name']} | {s['industry']} | {s['then_ratio']:.1f} | "
                     f"{s['vol_ratio']:.1f} | {s['chg_pct']:+.1f}% | {s['ret_window_pct']:+.1f}% |")

    lines += [
        "", f"## 潛力股候選（市值 {MAX_CAP / 1e8:,.0f} 億以下；法人悄悄進場、新聞還少、股價還沒大漲）",
        "投信/外資連買 = 最近連續淨買天數；5日買超% = 近5日淨買股數占區間日均成交量的比例。",
        "| 代號 | 名稱 | 市場 | 產業 | 市值(億) | 收盤 | 區間報酬 | 量比 | 投信連買 | 投信5日% | 外資連買 | 外資5日% "
        "| 近區間高點 | 熱門產業 | 提及 | 分數 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|",
    ]
    for s in scan["hidden"]:
        lines.append(
            f"| {s['code']} | {s['name']} | {s['market']} | {s['industry']} | "
            f"{(s['cap'] or 0) / 1e8:,.0f} | {s['close']:g} | {s['ret_window_pct']:+.1f}% | {s['vol_ratio']:.1f} | {s['trust_streak']} | "
            f"{s['trust_5d_pct']:.1f} | {s['foreign_streak']} | {s['foreign_5d_pct']:.1f} | "
            f"{'是' if s['near_high'] else ''} | {'是' if s['hot_sector'] else ''} | "
            f"{s['mentions']} | {s['score']} |")

    lines += ["", "## 最新新聞與 PTT 標題（新到舊）"]
    for n in scan["news"]:
        when = n["time"].astimezone(TAIPEI).strftime("%m/%d %H:%M") if n["time"] else ""
        lines.append(f"- [{n['source']}] {when} {n['title']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", help="last trading day to include (YYYY-MM-DD); default today in Taipei")
    parser.add_argument("--out", default="out", help="directory for datapack.md and scan.json")
    args = parser.parse_args()
    end = date.fromisoformat(args.date) if args.date else datetime.now(TAIPEI).date()
    scan = build(end)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "datapack.md").write_text(render(scan), encoding="utf-8")
    (out / "scan.json").write_text(json.dumps(scan, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
    print(f"wrote {out / 'datapack.md'} for trading day {scan['date']}")


if __name__ == "__main__":
    main()
