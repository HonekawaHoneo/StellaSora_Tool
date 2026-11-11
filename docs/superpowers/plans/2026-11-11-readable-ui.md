# 読みやすいUI Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan inline, then request one final review.

**Goal:** コンパクトな配置を維持して、文字の読みやすさとカウンターの操作性を改善する。

**Architecture:** 表示専用のCSSと目標入力の補足文を変更する。計算・保存・イベント処理は既存のまま利用する。

**Tech Stack:** 静的HTML/CSS/JavaScript、Node.js標準テスト。

**Spec:** `docs/superpowers/specs/2026-11-11-readable-ui-design.md`

## Global Constraints

- 全9カウンター、価格、計算、研究上限、保存キー、リセット後の目標保持を維持する。
- 既存の色分けと960px／480pxの音符グリッド構成を維持する。
- 新規依存関係は追加しない。

## Review Focus

- 幅320／480／600／960pxでの数値とボタンの収まり。
- 長い保存値の自動縮小と既存のwide-numberレイアウト。
- 研究残数と超過表示の読みやすさ。
- キーボードフォーカスと入力エラーの視認性。
- 表示変更によるカウンターID・操作先・保存互換性への影響。

### Task 1: 表示と操作サイズ

**Files:** `dist/styles.css`, `dist/index.html`, `README.md`

**Interfaces:** 既存のクラスとDOM IDをそのまま利用し、モデルと保存データを変更しない。

- [x] 基準状態の`npm test`で10件成功を確認する。
- [x] 補足文字・色・余白・入力欄・ボタンサイズを調整する。
- [x] 狭い3列表示と長い数値用レイアウトを維持する。
- [x] `npm test`、JavaScript構文、HTML参照、CSS構文、差分を確認する。
- [x] 管理プレビューを試し、結果と検証できない範囲を記録する。
- [x] 最終レビューの指摘を解消し、既存Site更新用の差分を準備する。公開結果はSites実行ツールの記録を参照。

表示だけの可逆的変更のため、実装をなぞる新規テストは追加しない。既存の計算テストと表示確認で検証する。

## 検証結果

- `npm test`: 10件成功。`node --check`で両JavaScriptの構文が正常。
- tinycss2で210個のCSSルールと宣言を解析。HTML内の参照ファイル、SVG参照、JavaScriptのDOM ID参照が正常。
- 主要な小さい文字9組の前景色・背景色を数値で検証し、コントラスト比4.67〜6.37:1。
- `sites-preview start /workspace/StellaSora_Tool`は`relay could not open browser port 4173: timed out waiting for relay readiness`で失敗。`sites-preview status`は停止状態。実ブラウザーでの画面サイズ別表示・操作・スクリーンショットは未検証。
- 独立レビューで、960px以上の6列表示における4〜5桁の数値欄の狭さを指摘。数値をボタンの上に置く配置をこの幅にも適用して修正した。その他の指摘はなし。
