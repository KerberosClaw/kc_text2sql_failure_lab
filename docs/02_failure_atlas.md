# The Failure Atlas — a Taxonomy of Semantic Traps

> **Summary (EN):** Eight reproducible cases across eight trap families,
> every one executable and every one wrong. Each entry follows the same
> anatomy: an innocent question, a hidden assumption in the data, a
> naive-but-plausible SQL answer, and a result-level oracle. Browse them
> interactively in the gallery (`make gallery`) — every number there is
> produced live from `demo.db`. The taxonomy is open: new families are
> welcome as long as they ship with a data-level trap and an unambiguous
> grading rule.

以下為中文內容。

---

## 案例解剖學（每案固定格式）

| 欄位 | 作用 |
|---|---|
| `question` | 交給模型的自然語言問題 |
| `ambiguity_resolution` | 先把歧義吵完：這題「對」為什麼是唯一的、輸出幾欄 |
| `hidden_trap` | 陷阱藏在資料的哪裡、為什麼看起來沒事 |
| `naive_sql` | 看似合理、可執行、錯的答案 — 週五下午會過 review 的那種 |
| `oracle` | 結果級標準答案＋判分模式（不比 SQL 字串） |

## 八個家族（v1）

| 案例 | 家族 | 陷阱一句話 |
|---|---|---|
| `null_bucket_ranking` | null-semantics | 散客的公司欄全空，GROUP BY 把幾百個人聚成一列「NULL 大戶」進榜 |
| `join_fanout_count` | join-fanout | 經過明細表的 JOIN 讓多品項訂單被重複計數 — 每個總數都合理、每個都錯 |
| `growth_definition` | growth-definition | 「成長最多」：絕對增量冠軍與百分比冠軍是兩個不同類別 |
| `top_n_ties` | top-n-ties | 第 3 名恰好平手，LIMIT 3 隨機砍掉其中一個 — 砍誰看引擎心情 |
| `empty_vs_zero` | empty-vs-zero | 零訂單的類別從 INNER JOIN 報表裡整列消失 —「沒有列」和「值為零」是兩個答案 |
| `missing_period` | missing-period | 缺單月的趨勢少一列，圖看起來完整、下游平均全歪 |
| `entity_type_ignored` | entity-semantics | 法人列的聯絡人欄也有人名 —「姓名非空」不是「個人」的正確定義 |
| `enum_code_guess` | value-domain | 猜 enum 代碼 `= 1`（不存在）→ 回 0 列，看起來像「查無資料」的正經答案 |

## 兩個設計原則

**一題一陷阱。** 每個案例只測一件事。我們自己踩過反例：ties 案例
初版沒在 DDL 記載類別值域，一個強模型寫了 `'Toys'`（實際是小寫）
拿到 0 列 — 那次失敗測到的是「值域字面」不是「平手處理」。修法是把
值域寫進 schema 註解，讓平手陷阱單獨受測。（值域字面本身值得成為
獨立案例 — 歡迎 PR。）

**陷阱住在資料裡，不住在題目裡。** 題目與消歧句把「對」定義到唯一；
會不會踩雷取決於模型有沒有正確理解資料形狀。這也是為什麼 `make db`
的生成器逐一保證每個陷阱的前置條件，測試套件會驗（`tests/`）。

## 擴充路線（v2 候選）

聚合粒度錯置（訂單級 vs 明細級）、時間區間邊界（半開 vs 閉、時區）、
單位混淆（含稅未稅）、值域字面（類別名大小寫）、多對多對帳
（分組加總 ≠ 全庫總數）、自然語言歧義（刻意不消歧、測「先反問再答」）。
