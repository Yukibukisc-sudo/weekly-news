# 三地週報 — 全自動每週新聞更新

每週自動用 Claude API（搭配 web search）搜尋「台灣 / 日本 / 世界 / 財經 / 生成式AI」
五個分類上週的十大新聞，整理成一份網頁，並自動部署到 GitHub Pages。

整套流程全自動，啟動後不需要手動操作。

---

## 運作方式

```
GitHub Actions（每週一排程觸發）
   │
   ├─ 1. scripts/fetch_news.py
   │     呼叫 Anthropic Claude API，開啟 web_search 工具，
   │     針對五個分類各搜尋「上週」十大新聞，輸出 data/news.json
   │
   ├─ 2. scripts/build_html.py
   │     讀取 data/news.json，套入 template.html 模板，
   │     產生最終網頁 dist/index.html
   │
   ├─ 3. git commit 把 data/news.json 與 dist/index.html 寫回 repo
   │     （方便你隨時在 repo 裡看到歷史資料與網頁版本）
   │
   └─ 4. 部署 dist/ 目錄到 GitHub Pages
         （你和任何人都可以用網址直接看到最新一期週報）
```

---

## 設定步驟（第一次設定，約 10 分鐘）

### 1. 建立 GitHub repo

把這個資料夾上傳成一個新的 GitHub repository（公開或私有皆可，
若是私有 repo 要確認 GitHub Pages 的方案支援私有部署，免費帳號通常建議用公開 repo）。

```bash
cd news-auto
git init
git add .
git commit -m "init: 全自動新聞週報"
git branch -M main
git remote add origin https://github.com/<你的帳號>/<repo名稱>.git
git push -u origin main
```

### 2. 設定 Anthropic API 金鑰

1. 到 [console.anthropic.com](https://console.anthropic.com) 取得你的 API Key（格式類似 `sk-ant-...`）。
2. 到 GitHub repo 頁面 → **Settings** → **Secrets and variables** → **Actions**。
3. 點 **New repository secret**，新增一筆：
   - Name: `ANTHROPIC_API_KEY`
   - Value: 貼上你的金鑰
4. 存檔。

> ⚠️ 金鑰請務必透過 GitHub Secrets 設定，不要直接寫進程式碼或 commit 進 repo。

### 3. 開啟 GitHub Pages

1. 到 repo 的 **Settings** → **Pages**。
2. **Source** 選擇 **GitHub Actions**（不是 "Deploy from a branch"）。
3. 存檔即可，不需要再手動指定分支。

### 4. 第一次手動觸發，確認整套流程跑得動

1. 到 repo 的 **Actions** 頁籤。
2. 左側選擇「每週自動更新新聞週報」這個 workflow。
3. 點右側的 **Run workflow** 按鈕手動跑一次。
4. 等待約 2-5 分鐘（要呼叫 5 次帶 web search 的 API，會比一般 API 呼叫慢一些）。
5. 跑完後到 **Settings → Pages** 頁面上方會出現你的網站網址，
   格式通常是：`https://<你的帳號>.github.io/<repo名稱>/`

之後每週一台灣時間早上 8:30，會自動重新執行一次，不需要再手動觸發。

---

## 之後想自己調整的地方

| 想做的事 | 要改哪裡 |
|---|---|
| 改排程時間 | `.github/workflows/weekly-update.yml` 裡的 `cron: "30 0 * * 1"`（cron 是 UTC 時間，記得算時差） |
| 改用別的 Claude 模型 | `scripts/fetch_news.py` 開頭的 `NEW_MODEL` 環境變數，或直接改程式碼中的預設值 `claude-sonnet-4-6` |
| 改新聞分類或搜尋主題 | `scripts/fetch_news.py` 裡的 `CATEGORIES` 清單，可新增/刪除/修改 `prompt_topic` |
| 改網頁外觀、顏色、版面 | `template.html`（這是網頁的原始模板，純 HTML/CSS/JS，跟你之前看到的版本是同一份設計） |
| 想要本地手動測試，不想等排程 | 見下方「本地測試」章節 |

---

## 本地測試（不透過 GitHub Actions）

如果你想在自己電腦先測試流程是否正常，不用等排程：

```bash
# 1. 安裝 Python 3.9+（通常 Mac/Linux 已內建）

# 2. 設定環境變數（暫時性，僅在這個終端機視窗有效）
export ANTHROPIC_API_KEY="sk-ant-你的金鑰"

# 3. 執行抓新聞（會花 1-3 分鐘，因為要做 5 次帶搜尋的 API 呼叫）
python3 scripts/fetch_news.py

# 4. 執行 build，產生最終網頁
python3 scripts/build_html.py

# 5. 打開 dist/index.html 看結果（直接用瀏覽器開啟這個檔案即可預覽）
```

如果想測試「不是今天所在週」的資料範圍，可以加上：

```bash
export WEEK_END_OVERRIDE="2026-06-21"   # 指定週末日期 (週日)
python3 scripts/fetch_news.py
```

---

## 費用估算

每次排程會呼叫 5 次 Claude API（每個分類一次），每次都會用到 web_search 工具
（工具呼叫本身依 Anthropic 定價另計，搜尋次數依新聞豐富程度可能每分類用到數次搜尋）。
建議先在 [console.anthropic.com](https://console.anthropic.com) 的用量頁面觀察前 1-2 次
執行的實際花費，再評估是否需要調整分類數量或搜尋深度。

GitHub Actions 與 GitHub Pages 在一般使用量下都在免費額度內
（公開 repo 的 Actions 分鐘數與 Pages 流量都有寬鬆的免費額度）。

---

## 檔案結構

```
news-auto/
├── .github/workflows/weekly-update.yml   排程設定
├── scripts/
│   ├── fetch_news.py                     抓新聞 → data/news.json
│   └── build_html.py                     套模板 → dist/index.html
├── template.html                          網頁原始模板（含佔位符）
├── data/
│   └── news.json                          最近一次抓到的新聞資料（自動產生/更新）
├── dist/
│   └── index.html                         最終部署的網頁（自動產生/更新）
├── requirements.txt
└── README.md                              這份說明文件
```

---

## 疑難排解

**Q: Actions 執行失敗，錯誤訊息跟 API key 有關？**
檢查 repo Secrets 裡的 `ANTHROPIC_API_KEY` 是否設定正確、有沒有多打空格或斷行。

**Q: 跑完了但某個分類新聞篇數不是 10 則？**
模型偶爾會因搜尋結果不足而少給幾則，程式會印出警告但仍會繼續輸出，
不會讓整個流程失敗。可以到 Actions 的執行紀錄（log）查看實際警告內容。

**Q: 想暫停自動更新？**
到 repo Settings → Actions → General，把 Actions 停用，
或直接刪除 `.github/workflows/weekly-update.yml` 這個檔案。

**Q: GitHub Pages 網址打不開或顯示 404？**
確認 Settings → Pages 裡 Source 是設為 "GitHub Actions"，
並確認至少成功跑過一次 workflow（看 Actions 頁籤有沒有綠勾勾）。
