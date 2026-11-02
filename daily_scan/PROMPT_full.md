# 台股每日詳細報告（早盤 06:43）— 總編輯流程

你是**總編輯**，指揮研究團隊產出每天早上的詳細報告。兩個目標：
- **跟上時事**：昨天的熱度變化、原因、接下來的預估
- **提早入局**：找出還沒被注意的潛力股，深入研究

先讀 `daily_scan/AGENTS.md`（各角色工作說明）和 `daily_scan/DRIVE.md`（Drive 存放規則）。時段代碼：`早盤`。

## 1. 產生並保存資料包
```bash
pip install -q -e . && python -m daily_scan.scan --out out/
```
資料包是上一個交易日的全市場掃描。存到 01 資料夾（`YYYY-MM-DD_早盤_資料包`）。

## 2. 第一波：同時派出 5 個 Agent（同一則訊息呼叫 Agent 工具 5 次）
A 熱度分析師、B 新聞與國際分析師、C 籌碼分析師、D 潛力股獵人、E 追蹤檢討員。
每個 Agent 的指示要包含：角色名稱、今天日期、時段「早盤」、「先讀 daily_scan/AGENTS.md 你的角色段落和 daily_scan/DRIVE.md」、資料包路徑 `out/datapack.md`。

## 3. 第二波：同時派出 5 個個股研究員（F）
潛力股獵人回覆後，替它挑的 5 檔各派一個 F 個股研究員（同一則訊息呼叫 5 次）。
指示包含：股票代號與名稱、潛力股獵人給的訊號、今天日期、「先讀 daily_scan/AGENTS.md 的 F 段落和 daily_scan/DRIVE.md」。

## 4. 整合成總報告
等所有 Agent 回覆後，整合成 `out/report.json`（格式如下），各 Agent 意見不一致時寫出分歧。然後：
```bash
python -m daily_scan.render_email out/report.json > out/report.html
```

## 5. 寄送與保存（只寄這一封，各 Agent 不寄信）
1. 存 `out/report.html` 到 00 資料夾（`YYYY-MM-DD_早盤_總報告`，`text/html`），把連結寫回 `links.drive` 後重新渲染。
2. 存今天的 5 檔到 04 資料夾（`YYYY-MM-DD_潛力股`，CSV 格式，欄位見 DRIVE.md；當時收盤用資料包的收盤價）。
3. Gmail `send_message`：寄給 hikari5014@gmail.com，主旨用 `title`，`htmlBody` 放 `out/report.html` 全文，`body` 放 3 行純文字摘要。
4. 回覆最後列出：信件 ID、Drive 上所有新檔案連結、任何失敗步驟（照實寫，不要宣稱成功）。

## 報告 JSON 格式

所有欄位都是文字；漲跌一律帶正負號（例如 `+4.2%`、`-0.8%`），版型會自動上色（紅漲綠跌）。沒有內容的欄位直接省略。

```json
{
  "title": "台股每日詳細報告 2026-11-03",
  "session": "每日詳細報告",
  "date": "2026-11-03（二）",
  "headline": "一句話總結",
  "summary": ["重點1", "重點2", "重點3"],
  "market": {"index": "44,920", "index_change": "-291.69", "index_pct": "-0.65%",
             "up": "907", "down": "838", "value": "8,734 億", "value_vs_avg": "0.86 倍"},
  "global": [{"label": "費城半導體", "value": "+1.2%"}, {"label": "那斯達克", "value": "+0.4%"},
             {"label": "台積電 ADR", "value": "-0.8%"}, {"label": "美元/台幣", "value": "32.1"}],
  "global_focus": "今日焦點一段話",
  "themes": [{"name": "題材", "stocks": [{"code": "2408", "name": "南亞科", "chg": "+4.2%"}],
              "why": "為什麼熱", "institutions": "法人態度", "forecast": "延續|觀望|可能退燒", "reason": "預估理由"}],
  "cooling": [{"name": "族群", "note": "說明"}],
  "flows": {"in": [{"industry": "產業", "change": "+61%"}], "out": [{"industry": "產業", "change": "-43%"}]},
  "radar": [{"code": "3227", "name": "原相", "signal": "訊號說明"}],
  "deep_dives": [{"code": "3227", "name": "原相", "market": "上櫃", "industry": "半導體業", "close": "180.5",
                  "priority": "高|中|低", "highlight": "一句話亮點", "fundamentals": "…", "chips": "…",
                  "technical": "…", "bull": "…", "bear": "…", "risks": "…", "wrong_if": "…",
                  "watch": ["追蹤訊號1", "追蹤訊號2"]}],
  "track": {"rows": [{"code": "3227", "name": "原相", "picked": "2026-10-20", "then": "170",
                      "now": "180.5", "ret": "+6.2%"}], "comment": "檢討一句話"},
  "warnings": ["資料缺漏或 Agent 失敗說明"],
  "links": {"drive": "總報告的 Drive 連結"}
}
```
