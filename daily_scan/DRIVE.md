# Google Drive 存放規則（所有 Agent 共用）

根資料夾：`台股AI研究室`（ID `17zjLfUnspfbT3pbOA9nk9elyfeo88kMH`）

| 資料夾 | ID | 放什麼 | 誰寫入 |
|---|---|---|---|
| 00_每日總報告 | `17sdGXXFBx-MWkMdLTTe8dmbOTj6mpG3A` | 三份定時總報告（和 Gmail 寄出的同一份） | 總編輯 |
| 01_原始資料 | `1FQcsQdFdPjGOYuel-Jw3t5tJI12HT-f0` | 每次掃描的資料包 | 總編輯 |
| 02_分析師報告 | `15FX5zW7XnADW6YsKsO8EhclndHFGFSso` | 每個分析師 Agent 每次的工作成果 | 各分析師 |
| 03_個股研究檔案 | `1twpv6GTIYJ1wfRbpqINYNqcnZ7oHaM5U` | 每檔深入研究過的股票，一次一份，持續累積 | 個股研究員 |
| 04_追蹤紀錄 | `1OuJB9k5vcHSP-guDbl-seybMo7U_720w` | 每天挑出的潛力股清單 | 總編輯 |
| 99_系統設定 | `1WUbn5Hta9AKHFZw49UP3TQivG6rHNzsT` | 說明文件（人看的，Agent 不寫入） | — |

## 檔名規則（讓 Agent 用標題搜尋就找得到）

- 時段代碼：`早盤`（詳細報告）、`收盤`、`晚間`
- 00：`YYYY-MM-DD_時段_總報告`
- 01：`YYYY-MM-DD_時段_資料包`
- 02：`YYYY-MM-DD_時段_角色名`，例如 `2026-11-03_收盤_熱度分析師`
- 03：`代號_名稱_YYYY-MM-DD`，例如 `3227_原相_2026-11-03`
- 04：`YYYY-MM-DD_潛力股`

## 寫入方式

- 一律用 Google Drive `create_file`，`parentId` 填上表的資料夾 ID。
- 文字報告：`textContent` 放內容，`contentMimeType` 用 `text/plain`（會轉成 Google 文件，之後可用 `read_file_content` 讀）。
- 總報告：`textContent` 放渲染好的 HTML，`contentMimeType` 用 `text/html`。
- 04 潛力股清單：`contentMimeType` 用 `text/csv`（會轉成試算表），欄位 `代號,名稱,市場,選出日,當時收盤,研究優先度,一句話理由`。
- **只新增、不修改舊檔**。同名檔已存在也照樣新增。

## 讀取方式

- 找檔：`search_files`，例如 `parentId = '15FX5zW7XnADW6YsKsO8EhclndHFGFSso' and title contains '熱度分析師'`，依標題日期挑最近的。
- 讀檔：`read_file_content`（Google 文件、試算表都可以）。
- 讀不到（剛開始使用、還沒有舊檔）就略過，在報告裡註明「尚無歷史資料」。
