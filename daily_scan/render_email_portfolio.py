"""Portfolio-style email design (demo): the same report JSON as render_email.

    python -m daily_scan.render_email_portfolio report.json > report.html

Dotted-grid backdrop, an oversized black display masthead with a pill letter,
small letter-spaced labels, white rounded cards with soft shadows, black pill
buttons and one indigo accent. Built from tables with inline styles so Gmail
keeps it; the dot grid and shadows simply drop out where a client ignores them.
Taiwan colours: red is up, green is down.
"""

from __future__ import annotations

import json
import sys

from daily_scan.render_email import LEVELS, e, move_color, num

BLACK, INK, GREY, LIGHT = "#0d0f14", "#1b1f2a", "#6b7280", "#9aa1ad"
INDIGO, LAVENDER, LAVENDER_2 = "#4f5bd5", "#eef0ff", "#dfe3ff"
UP, DOWN = "#e0453a", "#16a05d"
LINE = "#eceef2"
DISPLAY = "'Helvetica Neue','Arial Black',Arial,'PingFang TC','Microsoft JhengHei',sans-serif"
SANS = "'Helvetica Neue',Arial,'PingFang TC','Microsoft JhengHei',sans-serif"
SCRIPT = "'Bradley Hand','Segoe Script','Snell Roundhand',cursive"
PAGE = ("background-color:#f3f4f7;background-image:radial-gradient(#d5d8e0 1px,transparent 1px);"
        "background-size:22px 22px;")
CARD = ("background-color:#ffffff;border:1px solid #ffffff;border-radius:28px;"
        "box-shadow:0 18px 50px rgba(30,36,60,.10),0 2px 6px rgba(30,36,60,.04);")
EDITION_NO = {"每日詳細報告": "01", "收盤快報": "02", "晚間快報": "03"}
EDITION_EN = {"每日詳細報告": "MORNING", "收盤快報": "CLOSING", "晚間快報": "EVENING"}


def label(text: str, color: str = GREY, size: int = 11) -> str:
    return (f'<span style="font:600 {size}px/1.5 {SANS};letter-spacing:3px;color:{color};'
            f'text-transform:uppercase">{e(text)}</span>')


def pill(text: str, fg: str, bg: str, dot: str | None = None) -> str:
    d = (f'<span style="display:inline-block;width:7px;height:7px;border-radius:7px;background-color:{dot};'
         f'margin-right:7px;vertical-align:1px"></span>' if dot else "")
    return (f'<span style="display:inline-block;padding:6px 14px;border-radius:999px;background-color:{bg};'
            f'font:700 11px/1.3 {SANS};letter-spacing:1px;color:{fg};white-space:nowrap">{d}{e(text)}</span>')


def arrow_badge(bg: str = LAVENDER, fg: str = INDIGO, size: int = 30) -> str:
    return (f'<span style="display:inline-block;width:{size}px;height:{size}px;line-height:{size}px;'
            f'text-align:center;border-radius:{size}px;background-color:{bg};color:{fg};'
            f'font:700 15px/{size}px {SANS}">&#8599;</span>')


def black_button(text: str, href: str) -> str:
    return (f'<a href="{e(href)}" style="display:inline-block;padding:13px 26px;border-radius:999px;'
            f'background-color:{BLACK};color:#ffffff;font:700 14px/1 {SANS};text-decoration:none">'
            f'{e(text)}&nbsp;&nbsp;&rarr;</a>')


def meter(level: int, color: str) -> str:
    cells = "".join(f'<td width="18%" style="height:5px;border-radius:5px;background-color:'
                    f'{color if i < level else "rgba(255,255,255,.22)"}"></td><td width="2.5%"></td>'
                    for i in range(5))
    return f'<table role="presentation" width="96" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table>'


def bar(fraction: float, color: str) -> str:
    pct = max(3, min(100, round(fraction * 100)))
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="{pct}%" style="height:10px;border-radius:10px;background-color:{color}"></td>'
            f'<td width="{100 - pct}%" style="height:10px;border-radius:10px;background-color:#f1f2f5"></td>'
            f'</tr></table>')


def section_title(title: str, english: str, more: str = "") -> str:
    return (f'<table role="presentation" width="100%" style="margin-bottom:16px"><tr><td>'
            f'<span style="font:800 24px/1.2 {DISPLAY};color:{BLACK};letter-spacing:-.5px">{e(title)}</span>'
            f'&nbsp;&nbsp;{arrow_badge()}</td>'
            f'<td align="right" style="font:500 12px/1 {SANS};color:{GREY}">{label(english, LIGHT, 10)}'
            f'{"<br>" + e(more) if more else ""}</td></tr></table>')


def wrap_card(inner: str, pad: str = "30px 30px") -> str:
    return (f'<tr><td class="card-out" style="padding:12px 16px"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" style="{CARD}"><tr><td class="card-pad" style="padding:{pad}">{inner}</td></tr></table></td></tr>')


def masthead(r: dict) -> str:
    session = r.get("session") or ""
    side = "".join(f'<div style="font:500 12px/1.75 {SANS};letter-spacing:2px;color:{GREY}">{w}</div>'
                   for w in ("HEAT", "FLOWS", "RADAR", "TRACK"))
    # The pill stands in for the "o", as in the reference's masthead.
    pill_o = ('<span class="pill-o" style="display:inline-block;width:78px;height:30px;border:13px solid #0d0f14;'
              'border-radius:999px;vertical-align:-2px;margin:0 3px"></span>')
    return (
        f'<tr><td style="padding:26px 22px 4px"><table role="presentation" width="100%"><tr>'
        f'<td valign="top"><table role="presentation"><tr><td valign="middle" style="padding-right:14px">'
        f'<div style="width:46px;height:2px;background-color:{BLACK}"></div></td><td>'
        f'{label("Taiwan Equity", INK, 11)}<br>{label("AI Daily Series", INK, 11)}</td></tr></table></td>'
        f'<td align="right" valign="top" style="font:800 24px/1 {DISPLAY};color:{BLACK}">'
        f'{EDITION_NO.get(session, "01")} / 03</td></tr></table></td></tr>'
        f'<tr><td style="padding:18px 22px 6px"><table role="presentation" width="100%"><tr>'
        f'<td class="mast" valign="bottom" style="font:900 86px/0.9 {DISPLAY};color:{BLACK};letter-spacing:-4px;'
        f'white-space:nowrap">St{pill_o}cks<span style="font:400 40px/1 {SANS};color:{INDIGO};'
        f'vertical-align:top;letter-spacing:0;margin-left:4px">&#10022;</span></td>'
        f'<td class="side" valign="bottom" width="92" style="border-left:1px solid #cfd3db;padding-left:12px">{side}</td>'
        f'</tr></table></td></tr>')


def hero(r: dict) -> str:
    m = r.get("market") or {}
    session = r.get("session") or ""
    headline = str(r.get("headline") or "")
    # The clause after the last separator takes the accent colour, like "Better Tomorrow."
    head, sep, tail = headline.rpartition("；")
    head_html = (f'{e(head)}{e(sep)}<br><span style="color:{INDIGO}">{e(tail)}</span>' if sep
                 else e(headline))
    up, down = num(m.get("up")) or 0, num(m.get("down")) or 0
    stats = [
        (m.get("index"), "加權指數", m.get("index_pct"), move_color(m.get("index_change"))),
        (f'{int(up)}:{int(down)}', "漲跌家數", "紅漲 綠跌", GREY),
        (m.get("value"), "成交金額", f'均量 {m.get("value_vs_avg", "")}', GREY),
    ]
    stat_cells = "".join(
        f'<td class="stat-td" width="33%" valign="top" style="padding:0 10px;{"border-left:1px solid " + LINE + ";" if i else ""}">'
        f'<div class="stat" style="font:800 22px/1.2 {DISPLAY};color:{BLACK};white-space:nowrap">{e(big)}</div>'
        f'<div style="font:500 12px/1.5 {SANS};color:{GREY};margin-top:4px">{e(small)}</div>'
        f'<div style="font:700 12px/1.4 {SANS};color:{color}">{e(note)}</div></td>'
        for i, (big, small, note, color) in enumerate(stats))
    summary = "".join(f'<div style="font:400 15px/1.7 {SANS};color:#4b5563;margin-top:6px">{e(s)}</div>'
                      for s in (r.get("summary") or [])[:3])
    link = (r.get("links") or {}).get("drive") or "#"
    return wrap_card(
        f'<table role="presentation" width="100%"><tr><td>'
        f'<span style="font:900 22px/1 {DISPLAY};color:{BLACK}">A</span></td>'
        f'<td align="right">{pill(EDITION_EN.get(session, "DAILY") + " EDITION", "#ffffff", BLACK)}</td>'
        f'</tr></table>'
        f'<div style="margin-top:22px">{pill("LIVE · " + str(r.get("date") or ""), INDIGO, LAVENDER, INDIGO)}</div>'
        f'<div style="margin-top:16px;font:900 34px/1.22 {DISPLAY};color:{BLACK};letter-spacing:-.5px">{head_html}</div>'
        f'{summary}'
        f'<table role="presentation" style="margin-top:22px"><tr><td>{black_button("完整研究資料", link)}</td>'
        f'<td style="padding-left:20px"><a href="{e(link)}" style="font:700 14px/1 {SANS};color:{BLACK};'
        f'text-decoration:underline">潛力股雷達</a></td></tr></table>'
        f'<table role="presentation" width="100%" style="margin-top:28px"><tr>{stat_cells}</tr></table>'
        + side_visual(r), pad="26px 28px 28px")


def side_visual(r: dict) -> str:
    """The reference's photo column, here a lavender panel with floating cards and a handwritten note."""
    themes = r.get("themes") or []
    top = themes[0] if themes else {}
    flows = (r.get("flows") or {}).get("in") or []
    lead = flows[0] if flows else {}
    float_card = (
        f'<table role="presentation" width="100%" style="background-color:#ffffff;border-radius:18px;'
        f'box-shadow:0 10px 30px rgba(79,91,213,.16)"><tr><td style="padding:14px 16px">'
        f'<div style="font:800 15px/1.3 {DISPLAY};color:{BLACK}">{{title}}</div>'
        f'<div style="font:500 12px/1.5 {SANS};color:{GREY}">{{sub}}</div></td>'
        f'<td width="40" align="right" style="padding-right:14px">{arrow_badge()}</td></tr></table>')
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:26px;'
        f'background-color:{LAVENDER};background-image:linear-gradient(135deg,{LAVENDER} 0%,{LAVENDER_2} 100%);'
        f'border-radius:24px"><tr><td style="padding:22px">'
        f'<div style="font:400 22px/1.25 {SCRIPT};color:#3a3f55;transform:rotate(-4deg)">'
        f'Follow the money,<br>not the noise &#8600;</div>'
        f'<div style="height:14px"></div>'
        + float_card.replace("{title}", e(top.get("name", "今日焦點")))
                    .replace("{sub}", "今日最熱題材 · " + e(top.get("forecast", "")))
        + '<div style="height:10px"></div>'
        + float_card.replace("{title}", "資金流入 " + e(lead.get("industry", "")))
                    .replace("{sub}", "成交占比變化 " + e(lead.get("change", "")))
        + '</td></tr></table>')


def flows_card(r: dict) -> str:
    flows = r.get("flows") or {}
    if not (flows.get("in") or flows.get("out")):
        return ""
    items = list(flows.get("in") or []) + list(flows.get("out") or [])
    peak = max((abs(num(x.get("change")) or 0) for x in items), default=1) or 1
    rows = "".join(
        f'<tr><td width="30%" style="padding:7px 0;font:600 13px/1.3 {SANS};color:{INK}">{e(x.get("industry"))}</td>'
        f'<td style="padding:7px 10px">{bar(abs(num(x.get("change")) or 0) / peak, move_color(x.get("change")))}</td>'
        f'<td width="52" align="right" style="font:800 13px/1 {DISPLAY};color:{move_color(x.get("change"))}">'
        f'{e(x.get("change"))}</td></tr>' for x in items)
    glob = ""
    if r.get("global"):
        tiles = [
            f'<td width="50%" valign="top" style="padding:4px"><table role="presentation" width="100%" '
            f'style="background-color:#f7f8fa;border-radius:16px"><tr><td style="padding:12px 14px">'
            f'<div style="font:600 11px/1.3 {SANS};color:{GREY}">{e(g.get("label"))}</div>'
            f'<div style="font:800 18px/1.3 {DISPLAY};color:{move_color(g.get("value"))}">{e(g.get("value"))}</div>'
            f'</td></tr></table></td>' for g in r["global"][:4]]
        cells = "".join(f"<tr>{''.join(tiles[i:i + 2])}</tr>" for i in range(0, len(tiles), 2))
        glob = (f'<div style="margin:22px 0 8px">{label(r.get("global_title") or "隔夜國際盤", INDIGO, 11)}</div>'
                f'<table role="presentation" width="100%">{cells}</table>'
                + (f'<div style="margin-top:12px;font:400 14px/1.7 {SANS};color:#4b5563">{e(r["global_focus"])}</div>'
                   if r.get("global_focus") else ""))
    return wrap_card(section_title("資金流向", "Money Flow", "成交占比 vs 區間平均")
                     + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>'
                     + glob)


THEME_BG = [
    ("#111522", "linear-gradient(135deg,#1a2033 0%,#0b0e17 100%)", "#ffffff", "#aab1c5"),
    ("#e9ebf0", "linear-gradient(135deg,#f4f5f8 0%,#d9dce4 100%)", BLACK, GREY),
    ("#2b2f8f", "linear-gradient(135deg,#3b44c4 0%,#1b1e5e 100%)", "#ffffff", "#c9cdf7"),
]


def themes_card(r: dict) -> str:
    if not r.get("themes"):
        return ""
    blocks = []
    for i, t in enumerate(r["themes"]):
        solid, grad, fg, sub = THEME_BG[i % len(THEME_BG)]
        tag_fg, _, level = LEVELS.get(t.get("forecast", "觀望"), (GREY, "", 3))
        level = int(t.get("heat") or level)
        stocks = "　".join(
            f'{e(s.get("code"))} {e(s.get("name"))} <b style="color:{move_color(s.get("chg")) if fg == BLACK else "#ffffff"}">'
            f'{e(s.get("chg"))}</b>' for s in t.get("stocks") or [])
        cover = (f'<img src="{e(t["image"])}" width="100%" alt="" style="display:block;width:100%;max-height:200px;'
                 f'object-fit:cover;border-radius:20px 20px 0 0">' if str(t.get("image", "")).startswith("https://")
                 else "")
        details = "".join(
            f'<div style="margin-top:12px"><div>{label(k, INDIGO, 10)}</div>'
            f'<div style="font:400 14px/1.7 {SANS};color:#374151">{e(t.get(key))}</div></div>'
            for k, key in (("Why · 為什麼熱", "why"), ("Flows · 法人態度", "institutions"), ("Outlook · 熱度預估", "reason"))
            if t.get(key))
        blocks.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;'
            f'border:1px solid {LINE};border-radius:22px">'
            f'<tr><td style="padding:0;border-radius:22px 22px 0 0;background-color:{solid};background-image:{grad}">'
            f'{cover}<table role="presentation" width="100%"><tr><td style="padding:20px 22px">'
            f'<div style="font:800 20px/1.3 {DISPLAY};color:{fg}">{e(t.get("name"))}</div>'
            f'<div style="margin-top:6px;font:500 12px/1.7 {SANS};color:{sub}">{stocks}</div></td>'
            f'<td width="110" align="right" valign="top" style="padding:20px 22px 0 0">'
            f'{pill(t.get("forecast", "觀望"), tag_fg, "#ffffff")}<div style="height:10px"></div>'
            f'<div style="display:inline-block">{meter(level, "#ffffff" if fg != BLACK else INDIGO)}</div>'
            f'</td></tr></table></td></tr>'
            f'<tr><td style="padding:6px 22px 20px">{details}</td></tr></table>')
    cooling = ""
    if r.get("cooling"):
        cooling = (f'<div style="padding:18px 20px;background-color:#f7f8fa;border-radius:20px">'
                   f'{label("Cooling · 退燒觀察", GREY, 10)}'
                   + "".join(f'<div style="margin-top:8px;font:400 14px/1.6 {SANS};color:#374151">'
                             f'<b style="color:{BLACK}">{e(c.get("name"))}</b>　{e(c.get("note"))}</div>'
                             for c in r["cooling"]) + "</div>")
    return wrap_card(section_title("熱門題材", "Hot Themes", f'{len(r["themes"])} themes') + "".join(blocks) + cooling)


def radar_card(r: dict) -> str:
    if not r.get("radar"):
        return ""
    rows = "".join(
        f'<tr><td width="44" valign="top" style="padding:14px 0;border-bottom:1px solid {LINE};'
        f'font:800 13px/1.6 {DISPLAY};color:{LIGHT}">{i:02d}</td>'
        f'<td valign="top" style="padding:14px 0;border-bottom:1px solid {LINE}">'
        f'<div style="font:800 16px/1.4 {DISPLAY};color:{BLACK}">{e(x.get("name"))}'
        f' <span style="font:600 12px/1 {SANS};color:{LIGHT}">{e(x.get("code"))}</span></div>'
        f'<div style="font:400 13px/1.65 {SANS};color:#4b5563;margin-top:3px">{e(x.get("signal"))}</div></td>'
        f'<td width="44" align="right" valign="middle" style="border-bottom:1px solid {LINE}">{arrow_badge()}</td></tr>'
        for i, x in enumerate(r["radar"], 1))
    return wrap_card(section_title("潛力股雷達", "Radar", "明早深入研究")
                     + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>')


def deep_card(r: dict) -> str:
    if not r.get("deep_dives"):
        return ""
    out = []
    for d in r["deep_dives"]:
        tag_fg, _, _ = LEVELS.get(d.get("priority", "中"), (GREY, "", 3))
        kicker = f'{d.get("market", "")} · {d.get("industry", "")}'
        fields = "".join(
            f'<div style="margin-top:12px">{label(k, INDIGO, 10)}<div style="font:400 14px/1.7 {SANS};'
            f'color:#374151">{e(d.get(key))}</div></div>'
            for k, key in (("Fundamentals · 基本面", "fundamentals"), ("Flows · 籌碼", "chips"),
                           ("Technical · 技術面", "technical"), ("Risk · 主要風險", "risks"),
                           ("Invalidation · 看錯訊號", "wrong_if")) if d.get(key))
        watch = "".join(f'<div style="margin-top:6px;font:400 14px/1.6 {SANS};color:#374151">'
                        f'<b style="color:{INDIGO}">{n:02d}</b>　{e(w)}</div>'
                        for n, w in enumerate(d.get("watch") or [], 1))
        out.append(
            f'<table role="presentation" width="100%" style="margin-bottom:18px;border:1px solid {LINE};'
            f'border-radius:22px"><tr><td style="padding:22px">'
            f'<table role="presentation" width="100%"><tr><td>'
            f'<div>{label(kicker, LIGHT, 10)}</div>'
            f'<div style="font:900 28px/1.2 {DISPLAY};color:{BLACK}">{e(d.get("name"))} '
            f'<span style="font:700 14px/1 {SANS};color:{LIGHT}">{e(d.get("code"))} · {e(d.get("close"))}</span></div>'
            f'</td><td align="right" valign="top">{pill("優先度 " + str(d.get("priority", "")), tag_fg, "#f7f8fa")}'
            f'</td></tr></table>'
            f'<div style="margin-top:12px;font:800 17px/1.5 {DISPLAY};color:{INDIGO}">{e(d.get("highlight"))}</div>'
            + fields
            + f'<table role="presentation" width="100%" style="margin-top:14px"><tr>'
            f'<td width="49%" valign="top" style="padding:14px;background-color:#fdf0ef;border-radius:16px">'
            f'{label("Bull · 看多", UP, 10)}<div style="font:400 13px/1.65 {SANS};color:#374151;margin-top:4px">'
            f'{e(d.get("bull"))}</div></td><td width="2%"></td>'
            f'<td width="49%" valign="top" style="padding:14px;background-color:#ecf8f1;border-radius:16px">'
            f'{label("Bear · 看空", DOWN, 10)}<div style="font:400 13px/1.65 {SANS};color:#374151;margin-top:4px">'
            f'{e(d.get("bear"))}</div></td></tr></table>'
            + (f'<div style="margin-top:14px">{label("Watch · 追蹤訊號", INDIGO, 10)}{watch}</div>' if watch else "")
            + '</td></tr></table>')
    return wrap_card(section_title("潛力股深入研究", "Deep Dive") + "".join(out))


def track_card(r: dict) -> str:
    t = r.get("track") or {}
    if not t.get("rows"):
        return ""
    peak = max((abs(num(x.get("ret")) or 0) for x in t["rows"]), default=1) or 1
    rows = "".join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid {LINE}"><div style="font:800 14px/1.4 {DISPLAY};'
        f'color:{BLACK}">{e(x.get("name", ""))} <span style="color:{LIGHT};font-weight:600">{e(x.get("code"))}</span></div>'
        f'<div style="font:500 11px/1.4 {SANS};color:{LIGHT}">{e(x.get("picked"))} · {e(x.get("then"))} &rarr; {e(x.get("now"))}</div></td>'
        f'<td width="42%" style="padding:10px;border-bottom:1px solid {LINE}">'
        f'{bar(abs(num(x.get("ret")) or 0) / peak, move_color(x.get("ret")))}</td>'
        f'<td width="60" align="right" style="border-bottom:1px solid {LINE};font:800 15px/1 {DISPLAY};'
        f'color:{move_color(x.get("ret"))}">{e(x.get("ret"))}</td></tr>' for x in t["rows"])
    return wrap_card(section_title("過去潛力股追蹤", "Track Record")
                     + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>'
                     + (f'<div style="margin-top:12px;font:400 14px/1.7 {SANS};color:#374151">{e(t["comment"])}</div>'
                        if t.get("comment") else ""))


def footer(r: dict) -> str:
    notes = "".join(f'<div style="margin-top:4px">— {e(w)}</div>' for w in r.get("warnings") or [])
    return (
        f'<tr><td align="center" style="padding:18px 16px 6px"><table role="presentation" style="background-color:'
        f'#ffffff;border-radius:999px;box-shadow:0 12px 34px rgba(30,36,60,.12)"><tr>'
        f'<td style="padding:10px 6px 10px 10px"><span style="display:inline-block;width:34px;height:34px;'
        f'line-height:34px;border-radius:34px;background-color:{BLACK};color:#fff;text-align:center;'
        f'font:800 12px/34px {DISPLAY}">AI</span></td>'
        f'<td class="foot-pill" style="padding:10px 22px 10px 6px;font:800 15px/1 {DISPLAY};color:{BLACK};white-space:nowrap">'
        f'Taiwan Equity AI Desk&nbsp;&nbsp;·&nbsp;&nbsp;{e(r.get("session"))}</td></tr></table></td></tr>'
        f'<tr><td style="padding:16px 30px 34px;font:400 12px/1.8 {SANS};color:{GREY}">'
        + (f'{label("Editor notes", INK, 10)}{notes}<div style="height:10px"></div>' if notes else "")
        + '本報由 AI 研究團隊整理公開資料自動產生，僅供資訊參考，不構成投資建議。紅色為上漲、綠色為下跌。</td></tr>')


def render(r: dict) -> str:
    body = (masthead(r) + hero(r) + flows_card(r) + themes_card(r) + radar_card(r) + deep_card(r)
            + track_card(r) + footer(r))
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="light only"><title>{e(r.get("title"))}</title>'
            f'<style>@media only screen and (max-width:480px){{.mast{{font-size:54px!important;letter-spacing:-2px!important}}'
            f'.pill-o{{width:46px!important;height:18px!important;border-width:8px!important}}'
            f'.side{{display:none!important}}.stat{{font-size:16px!important;white-space:normal!important}}.stat-td{{padding:0 5px!important}}'
            f'.card-pad{{padding:22px 16px!important}}.card-out{{padding:8px 6px!important}}'
            f'.foot-pill{{font-size:12px!important;padding-right:14px!important}}}}</style></head>'
            f'<body style="margin:0;padding:0;{PAGE}"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" style="{PAGE}"><tr><td align="center" style="padding:10px 4px">'
            f'<table role="presentation" width="680" cellpadding="0" cellspacing="0" style="max-width:680px;'
            f'width:100%">{body}</table></td></tr></table></body></html>')


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
