"""Render a report (JSON written by the editor agent) as a designed HTML email.

    python -m daily_scan.render_email report.json > report.html

An electronic-newspaper layout on frosted-glass panels: serif headlines, a
masthead and section rules carry the hierarchy (no emoji), and the dashboard
keeps its charts as table-cell bars. Email clients drop <style> blocks,
backdrop-filter and SVG, so everything is tables with inline styles; the glass
is translucent white over a soft gradient, with a solid fallback colour for
clients that ignore gradients. Taiwan colours: red is up, green is down. Every
text field is escaped; the JSON schema is documented in PROMPT_full.md.
"""

from __future__ import annotations

import json
import re
import sys
from html import escape

INK, SOFT, MUTED = "#16202c", "#3d4a5a", "#6c7a8b"
RULE = "rgba(22,32,44,.14)"
UP, DOWN, NEUTRAL = "#d43f3f", "#17935a", "#7b8794"
ACCENT = "#1d3a6e"
WALL = ("background-color:#e9eef5;"
        "background-image:linear-gradient(160deg,#dbe6f4 0%,#f3e8ef 45%,#e6f0ea 100%);")
GLASS = ("background-color:rgba(255,255,255,.62);border:1px solid rgba(255,255,255,.85);"
         "border-radius:22px;box-shadow:0 8px 30px rgba(29,58,110,.10),inset 0 1px 0 rgba(255,255,255,.9);")
GLASS_TINT = ("background-color:rgba(255,255,255,.45);border:1px solid rgba(255,255,255,.7);"
              "border-radius:16px;")
SERIF = "'Noto Serif TC','Songti TC','Source Han Serif TC','PMingLiU',Georgia,serif"
SANS = "'PingFang TC','Noto Sans TC','Microsoft JhengHei','Helvetica Neue',Arial,sans-serif"
NUM = "'SF Pro Display','Helvetica Neue','Segoe UI',Arial,sans-serif"
LEVELS = {  # label -> (text colour, tint, meter level 1-5)
    "延續": ("#b4232a", "rgba(212,63,63,.12)", 5), "觀望": ("#9a5b00", "rgba(214,150,30,.14)", 3),
    "可能退燒": ("#1f5fa8", "rgba(31,95,168,.12)", 1),
    "高": ("#b4232a", "rgba(212,63,63,.12)", 5), "中": ("#9a5b00", "rgba(214,150,30,.14)", 3),
    "低": ("#4b5868", "rgba(75,88,104,.12)", 1),
}
EDITIONS = {"每日詳細報告": "晨報", "收盤快報": "收盤快報", "晚間快報": "晚間快報"}


def e(value) -> str:
    return escape(str(value if value is not None else ""))


def num(text) -> float | None:
    m = re.search(r"[-+−]?\d[\d,]*\.?\d*", str(text))
    return float(m.group(0).replace(",", "").replace("−", "-")) if m else None


def move_color(text) -> str:
    s = str(text).strip()
    return UP if s.startswith("+") else DOWN if s.startswith(("-", "−")) else INK


def tag(label: str) -> str:
    fg, bg, _ = LEVELS.get(label, (SOFT, "rgba(75,88,104,.12)", 3))
    return (f'<span style="display:inline-block;padding:3px 12px;border-radius:999px;background-color:{bg};'
            f'color:{fg};font:700 12px/1.4 {SANS};letter-spacing:1px;white-space:nowrap">{e(label)}</span>')


def meter(level: int, color: str) -> str:
    """Five segments, the first ``level`` filled: the heat or priority at a glance."""
    cells = "".join(
        f'<td width="18%" style="height:6px;border-radius:3px;background-color:'
        f'{color if i < level else "rgba(22,32,44,.10)"}"></td><td width="2%"></td>' for i in range(5))
    return f'<table role="presentation" width="120" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table>'


def bar(fraction: float, color: str, height: int = 8) -> str:
    pct = max(2, min(100, round(fraction * 100)))
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="{pct}%" style="height:{height}px;border-radius:{height}px;background-color:{color}"></td>'
            f'<td width="{100 - pct}%" style="height:{height}px"></td></tr></table>')


def panel(inner: str, pad: str = "22px 24px") -> str:
    return (f'<tr><td style="padding:10px 14px"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" style="{GLASS}"><tr><td style="padding:{pad}">{inner}</td></tr></table></td></tr>')


def section_head(english: str, chinese: str) -> str:
    return (f'<div style="font:700 11px/1 {SANS};letter-spacing:3px;color:{MUTED}">{e(english)}</div>'
            f'<div style="font:900 24px/1.25 {SERIF};color:{INK};margin:6px 0 10px">{e(chinese)}</div>'
            f'<div style="height:2px;background-color:{INK};margin-bottom:2px"></div>'
            f'<div style="height:1px;background-color:{RULE};margin-bottom:14px"></div>')


def field(label: str, text) -> str:
    if not text:
        return ""
    return (f'<div style="margin-top:10px;font:400 14px/1.75 {SANS};color:{SOFT}">'
            f'<span style="font:700 12px/1 {SANS};letter-spacing:2px;color:{ACCENT}">{e(label)}</span>'
            f'<br>{e(text)}</div>')


def image(src: str | None, credit: str | None) -> str:
    if not src or not str(src).startswith("https://"):
        return ""
    return (f'<img src="{e(src)}" width="100%" alt="" style="display:block;width:100%;max-height:240px;'
            f'object-fit:cover;border-radius:14px;margin-bottom:10px">'
            f'<div style="font:400 11px/1.4 {SANS};color:{MUTED};margin:-4px 0 10px">圖片來源：{e(credit)}</div>')


def masthead(r: dict) -> str:
    edition = EDITIONS.get(r.get("session"), r.get("session") or "報告")
    return panel(
        f'<table role="presentation" width="100%"><tr>'
        f'<td style="font:700 11px/1 {SANS};letter-spacing:3px;color:{MUTED}">TAIWAN EQUITY AI DESK</td>'
        f'<td align="right" style="font:700 11px/1 {SANS};letter-spacing:2px;color:{MUTED}">{e(r.get("date"))}</td>'
        f'</tr></table>'
        f'<div style="height:2px;background-color:{INK};margin:12px 0 2px"></div>'
        f'<div style="height:1px;background-color:{INK};margin-bottom:14px"></div>'
        f'<div style="text-align:center;font:900 44px/1.1 {SERIF};color:{INK};letter-spacing:6px">台股 AI {e(edition)}</div>'
        f'<div style="text-align:center;font:400 12px/1 {SANS};color:{MUTED};letter-spacing:4px;margin-top:10px">'
        f'全市場掃描　·　熱度追蹤　·　潛力股雷達</div>'
        f'<div style="height:1px;background-color:{INK};margin:14px 0 2px"></div>'
        f'<div style="height:2px;background-color:{INK};margin-bottom:18px"></div>'
        f'<div style="font:900 28px/1.35 {SERIF};color:{INK}">{e(r.get("headline"))}</div>'
        + "".join(f'<div style="margin-top:10px;font:400 16px/1.7 {SERIF};color:{SOFT}">'
                  f'<span style="font:700 13px/1 {NUM};color:{ACCENT};margin-right:8px">{i:02d}</span>{e(s)}</div>'
                  for i, s in enumerate(r.get("summary") or [], 1)),
        pad="20px 26px 24px")


def dashboard(r: dict) -> str:
    m = r.get("market") or {}
    if not m:
        return ""
    up, down = num(m.get("up")) or 0, num(m.get("down")) or 0
    ratio = num(m.get("value_vs_avg")) or 0

    def tile(label, big, small, color=INK, extra=""):
        return (f'<td width="33%" valign="top" style="padding:5px"><table role="presentation" width="100%" '
                f'style="{GLASS_TINT}"><tr><td style="padding:14px">'
                f'<div style="font:700 11px/1 {SANS};letter-spacing:2px;color:{MUTED}">{e(label)}</div>'
                f'<div style="font:700 26px/1.2 {NUM};color:{INK};margin:8px 0 4px">{e(big)}</div>'
                f'<div style="font:600 12px/1.3 {NUM};color:{color}">{e(small)}</div>{extra}</td></tr></table></td>')
    breadth = (f'<div style="margin-top:10px"><table role="presentation" width="100%" cellpadding="0" '
               f'cellspacing="0"><tr><td width="{max(2, round(up / ((up + down) or 1) * 100))}%" '
               f'style="height:6px;background-color:{UP};border-radius:6px 0 0 6px"></td>'
               f'<td style="height:6px;background-color:{DOWN};border-radius:0 6px 6px 0"></td></tr></table></div>')
    volume = f'<div style="margin-top:10px">{bar(min(ratio / 2, 1), ACCENT, 6)}</div>'
    tiles = (tile("加權指數", m.get("index"), f'{m.get("index_change", "")}　{m.get("index_pct", "")}',
                  move_color(m.get("index_change")))
             + tile("漲跌家數", f'{int(up)} : {int(down)}', "紅漲　綠跌", MUTED, breadth)
             + tile("成交金額", m.get("value"), f'為均量 {m.get("value_vs_avg", "")}', MUTED, volume))
    body = (section_head("MARKET DASHBOARD", "盤勢儀表板")
            + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{tiles}</tr></table>')

    if r.get("global"):
        cells = "".join(
            f'<td valign="top" style="padding:5px"><table role="presentation" width="100%" style="{GLASS_TINT}">'
            f'<tr><td style="padding:10px 12px"><div style="font:600 11px/1.3 {SANS};color:{MUTED}">{e(g.get("label"))}'
            f'</div><div style="font:700 18px/1.3 {NUM};color:{move_color(g.get("value"))}">{e(g.get("value"))}</div>'
            f'</td></tr></table></td>' for g in r["global"][:4])
        body += (f'<div style="font:700 13px/1 {SANS};letter-spacing:2px;color:{ACCENT};margin:16px 0 6px">'
                 f'隔夜國際盤</div><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
                 f'<tr>{cells}</tr></table>'
                 + (f'<div style="margin-top:10px;font:400 15px/1.7 {SERIF};color:{SOFT}">{e(r["global_focus"])}</div>'
                    if r.get("global_focus") else ""))

    flows = r.get("flows") or {}
    if flows.get("in") or flows.get("out"):
        items = list(flows.get("in") or []) + list(flows.get("out") or [])
        peak = max((abs(num(x.get("change")) or 0) for x in items), default=1) or 1

        def rows(entries, color):
            return "".join(
                f'<tr><td width="34%" style="padding:5px 0;font:500 13px/1.3 {SANS};color:{SOFT}">'
                f'{e(x.get("industry"))}</td><td style="padding:5px 8px">'
                f'{bar(abs(num(x.get("change")) or 0) / peak, color)}</td>'
                f'<td width="56" align="right" style="font:700 13px/1 {NUM};color:{color}">{e(x.get("change"))}</td></tr>'
                for x in entries or [])
        body += (f'<div style="font:700 13px/1 {SANS};letter-spacing:2px;color:{ACCENT};margin:18px 0 6px">'
                 f'產業資金流向（成交占比變化）</div><table role="presentation" width="100%" cellpadding="0" '
                 f'cellspacing="0">{rows(flows.get("in"), UP)}{rows(flows.get("out"), DOWN)}</table>')
    return panel(body)


def themes(r: dict) -> str:
    if not r.get("themes") and not r.get("cooling"):
        return ""
    out = section_head("HOT THEMES", "熱門題材")
    for i, t in enumerate(r.get("themes") or []):
        fg, _, level = LEVELS.get(t.get("forecast", "觀望"), (SOFT, "", 3))
        level = int(t.get("heat") or level)
        chips = "".join(
            f'<span style="display:inline-block;margin:6px 8px 0 0;font:500 13px/1.6 {SANS};color:{SOFT}">'
            f'{e(s.get("code"))} {e(s.get("name"))} <b style="font-family:{NUM};color:{move_color(s.get("chg"))}">'
            f'{e(s.get("chg"))}</b></span>' for s in t.get("stocks") or [])
        out += (
            (f'<div style="height:1px;background-color:{RULE};margin:18px 0"></div>' if i else "")
            + image(t.get("image"), t.get("image_credit"))
            + f'<table role="presentation" width="100%"><tr><td valign="top">'
            f'<div style="font:900 21px/1.35 {SERIF};color:{INK}">{e(t.get("name"))}</div></td>'
            f'<td align="right" valign="top" width="130">{tag(t.get("forecast", "觀望"))}'
            f'<div style="margin-top:8px">{meter(level, fg)}</div></td></tr></table>'
            + f'<div>{chips}</div>'
            + field("為什麼熱", t.get("why")) + field("法人態度", t.get("institutions"))
            + field("熱度預估", t.get("reason")))
    if r.get("cooling"):
        out += (f'<div style="margin-top:22px;padding:14px 16px;{GLASS_TINT}">'
                f'<div style="font:700 13px/1 {SANS};letter-spacing:2px;color:#1f5fa8">退燒觀察</div>'
                + "".join(f'<div style="margin-top:8px;font:400 14px/1.7 {SANS};color:{SOFT}">'
                          f'<b style="font-family:{SERIF};color:{INK}">{e(c.get("name"))}</b>　{e(c.get("note"))}</div>'
                          for c in r["cooling"]) + "</div>")
    return panel(out)


def radar(r: dict) -> str:
    if not r.get("radar"):
        return ""
    rows = "".join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid {RULE};font:700 15px/1.4 {SERIF};color:{INK};'
        f'white-space:nowrap" valign="top">{e(x.get("code"))} {e(x.get("name"))}</td>'
        f'<td style="padding:10px 0 10px 14px;border-bottom:1px solid {RULE};font:400 14px/1.6 {SANS};color:{SOFT}">'
        f'{e(x.get("signal"))}</td></tr>' for x in r["radar"])
    return panel(section_head("RADAR", "潛力股雷達（明早深入研究）")
                 + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>')


def deep_dives(r: dict) -> str:
    if not r.get("deep_dives"):
        return ""
    out = section_head("DEEP DIVE", "潛力股深入研究")
    for i, d in enumerate(r["deep_dives"]):
        fg, _, level = LEVELS.get(d.get("priority", "中"), (SOFT, "", 3))
        watch = "".join(f'<div style="margin-top:6px;font:400 14px/1.6 {SANS};color:{SOFT}">'
                        f'<span style="font:700 12px/1 {NUM};color:{ACCENT};margin-right:8px">{n:02d}</span>{e(w)}</div>'
                        for n, w in enumerate(d.get("watch") or [], 1))
        out += (
            (f'<div style="height:2px;background-color:{INK};margin:26px 0 2px"></div>'
             f'<div style="height:1px;background-color:{RULE};margin-bottom:18px"></div>' if i else "")
            + image(d.get("image"), d.get("image_credit"))
            + f'<div style="font:700 11px/1 {SANS};letter-spacing:2px;color:{MUTED}">'
            f'{e(d.get("market"))}　·　{e(d.get("industry"))}　·　收盤 {e(d.get("close"))}</div>'
            f'<table role="presentation" width="100%" style="margin-top:6px"><tr><td valign="top">'
            f'<span style="font:900 26px/1.3 {SERIF};color:{INK}">{e(d.get("name"))}</span>'
            f'<span style="font:700 16px/1 {NUM};color:{MUTED};margin-left:8px">{e(d.get("code"))}</span></td>'
            f'<td align="right" valign="top" width="130"><div style="font:700 11px/1 {SANS};letter-spacing:2px;'
            f'color:{MUTED};margin-bottom:6px">研究優先度</div>{tag(d.get("priority", "中"))}'
            f'<div style="margin-top:8px">{meter(level, fg)}</div></td></tr></table>'
            f'<div style="margin:14px 0 4px;padding:4px 0 4px 16px;border-left:3px solid {ACCENT};'
            f'font:700 18px/1.6 {SERIF};color:{INK}">{e(d.get("highlight"))}</div>'
            + field("基本面", d.get("fundamentals")) + field("籌碼", d.get("chips"))
            + field("技術面", d.get("technical"))
            + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:14px">'
            f'<tr><td width="49%" valign="top" style="padding:12px 14px;background-color:rgba(212,63,63,.08);'
            f'border-radius:14px"><div style="font:900 15px/1 {SERIF};color:{UP}">看多論點</div>'
            f'<div style="margin-top:8px;font:400 13px/1.7 {SANS};color:{SOFT}">{e(d.get("bull"))}</div></td>'
            f'<td width="2%"></td><td width="49%" valign="top" style="padding:12px 14px;'
            f'background-color:rgba(23,147,90,.08);border-radius:14px"><div style="font:900 15px/1 {SERIF};'
            f'color:{DOWN}">看空論點</div><div style="margin-top:8px;font:400 13px/1.7 {SANS};color:{SOFT}">'
            f'{e(d.get("bear"))}</div></td></tr></table>'
            + field("主要風險", d.get("risks")) + field("看錯訊號", d.get("wrong_if"))
            + (f'<div style="margin-top:12px;font:700 12px/1 {SANS};letter-spacing:2px;color:{ACCENT}">追蹤訊號</div>'
               + watch if watch else ""))
    return panel(out)


def track(r: dict) -> str:
    t = r.get("track") or {}
    if not t.get("rows"):
        return ""
    peak = max((abs(num(x.get("ret")) or 0) for x in t["rows"]), default=1) or 1
    rows = "".join(
        f'<tr><td style="padding:9px 0;border-bottom:1px solid {RULE};font:700 14px/1.3 {SERIF};color:{INK}">'
        f'{e(x.get("code"))} {e(x.get("name", ""))}<div style="font:400 11px/1.4 {NUM};color:{MUTED}">'
        f'{e(x.get("picked"))}　{e(x.get("then"))} → {e(x.get("now"))}</div></td>'
        f'<td width="40%" style="padding:9px 10px;border-bottom:1px solid {RULE}">'
        f'{bar(abs(num(x.get("ret")) or 0) / peak, move_color(x.get("ret")))}</td>'
        f'<td width="64" align="right" style="border-bottom:1px solid {RULE};font:700 15px/1 {NUM};'
        f'color:{move_color(x.get("ret"))}">{e(x.get("ret"))}</td></tr>' for x in t["rows"])
    return panel(section_head("TRACK RECORD", "過去潛力股追蹤")
                 + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>'
                 + field("檢討", t.get("comment")))


def footer(r: dict) -> str:
    warnings = "".join(f'<div style="margin-top:4px">— {e(w)}</div>' for w in r.get("warnings") or [])
    link = (r.get("links") or {}).get("drive")
    return (f'<tr><td style="padding:10px 30px 30px;font:400 12px/1.8 {SANS};color:{MUTED}">'
            + (f'<div style="font:700 11px/1 {SANS};letter-spacing:2px;color:{SOFT};margin-bottom:4px">編輯附註</div>'
               f'{warnings}<div style="height:10px"></div>' if warnings else "")
            + (f'完整資料與各分析師報告：<a href="{e(link)}" style="color:{ACCENT}">Google Drive</a><br>' if link else "")
            + '本報由 AI 研究團隊整理公開資料自動產生，僅供資訊參考，不構成投資建議。紅色為上漲、綠色為下跌。'
              '</td></tr>')


def render(r: dict) -> str:
    body = (masthead(r) + dashboard(r) + themes(r) + radar(r) + deep_dives(r) + track(r) + footer(r))
    return (
        f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="color-scheme" content="light only"><title>{e(r.get("title"))}</title></head>'
        f'<body style="margin:0;padding:0;{WALL}">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{WALL}">'
        f'<tr><td align="center" style="padding:18px 6px">'
        f'<table role="presentation" width="660" cellpadding="0" cellspacing="0" '
        f'style="max-width:660px;width:100%;font-family:{SANS}">{body}</table>'
        f'</td></tr></table></body></html>')


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
