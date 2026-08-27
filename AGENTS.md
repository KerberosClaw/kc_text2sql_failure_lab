# AGENTS.md — Text-to-SQL Failure Lab

## 專案定位

這是公開、可重現的 Text-to-SQL 語意失敗實驗室。核心主張是：SQL 可安全執行，不代表答案語意正確。案例以合成資料展示模型在 NULL、JOIN fan-out、時間缺期、實體語意、值域與範圍謂詞等陷阱上的失敗。

## 接手順序

1. 讀 `README.md` 掌握目前案例、指令與 scoreboard。
2. 讀 `DESIGN.md`；案例格式、taxonomy、資料生成、provider 與 gallery 設計以此為準。
3. 動安全護欄前讀 `SECURITY.md`；不要把「安全可執行」宣稱成「語意正確」。
4. 新增案例前讀 `docs/02_failure_atlas.md`，避免建立重複家族。

## 不可破壞的契約

- 一個案例一份 `cases/<id>.yaml`，`id` 使用 snake_case 且唯一。
- 判分比較 result set，不比較 SQL 字串；oracle 必須把「正確答案」釘成唯一。
- 陷阱要住在 deterministic seeded data 裡，並由測試保證 naive 與 oracle 結果確實分離。
- `mock-naive` 必須全紅、`mock-oracle` 必須全綠；評測器先通過自己的自驗，才有資格評模型。
- CI 保持零 secret、零付費呼叫、可重現；真模型憑證只走環境變數。
- 本 repo 是公開的。案例只用虛構資料，不得帶入客戶、公司、內部 schema、真實領域名稱或未公開實測數字。
- 修改對外敘述時同步檢查英文與正體中文版，以及 `web/data/` 的衍生資料是否需要重建。

## 驗證

- `make db`：重建 deterministic SQLite fixture。
- `make test`：執行 lint／測試與 evaluator 自驗。
- `make eval`：重跑兩個 mock 並更新 gallery data。
- 修改 web/gallery 後，以 `make gallery` 本機檢視。

只跑與改動相稱的 gate；若更新案例、generator、grader 或 provider，至少執行 `make test`。
