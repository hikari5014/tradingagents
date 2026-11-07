"""Free, keyless Taiwan market-wide sources: TWSE, TPEx, FinMind, news and PTT.

Every fetcher returns plain dicts keyed by stock code, so the scan never cares
which exchange a figure came from. The exchanges throttle bursts, so requests to
them are spaced out.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import sys
import time
from datetime import UTC, date, datetime, timedelta

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (daily_scan; research)"}
TIMEOUT = 30
_EXCHANGE_PAUSE = 6.0   # seconds between exchange requests; bursts get an IP blocked
_BLOCK_BACKOFF = 90     # seconds to wait when an exchange answers with a non-JSON page (a temporary block)
_last_exchange_call = 0.0

# Common stocks have a four-digit code; ETFs, warrants and bonds do not.
STOCK_CODE = re.compile(r"^[1-9]\d{3}$")


class _Cached:
    def __init__(self, text: str):
        self.text = text

    def json(self):
        import json
        return json.loads(self.text)


def _get(url: str, *, exchange: bool = False, tries: int = 6, **params):
    """GET with spacing for the exchanges and retries: large tables sometimes arrive cut off.

    With DAILY_SCAN_CACHE set to a directory, dated exchange tables are kept there
    so a re-run of the same day reads them back instead of downloading again.
    """
    global _last_exchange_call
    cache_dir = os.getenv("DAILY_SCAN_CACHE")
    cache = None
    if cache_dir and exchange and "date" in params:
        key = hashlib.sha1(f"{url}?{sorted(params.items())}".encode()).hexdigest()
        cache = os.path.join(cache_dir, key + ".json")
        if os.path.exists(cache):
            with open(cache, encoding="utf-8") as f:
                return _Cached(f.read())
    for attempt in range(tries):
        if exchange:
            wait = _EXCHANGE_PAUSE - (time.monotonic() - _last_exchange_call)
            if wait > 0:
                time.sleep(wait)
            _last_exchange_call = time.monotonic()
        try:
            response = requests.get(url, params=params or None, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            response.json() if "json" in str(params.get("response", "")) else None
            if cache:
                os.makedirs(cache_dir, exist_ok=True)
                with open(cache, "w", encoding="utf-8") as f:
                    f.write(response.text)
            return response
        except (requests.RequestException, ValueError) as exc:
            if attempt == tries - 1:
                raise
            # A non-JSON answer from an exchange is its throttle page: the block lasts
            # a minute or more, so a short retry only burns attempts.
            blocked = exchange and isinstance(exc, (ValueError, requests.Timeout))
            delay = _BLOCK_BACKOFF * (attempt + 1) if blocked else 3 * (attempt + 1)
            print(f"[scan] {url.split('/')[2]} {params.get('date', '')}: {type(exc).__name__}, "
                  f"retry {attempt + 2}/{tries} in {delay}s", file=sys.stderr, flush=True)
            time.sleep(delay)


def _num(text) -> float:
    """A figure from an exchange table: '1,234', '-0.31 ', '--' or HTML-wrapped."""
    cleaned = re.sub(r"<[^>]+>", "", str(text)).replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _twse_sign(cell) -> float:
    """TWSE writes the direction apart from the amount, as '<p ...>-</p>' or '+'."""
    return -1.0 if "-" in re.sub(r"<[^>]+>", "", str(cell)) else 1.0


# --- daily quotes and institutional flows ----------------------------------

def twse_day(day: date) -> dict[str, dict] | None:
    """TWSE closing quotes for one day, or None when the market was closed."""
    body = _get("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX", exchange=True,
                date=day.strftime("%Y%m%d"), type="ALLBUT0999", response="json").json()
    table = next((t for t in body.get("tables", []) if "每日收盤行情" in str(t.get("title"))), None)
    if not table or not table.get("data"):
        return None
    out = {}
    for row in table["data"]:
        code = row[0].strip()
        if not STOCK_CODE.match(code):
            continue
        close = _num(row[8])
        change = _twse_sign(row[9]) * _num(row[10])
        out[code] = {"name": row[1].strip(), "market": "上市", "close": close,
                     "change": change, "volume": _num(row[2]), "value": _num(row[4])}
    index = next((t for t in body.get("tables", []) if "價格指數(臺灣證券交易所)" in str(t.get("title"))), None)
    if index:
        for row in index["data"]:
            if row[0].strip() == "發行量加權股價指數":
                out["_index"] = {"close": _num(row[1]), "change": _twse_sign(row[2]) * _num(row[3])}
    return out


def twse_institutional(day: date) -> dict[str, dict]:
    body = _get("https://www.twse.com.tw/rwd/zh/fund/T86", exchange=True,
                date=day.strftime("%Y%m%d"), selectType="ALLBUT0999", response="json").json()
    out = {}
    for row in body.get("data") or []:
        code = row[0].strip()
        if STOCK_CODE.match(code):
            out[code] = {"foreign": _num(row[4]) + _num(row[7]), "trust": _num(row[10]),
                         "dealer": _num(row[11])}
    return out


def _tpex_date(day: date) -> str:
    return day.strftime("%Y/%m/%d")


def tpex_day(day: date) -> dict[str, dict] | None:
    body = _get("https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes", exchange=True,
                date=_tpex_date(day), response="json").json()
    tables = body.get("tables") or []
    if not tables or not tables[0].get("data") or body.get("date") != day.strftime("%Y%m%d"):
        return None
    out = {}
    for row in tables[0]["data"]:
        code = row[0].strip()
        if STOCK_CODE.match(code):
            out[code] = {"name": row[1].strip(), "market": "上櫃", "close": _num(row[2]),
                         "change": _num(row[3]), "volume": _num(row[8]), "value": _num(row[9]),
                         "shares": _num(row[15])}
    return out


def tpex_institutional(day: date) -> dict[str, dict]:
    body = _get("https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade", exchange=True,
                type="Daily", sect="EW", date=_tpex_date(day), response="json").json()
    tables = body.get("tables") or []
    out = {}
    for row in (tables[0].get("data") if tables else None) or []:
        code = row[0].strip()
        if STOCK_CODE.match(code):
            out[code] = {"foreign": _num(row[10]), "trust": _num(row[13]), "dealer": _num(row[22])}
    return out


# Days a source could not be read, for the data pack to disclose.
MISSING: list[str] = []


def _optional(fetch, day: date, label: str) -> dict:
    try:
        return fetch(day) or {}
    except (requests.RequestException, ValueError) as exc:
        MISSING.append(f"{day} {label}: {type(exc).__name__}")
        return {}


def trading_days(end: date, count: int) -> list[tuple[date, dict]]:
    """The last ``count`` trading days up to ``end``: (day, {code: quote + flows}), oldest first.

    TWSE decides whether a day traded; a TPEx or flow table that cannot be read
    is left out of that day and recorded in MISSING rather than ending the scan.
    """
    days: list[tuple[date, dict]] = []
    day = end
    for _ in range(count * 3):          # long holidays leave gaps
        if len(days) == count:
            break
        if day.weekday() < 5:
            listed = twse_day(day)
            if listed:
                merged = dict(listed)
                otc = _optional(tpex_day, day, "上櫃行情")
                merged.update(otc)
                for flows in (_optional(twse_institutional, day, "上市法人"),
                              _optional(tpex_institutional, day, "上櫃法人") if otc else {}):
                    for code, f in flows.items():
                        if code in merged:
                            merged[code].update(f)
                days.append((day, merged))
        day -= timedelta(days=1)
    return list(reversed(days))


# --- attention lists, industries, news -------------------------------------

def attention_stocks() -> dict[str, str]:
    """Stocks the exchanges flagged today for unusual trading, with the reason."""
    out = {}
    try:
        body = _get("https://www.twse.com.tw/rwd/zh/announcement/notice", exchange=True, response="json").json()
        for row in body.get("data") or []:
            if STOCK_CODE.match(str(row[1]).strip()):
                out[row[1].strip()] = str(row[4])[:60]
        body = _get("https://www.tpex.org.tw/www/zh-tw/bulletin/attention", exchange=True, response="json").json()
        for row in (body.get("tables") or [{}])[0].get("data") or []:
            if STOCK_CODE.match(str(row[1]).strip()):
                out[row[1].strip()] = str(row[4])[:60]
    except (requests.RequestException, ValueError, IndexError):
        pass
    return out


def twse_shares() -> dict[str, float]:
    """Shares outstanding of every TWSE-listed company (TPEx quotes carry their own)."""
    try:
        rows = _get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L").json()
    except (requests.RequestException, ValueError):
        return {}
    return {r["公司代號"].strip(): _num(r.get("已發行普通股數或TDR原股發行股數", 0)) for r in rows}


def industries() -> dict[str, str]:
    """Industry of every listed stock, from FinMind (keyless)."""
    try:
        body = _get("https://api.finmindtrade.com/api/v4/data", dataset="TaiwanStockInfo").json()
    except (requests.RequestException, ValueError):
        return {}
    return {r["stock_id"]: r["industry_category"] for r in body.get("data") or []}


def cnyes_news(pages: int = 3) -> list[dict]:
    """Latest Taiwan-stock headlines from cnyes, each with the codes it is tagged with."""
    items = []
    for page in range(1, pages + 1):
        try:
            body = _get("https://api.cnyes.com/media/api/v1/newslist/category/tw_stock",
                        limit=30, page=page).json()
        except (requests.RequestException, ValueError):
            break
        for it in body.get("items", {}).get("data", []):
            codes = [m.get("code") for m in it.get("market") or [] if m.get("code")]
            items.append({"source": "鉅亨", "title": html.unescape(it.get("title", "")),
                          "time": datetime.fromtimestamp(int(it.get("publishAt", 0)), UTC),
                          "codes": codes})
    return items


def yahoo_news() -> list[dict]:
    try:
        text = _get("https://tw.stock.yahoo.com/rss", category="tw-market").text
    except requests.RequestException:
        return []
    out = []
    for item in re.findall(r"<item>(.*?)</item>", text, re.S):
        title = re.search(r"<title><!\[CDATA\[(.*?)\]\]>", item, re.S)
        when = re.search(r"<pubDate>(.*?)</pubDate>", item)
        if title:
            try:
                ts = datetime.strptime(when.group(1).strip(), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=UTC)
            except (AttributeError, ValueError):
                ts = None
            out.append({"source": "Yahoo", "title": html.unescape(title.group(1)), "time": ts, "codes": []})
    return out


def ptt_titles(pages: int = 4) -> list[dict]:
    """Recent PTT Stock board post titles: retail chatter, the earliest heat signal."""
    out, url = [], "https://www.ptt.cc/bbs/Stock/index.html"
    for _ in range(pages):
        try:
            text = _get(url).text
        except requests.RequestException:
            break
        for href, title in re.findall(r'<div class="title">\s*<a href="([^"]+)">([^<]+)</a>', text):
            if "[公告]" in title:
                continue
            stamp = re.search(r"M\.(\d{10})\.", href)
            ts = datetime.fromtimestamp(int(stamp.group(1)), UTC) if stamp else None
            out.append({"source": "PTT", "title": html.unescape(title.strip()), "time": ts, "codes": []})
        prev = re.search(r'href="(/bbs/Stock/index\d+\.html)">&lsaquo;', text)
        if not prev:
            break
        url = "https://www.ptt.cc" + prev.group(1)
    return out
