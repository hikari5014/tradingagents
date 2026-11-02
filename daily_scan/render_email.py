"""Render a report (JSON written by the editor agent) as a designed HTML email.

    python -m daily_scan.render_email report.json > report.html

Email clients drop <style> blocks and most layout CSS, so the page is built
from tables with inline styles, 640px wide, and reads on a phone. Taiwan
colours: red is up, green is down. Every text field is escaped; the JSON
schema is documented in PROMPT_full.md.
"""

from __future__ import annotations

import json
import sys
from html import escape

INK, MUTED, LINE, PAPER, CARD = "#1f2933", "#6b7785", "#e4e8ee", "#f3f5f8", "#ffffff"
NAVY, GOLD = "#14213d", "#f2b632"
UP, DOWN = "#d64545", "#1f9d55"
BADGES = {
    "延續": ("#fde8e8", "#b42318"), "觀望": ("#fef3d7", "#a15c07"), "可能退燒": ("#e6f0fb", "#1d5fa8"),
    "高": ("#fde8e8", "#b42318"), "中": ("#fef3d7", "#a15c07"), "低": ("#eef1f4", "#52606d"),
}
FONT = "'PingFang TC','Noto Sans TC','Microsoft JhengHei',Arial,sans-serif"


def e(value) -> str:
    return escape(str(value if value is not None else ""))


def move_color(text) -> str:
    s = str(text).strip()
    return UP if s.startswith("+") else DOWN if s.startswith(("-", "−")) else INK


def badge(label: str) -> str:
    bg, fg = BADGES.get(label, ("#eef1f4", "#52606d"))
    return (f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;background:{bg};'
            f'color:{fg};font-size:12px;font-weight:700;white-space:nowrap">{e(label)}</span>')


def section(title: str, body: str, icon: str = "") -> str:
    return (
        f'<tr><td style="padding:28px 28px 8px"><div style="font-size:18px;font-weight:800;color:{NAVY};'
        f'border-left:4px solid {GOLD};padding-left:10px">{e(icon)} {e(title)}</div></td></tr>'
        f'<tr><td style="padding:4px 28px 4px">{body}</td></tr>')


def card(inner: str, accent: str = LINE) -> str:
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:10px 0;'
            f'background:{CARD};border:1px solid {LINE};border-top:3px solid {accent};border-radius:10px">'
            f'<tr><td style="padding:14px 16px">{inner}</td></tr></table>')


def para(label: str, text) -> str:
    if not text:
        return ""
    return (f'<div style="margin-top:8px;font-size:14px;line-height:1.65;color:{INK}">'
            f'<b style="color:{NAVY}">{e(label)}</b>　{e(text)}</div>')


def stock_chips(stocks) -> str:
    chips = []
    for s in stocks or []:
        chg = s.get("chg", "")
        chips.append(
            f'<span style="display:inline-block;margin:4px 6px 0 0;padding:3px 8px;border:1px solid {LINE};'
            f'border-radius:6px;font-size:13px;color:{INK}">{e(s.get("code"))} {e(s.get("name"))} '
            f'<b style="color:{move_color(chg)}">{e(chg)}</b></span>')
    return "".join(chips)


def kpis(market: dict) -> str:
    if not market:
        return ""
    cells = [
        ("加權指數", market.get("index"), f'{market.get("index_change", "")}（{market.get("index_pct", "")}）'),
        ("上漲 / 下跌", f'{market.get("up", "")} / {market.get("down", "")}', "家"),
        ("成交金額", market.get("value"), f'均量的 {market.get("value_vs_avg", "")}'),
    ]
    tds = []
    for label, big, small in cells:
        color = move_color(small) if label == "加權指數" else MUTED
        tds.append(
            f'<td width="33%" style="padding:6px"><div style="background:{CARD};border:1px solid {LINE};'
            f'border-radius:10px;padding:12px;text-align:center"><div style="font-size:12px;color:{MUTED}">'
            f'{e(label)}</div><div style="font-size:20px;font-weight:800;color:{INK};margin:4px 0">{e(big)}</div>'
            f'<div style="font-size:12px;color:{color}">{e(small)}</div></div></td>')
    return (f'<tr><td style="padding:16px 22px 0"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0"><tr>{"".join(tds)}</tr></table></td></tr>')


def table(headers: list[str], rows: list[list], move_cols=()) -> str:
    head = "".join(f'<th style="padding:8px;text-align:left;font-size:12px;color:{MUTED};'
                   f'border-bottom:2px solid {LINE}">{e(h)}</th>' for h in headers)
    body = []
    for row in rows:
        tds = []
        for i, v in enumerate(row):
            color = move_color(v) if i in move_cols else INK
            tds.append(f'<td style="padding:8px;font-size:13px;color:{color};border-bottom:1px solid {LINE}">{e(v)}</td>')
        body.append(f"<tr>{''.join(tds)}</tr>")
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{CARD};'
            f'border:1px solid {LINE};border-radius:10px">'
            f'<tr>{head}</tr>{"".join(body)}</table>')


def render(r: dict) -> str:
    rows = []
    summary = "".join(f'<li style="margin:4px 0">{e(s)}</li>' for s in r.get("summary") or [])
    rows.append(
        f'<tr><td style="background:{NAVY};padding:26px 28px;border-radius:14px 14px 0 0">'
        f'<div style="font-size:12px;letter-spacing:2px;color:{GOLD};font-weight:700">'
        f'台股 AI 研究室 · {e(r.get("session"))}</div>'
        f'<div style="font-size:24px;font-weight:800;color:#fff;margin-top:6px">{e(r.get("date"))}</div>'
        f'<div style="font-size:16px;color:#dfe6f0;margin-top:10px;line-height:1.6">{e(r.get("headline"))}</div>'
        f'</td></tr>')
    rows.append(kpis(r.get("market") or {}))
    if summary:
        rows.append(section("今日重點", f'<ul style="margin:0;padding-left:20px;font-size:15px;line-height:1.7;'
                                     f'color:{INK}">{summary}</ul>', "📌"))

    if r.get("global"):
        cells = "".join(
            f'<td style="padding:6px"><div style="background:{CARD};border:1px solid {LINE};border-radius:8px;'
            f'padding:10px;text-align:center"><div style="font-size:12px;color:{MUTED}">{e(g.get("label"))}</div>'
            f'<div style="font-size:16px;font-weight:800;color:{move_color(g.get("value"))}">{e(g.get("value"))}</div>'
            f'</div></td>' for g in r["global"][:4])
        notes = "".join(para("", g.get("note")) for g in r["global"] if g.get("note"))
        rows.append(section("隔夜國際盤", f'<table role="presentation" width="100%"><tr>{cells}</tr></table>'
                            + para("今日焦點", r.get("global_focus")) + notes, "🌏"))

    if r.get("themes"):
        cards = []
        for t in r["themes"]:
            head = (f'<table role="presentation" width="100%"><tr><td style="font-size:16px;font-weight:800;'
                    f'color:{INK}">{e(t.get("name"))}</td><td align="right">{badge(t.get("forecast", "觀望"))}'
                    f'</td></tr></table>')
            cards.append(card(head + stock_chips(t.get("stocks")) + para("為什麼熱", t.get("why"))
                              + para("法人態度", t.get("institutions")) + para("熱度預估", t.get("reason")), UP))
        rows.append(section("熱門題材", "".join(cards), "🔥"))

    if r.get("cooling"):
        items = "".join(f'<li style="margin:6px 0"><b>{e(c.get("name"))}</b>　{e(c.get("note"))}</li>'
                        for c in r["cooling"])
        rows.append(section("退燒中", f'<ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.6;'
                                    f'color:{INK}">{items}</ul>', "🧊"))

    flows = r.get("flows") or {}
    if flows.get("in") or flows.get("out"):
        def col(title, items, color):
            li = "".join(f'<div style="font-size:14px;margin:4px 0;color:{INK}">{e(x.get("industry"))} '
                         f'<b style="color:{color}">{e(x.get("change"))}</b></div>' for x in items or [])
            return (f'<td width="50%" valign="top" style="padding:6px"><div style="background:{CARD};'
                    f'border:1px solid {LINE};border-radius:10px;padding:12px"><div style="font-size:12px;'
                    f'color:{MUTED};margin-bottom:4px">{title}</div>{li}</div></td>')
        rows.append(section("資金流向", f'<table role="presentation" width="100%"><tr>'
                            f'{col("資金流入", flows.get("in"), UP)}{col("資金流出", flows.get("out"), DOWN)}'
                            f'</tr></table>', "💰"))

    if r.get("radar"):
        rows.append(section("潛力股雷達（明早深入研究）", table(
            ["股票", "訊號"], [[f'{x.get("code")} {x.get("name")}', x.get("signal")] for x in r["radar"]]), "🔭"))

    if r.get("deep_dives"):
        cards = []
        for d in r["deep_dives"]:
            head = (f'<table role="presentation" width="100%"><tr><td><span style="font-size:17px;font-weight:800;'
                    f'color:{INK}">{e(d.get("code"))} {e(d.get("name"))}</span> <span style="font-size:12px;'
                    f'color:{MUTED}">{e(d.get("market"))} · {e(d.get("industry"))} · 收 {e(d.get("close"))}</span>'
                    f'</td><td align="right">研究優先度 {badge(d.get("priority", "中"))}</td></tr></table>'
                    f'<div style="margin-top:8px;padding:10px 12px;background:#fff8e6;border-radius:8px;'
                    f'font-size:14px;color:{INK}">💡 {e(d.get("highlight"))}</div>')
            debate = (f'<table role="presentation" width="100%" style="margin-top:10px"><tr>'
                      f'<td width="50%" valign="top" style="padding:8px;background:#fdf1f1;border-radius:8px;'
                      f'font-size:13px;line-height:1.6"><b style="color:{UP}">看多</b><br>{e(d.get("bull"))}</td>'
                      f'<td width="8"></td><td width="50%" valign="top" style="padding:8px;background:#eef8f2;'
                      f'border-radius:8px;font-size:13px;line-height:1.6"><b style="color:{DOWN}">看空</b><br>'
                      f'{e(d.get("bear"))}</td></tr></table>')
            watch = "".join(f'<li>{e(w)}</li>' for w in d.get("watch") or [])
            cards.append(card(
                head + para("基本面", d.get("fundamentals")) + para("籌碼", d.get("chips"))
                + para("技術面", d.get("technical")) + debate + para("主要風險", d.get("risks"))
                + para("看錯訊號", d.get("wrong_if"))
                + (f'<div style="margin-top:8px;font-size:14px;color:{INK}"><b style="color:{NAVY}">追蹤訊號</b>'
                   f'<ul style="margin:4px 0 0;padding-left:20px;line-height:1.6">{watch}</ul></div>' if watch else ""),
                GOLD))
        rows.append(section("潛力股深入研究", "".join(cards), "🔭"))

    track = r.get("track") or {}
    if track.get("rows"):
        rows.append(section("過去潛力股追蹤", table(
            ["股票", "選出日", "當時價", "最新價", "報酬"],
            [[f'{x.get("code")} {x.get("name", "")}', x.get("picked"), x.get("then"), x.get("now"), x.get("ret")]
             for x in track["rows"]], move_cols=(4,)) + para("檢討", track.get("comment")), "📊"))

    warnings = "".join(f'<li>{e(w)}</li>' for w in r.get("warnings") or [])
    link = r.get("links", {}).get("drive")
    rows.append(
        f'<tr><td style="padding:24px 28px 28px"><div style="background:{PAPER};border-radius:10px;padding:14px 16px;'
        f'font-size:12px;line-height:1.7;color:{MUTED}">'
        + (f'<b>提醒</b><ul style="margin:4px 0 8px;padding-left:18px">{warnings}</ul>' if warnings else "")
        + (f'完整資料與各分析師報告：<a href="{e(link)}" style="color:{NAVY}">Google Drive</a><br>' if link else "")
        + '本報告由 AI 自動整理公開資料產生，為資訊整理，不構成投資建議。紅色為上漲、綠色為下跌。</div></td></tr>')

    return (
        f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(r.get("title"))}</title></head>'
        f'<body style="margin:0;padding:0;background:{PAPER}">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAPER}">'
        f'<tr><td align="center" style="padding:20px 10px">'
        f'<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;'
        f'background:#fbfcfd;border-radius:14px;font-family:{FONT};box-shadow:0 2px 12px rgba(20,33,61,.08)">'
        + "".join(rows) + '</table></td></tr></table></body></html>')


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "-"
    if path == "-":
        data = json.load(sys.stdin)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    sys.stdout.write(render(data))


if __name__ == "__main__":
    main()
