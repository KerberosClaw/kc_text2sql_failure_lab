# Trustworthy Evaluation — the Eval Must Pass Its Own Eval

> **Summary (EN):** Grading Text-to-SQL at the SQL-string level is grading
> handwriting; we grade normalized result sets against a result-level
> oracle. Two built-in mocks (all-wrong / all-right) form the grader's
> entrance exam, run in CI on every push. This doc also documents our own
> first-run autopsy: three "model failures" that turned out to be spec
> bugs in the eval — under-specified output contracts and undocumented
> value literals — and what changed because of them.

以下為中文內容。

---

## 為什麼比結果、不比 SQL

同一題有無限多種正確 SQL：欄位別名不同、JOIN 順序不同、CTE 或子查詢、
視窗函數或自連接。拿 gold SQL 做字串／AST 比對，等於規定「用我的寫法
才算對」。本 repo 的 oracle 是**結果集**：模型 SQL 跑出來的資料經正規化
（浮點容差、依判分模式決定是否忽略列序）後與 oracle 結果比對。判分
模式三種：`ordered-set`（排行、時序）、`set`、`scalar`。

## 判分器的入學考

`mock-naive` 對每題回覆該題的 naive SQL（全錯）；`mock-oracle` 回覆
oracle SQL（全對）。CI 在每次 push 斷言：naive 必須 0 分、oracle 必須
滿分。**連這兩顆都分不開的判分器，沒資格為真模型打分。** 這個自我
檢驗跑在任何真模型之前，零成本、零金鑰、確定性。

## 第一次真模型跑分的驗屍報告（我們自己的打臉紀錄）

首輪讓一個旗艦模型上場，8 題掛了 3 題。逐案驗屍的結果：**三題全是
評測自己的洞，不是模型的錯。**

1. **輸出契約沒講死（兩題）。** 模型多回了一欄 `customer_id` — 語意
   全對、數字全對，但結果集比對失敗。錯在題目沒說「回傳恰好兩欄」。
   修法：每題的消歧句補上明確的輸出欄位契約；契約先講死，違約才算錯。
2. **值域字面沒記載（一題）。** 模型寫 `WHERE c.name = 'Toys'`，資料
   裡是小寫 `toys`，0 列。它的平手處理（DENSE_RANK）其實完全正確 —
   這題測到的是另一個陷阱，違反「一題一陷阱」。修法：類別值域寫進
   DDL 註解。

規格修正後重跑：同一個模型滿分。**評測的規格需要跟程式碼同等級的
嚴謹 — 你以為在測模型，其實常常在測自己的題目。**

## 可信跑分的最低配備

每份報告記錄：模型完整名稱、提示模板與 schema 的雜湊（prompt drift
可偵測）、逐題延遲、失敗分類（`wrong-result`／`exec-error`／`refused`）。
已知限制（誠實聲明）：目前每題單次執行，未做多次重跑的穩定性統計；
溫度／seed 依供應端預設。要發表比較性結論前，請自行加上重跑。
