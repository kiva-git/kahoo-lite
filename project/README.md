# project workspace

這個資料夾用來管理多個程式專案。

## 結構

- `project/<project-name>/`：各專案主目錄
- `project/_shared/`：共用腳本、模板、工具
- `project/_archive/`：封存不常用或已完成的專案

## 使用規則

1. 每個新專案建立在 `project/<project-name>/`
2. 共用內容放 `_shared/`，避免在各專案重複維護
3. 完成或暫停的專案可移到 `_archive/`
4. 每個專案建議至少包含：
   - `README.md`
   - `.gitignore`
   - 必要的啟動/測試指令說明
