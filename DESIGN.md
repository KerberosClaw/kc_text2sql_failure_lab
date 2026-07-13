# DESIGN — Text-to-SQL Failure Lab

> **Summary (EN):** Build spec for a semantic failure lab: YAML-specified failure cases graded at the result level against a seeded SQLite database whose traps are baked into the data. Two built-in mocks (naive/oracle) self-validate the grader. One OpenAI-compatible provider interface covers cloud and local models. A no-build static gallery renders cases and red/green model scorecards. MVP = 6 cases across 6 trap categories, mock-only CI, English-first docs with zh-TW versions.

以下為完整設計（中文）。

---

## 1. 定位

**Executable ≠ Correct — 語意失敗實驗室。**

不做「又一個 Text-to-SQL 框架」（Vanna / DB-GPT / Dataherald 已佔滿該賽道），做的是那些框架不展示的東西：SQL 可以正常執行、答案仍然語意錯誤的可重現案例集，加上一套「先驗證自己、再評模型」的判分器。

核心主張一句話：**護欄能讓 SQL 安全地執行，不能讓它表達正確的意思 — 確定性工程有明確的停止線，線後是模型能力的事。**

## 2. 案例規格（整個 repo 的靈魂）

一案例一 YAML，`cases/<id>.yaml`：

```yaml
id: null_bucket_ranking          # snake_case，唯一
category: null-semantics         # taxonomy 標籤（見 §3）
title: "Top customers ranking swallowed by a NULL bucket"
question: >                      # 交給模型的自然語言問題（含消歧句）
  Who are the top 10 customers by number of orders?
  Individual buyers (no company name) should appear under their personal name.
ambiguity_resolution: >          # 無歧義規格：這題「對」的定義為什麼是唯一的
  Ranking counts distinct orders per customer entity. Individuals are
  ranked by personal name, never merged into one bucket.
hidden_trap: >                   # 陷阱說明（人讀）
  company_name is NULL for individual buyers. GROUP BY company_name
  merges all individuals into a single NULL row that ranks top-3.
naive_sql: |                     # 看似合理、會踩雷的 SQL（可執行）
  SELECT company_name, COUNT(DISTINCT order_id) AS cnt
  FROM customers JOIN orders USING (customer_id)
  GROUP BY company_name ORDER BY cnt DESC LIMIT 10
oracle:                          # 結果級標準答案
  sql: |                         # 產生 oracle 結果用（僅供重建，不做字串比對）
    ...
  grading: ordered-set           # ordered-set | set | scalar（浮點容差 1e-6）
failure_modes: [wrong-result]    # 此案例預期的失敗形態
```

**判分鐵則：比結果、不比 SQL 字串。** 同題多解，gold SQL 不可靠；oracle 是結果集（排序正規化、浮點容差）。失敗分類：`wrong-result` / `exec-error` / `refused` / `out-of-scope`。

## 3. 陷阱分類學（taxonomy v0）

| 類別 | 陷阱一句話 | MVP |
|---|---|---|
| `null-semantics` | NULL 在 GROUP BY／聚合裡被聚成一組或被靜默丟棄 | ✅ |
| `join-fanout` | 一對多 JOIN 展開後 COUNT/SUM 灌水 | ✅ |
| `growth-definition` | 「成長最多」沒定義絕對值 vs 百分比，兩種答案不同 | ✅ |
| `top-n-ties` | Top-N 邊界平手，LIMIT 靜默砍人 | ✅ |
| `empty-vs-zero` | 沒有資料列 ≠ 值為零，缺席實體從統計裡消失 | ✅ |
| `missing-period` | 時間序列缺月／缺期，趨勢與平均被扭曲 | ✅ |
| `entity-semantics` | 實體型別欄被忽略 —「姓名非空」不等於「個人」 | ✅ |
| `value-domain` | enum 代碼／值域字面靠猜 — 0 列偽裝成「查無資料」 | ✅ |
| `scope-predicate` | 範圍限定詞無乾淨欄位可對應，模型省略整段過濾、退化成全體統計 | ✅ |
| `aggregation-grain` | 聚合粒度錯置（訂單級 vs 明細級） | v2 |
| `time-boundary` | 半開區間 vs 閉區間、時區、年界 | v2 |
| `unit-confusion` | 金額含稅／未稅、幣別、單位 | v2 |
| `nl-ambiguity` | 問題本身多解 — 展示「先消歧再評分」的必要性 | v2 |

Taxonomy 開放擴充（歡迎 PR 的設計），數量不固定。

## 4. 示範資料庫

- **不是附一顆 db，是附生成器**：`src/failure_lab/db_gen.py`，固定 seed、deterministic，`make db` 任何機器重建同一顆 `demo.db`（SQLite）。
- Schema：小型電商 — `customers`（含 company_name 可 NULL 的個人買家）／`orders`／`order_items`／`products`／`categories`。
- **陷阱埋進資料**：每個 case 的觸發條件由生成器保證存在（個人買家數量足以擠進排行、某兩類別成長平手、某月零訂單、多品項訂單製造 fan-out…）。生成器內以註解標明每個陷阱對應的 case id — 資料可稽核。

## 5. 執行器與供應介面

```
providers:
  mock-naive    # 內建：回 cases/*.yaml 的 naive_sql — 全紅
  mock-oracle   # 內建：回 oracle 結果 — 全綠
  openai-compat # 唯一真模型介面：base_url + api_key + model
                # （雲端 API 與本地 Ollama /v1 通吃）
```

- 判分器自驗：CI 斷言 `mock-naive` 全 fail、`mock-oracle` 全 pass — 評測先評自己。
- 真模型跑分紀錄完整 metadata：model id、prompt hash、重跑次數、溫度設定 — 可信評測的最低配備。
- CI 只跑 mock（零 secret、零成本、deterministic）。

## 6. 安全層（教學定位，不裝產品）

示範性最小護欄：SELECT-only、單語句、SQLite `ATTACH`/`PRAGMA` 封鎖、逾時與列數上限。搭配 `SECURITY.md` 威脅模型**明講能防什麼、不能防什麼** — 「安全可執行」與「語意正確」是兩回事，本 repo 的主題正是後者。

## 7. 靜態展廊（web/，無建置工具鏈）

- Vanilla JS ＋ 預先產出的 JSON（eval runner 輸出 = 單一事實源），無後端。
- 三個視圖：**案例牆**（卡片＋分類 badge）→ **案例頁**（問題 → 陷阱 → naive SQL → 紅綠結果 diff）→ **模型成績單**（模型 × 案例的紅綠矩陣 — 對外傳播的主視覺）。
- 本機 `python -m http.server` 即看；GitHub Pages 於公開發佈時啟用。

## 8. 文件（英文摘要＋中文內容，README 除外）

1. `docs/01_security_boundary.md` — 威脅模型、最小權限、護欄的停止線
2. `docs/02_failure_atlas.md` — 語意失敗圖鑑（由 cases/ 自動生成索引）
3. `docs/03_trustworthy_eval.md` — 結果級 oracle、消歧規格、mock 自驗、metadata

## 9. 里程碑

| 里程碑 | 內容 | 驗收 |
|---|---|---|
| M1 骨架 | 本設計、case schema、README | ✅ 完成 |
| M2 核心 | db_gen ＋ 9 案例 ＋ grader ＋ 雙 mock（provider 環境變數：`FLAB_BASE_URL/API_KEY/MODEL/REASONING_EFFORT`） | ✅ CI 綠：naive 全紅、oracle 全綠（16 tests） |
| M3 真模型 | openai-compat ＋ cli（codex／claude -p）provider ＋ 報告 JSON | ✅ 雲端 gpt-5.x（原 8 家族）＋ gpt-5.6-sol 經 codex CLI 全 9 案實跑 |
| M4 展廊 | web/ 三視圖 | ✅ 瀏覽器實測（案例牆／案例頁／成績單矩陣） |
| M5 內容 | 文件三篇、SECURITY、zh 版、README 定稿 | ✅ 完成 |
| M6 公開 | 乾淨歷史重發 public、啟 Pages | ⏳ 發佈 gate（另冊管理）全勾後執行 |

## 10. 技術基線

Python 3.12+，依賴僅 `pyyaml`（其餘 stdlib：sqlite3/json/argparse）。`pytest`＋`ruff`。Makefile：`db` / `eval` / `gallery` / `test`。MIT。
