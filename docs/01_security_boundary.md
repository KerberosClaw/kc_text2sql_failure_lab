# The Security Boundary — Where Guardrails Stop

> **Summary (EN):** Deterministic guardrails (read-only account, statement
> whitelist, timeout, row cap) reliably make generated SQL *safe to
> execute*. They cannot make it *semantically correct* — and treating the
> first guarantee as if it were the second is the most common way
> Text-to-SQL systems quietly lie. This doc walks the boundary line:
> what engineering can promise, what only model capability can, and why
> the two are routinely confused.

以下為中文內容。

---

## 兩種「錯」是不同物種

Text-to-SQL 的輸出可以在兩個完全不同的層面出錯：

1. **執行層** — SQL 語法錯、打到不存在的欄位、想寫入資料庫、跑太久。
   這一層的錯**看得見**：資料庫會報錯、護欄會攔截、逾時會中斷。
2. **語意層** — SQL 完全可執行、結果照常回來，但答案不是問題要的。
   這一層的錯**沒有任何警報**：NULL 桶進了排行榜、JOIN 灌水了計數、
   成長用了另一種定義 — 每個數字都是資料庫真算出來的。

護欄工程只管得到第一層。本 repo 的每一個案例都是第二層的標本。

## 確定性護欄能保證什麼

本 repo 的示範護欄（`failure_lab.guard`，完整邊界見 SECURITY.md）：

- 唯讀連線（資料庫層的最小權限，比任何字串過濾都可靠）
- 單一語句、只准 SELECT／WITH
- SQLite 危險關鍵字（ATTACH／PRAGMA／DML／DDL）先擋再跑
- 逾時中斷與列數上限

這些是**可窮舉**的：狀態有限、規則寫得完、測試蓋得住。工程在這一層
是有效的，而且應該做好做滿 — 資料庫帳號層的最小權限永遠是第一道，
關鍵字過濾只是安全帶，不是煞車。

## 確定性護欄不能保證什麼

語意正確性的失敗形態是**開放集合**：問法無限、資料形狀無限、兩者的
交互作用無限。想用規則逐一堵（「偵測到 NULL 分組就改寫」「看到成長
就注入定義」）只能涵蓋想像得到的情形，而且規則彼此打架、越堆越脆。

這條線的另一邊屬於模型能力：讀懂 schema 註解、對可空欄位保持警覺、
在含糊的問題前先消歧。本 repo 的成績單（scoreboard）展示的就是同一
套護欄、同一套提示下，不同能力的模型在語意層的分佈。

## 給實作者的三句話

1. 護欄照做，但別把「安全可執行」當成「答案正確」對外承諾。
2. 語意層的驗收要靠**結果級評測**（見 docs/03），不是 code review SQL 字串。
3. 規則堆到第三層還沒堵住的問題，答案通常不在規則裡 — 在模型選型裡。
