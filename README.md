# 資訊工程作品集網站

這是一個不依賴框架或後端的靜態作品集，可直接部署至 GitHub Pages。首頁由個人介紹與可分類的作品卡片牆組成；卡片會開啟摘要彈窗，只有具完整材料的作品才提供獨立作品頁或完整文件。

## 網站內容

- `index.html`：個人介紹、作品分類按鈕、作品卡片與摘要彈窗
- `projects/decimal-calculator/`：十進位加減計算機詳細頁
- `assets/css/styles.css`：全站樣式與響應式版面
- `assets/js/main.js`：行動版導覽與圖片放大
- `assets/images/`：作品圖片
- `assets/docs/`：作品頁所引用的研究文件

## 本機預覽

在 repository 根目錄執行：

```bash
python -m http.server 8000
```

瀏覽器開啟 `http://localhost:8000/`。

## 部署至 GitHub Pages

1. 建立 repository。若要使用個人首頁網址，名稱設為 `<GitHub帳號>.github.io`。
2. 將此資料夾內全部檔案 push 到 `main` branch。
3. 進入 repository 的 `Settings` → `Pages`。
4. `Source` 選擇 `Deploy from a branch`。
5. Branch 選 `main`，資料夾選 `/(root)`，按下 `Save`。

若使用一般 repository 名稱，網站網址會是 `https://<GitHub帳號>.github.io/<repository名稱>/`。本站所有連結均使用相對路徑，可支援兩種網址形式。

## 發布前確認

- 將首頁與頁尾的 GitHub 連結核對為正確帳號。
- 不要上傳成績單、排名、證件、API key 或含個人資料的原始檔。
- 新增作品時複製既有作品頁結構，維持相同閱讀順序。

## 新增作品卡片

1. 在首頁的 `.project-grid` 加入一個 `data-categories` 作品卡。
2. 在頁面底部加入對應的 `<template id="project-...">` 摘要資料。
3. 若有完整內容，在 template 設定 `data-more` 與 `data-more-label`；沒有完整頁時省略即可。
4. 同一作品可以同時屬於多個分類，例如 `data-categories="systems image"`。
