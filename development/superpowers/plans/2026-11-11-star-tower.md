# 星ノ塔カウンター Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement the following tasks inline.

**Goal:** 9個の独立したカウンター、全リセット、合計、自由入力の目標値と差額を持つツールを届ける。

**Architecture:** 依存関係のない静的サイト。計算モデルとDOM操作を分離し、localStorageで状態を保持する。

**Tech Stack:** HTML、CSS、JavaScript、Node.js標準テスト。

**Spec:** `development/superpowers/specs/2026-11-11-star-tower-design.md`

## Global Constraints

- カウンターは素質3、強化2、リロール(40)、音符(45/72/90/200/320/400)の9個。
- 合計に素質3・強化2を含めない。差額は常に目標値−合計。
- 回数は0未満にならない。全リセット後も目標値を維持する。
- ライブラリー、外部画像、サーバーは不要。

## Review Focus

- すべての単価の取り違え、記録専用カウンターの混入。
- 0からの減算、負数・小数・空欄・過大値の直接入力。
- 目標超過時の負の差額。
- リロード後の復元、保存データ破損、保存禁止時の操作継続。
- 小さい画面での横はみ出しとボタンの操作性。

### Task 1: 計算モデル

**Files:** `dist/counter.js`, `tests/counter.test.cjs`, `package.json`

**Interfaces:** COUNTERS、createState()、setCount(state,id,value)、adjustCount(state,id,delta)、setTarget(state,value)、resetCounts(state)、total(state)、remaining(state)、restoreState(value)。stateは{counts,target}。

- [x] 混合入力の合計5339、独立操作、0下限、全リセットと目標保持、負の差額、不正入力・復元のテストを先に記述する。
- [x] `npm test`が未実装で失敗することを確認する。
- [x] モデルを実装し、`npm test`で全件成功を確認する。

### Task 2: 画面と配布

**Files:** `dist/index.html`, `dist/styles.css`, `dist/app.js`, `README.md`, `.openai/hosting.json`

**Interfaces:** Task 1のモデルを消費。ブラウザーの入力・ボタン操作で状態を更新し即時描画する。

- [x] 合計・目標・差額を上部に置き、9個のカウンターとワンボタンリセットを実装する。
- [x] 状態をlocalStorageに保存する。読み書き失敗時も計算を継続する。
- [x] `npm test`とJavaScript構文チェックを実行する。
- [ ] 管理されたプレビューでPC・モバイル表示、全操作、復元、負の差額を確認する。環境のrelay起動タイムアウトで未検証。
- [x] 独立レビューを実施。モバイルの3〜4桁表示の指摘に対し、実測文字幅に基づく縮小と長い数値用の配置を実装。
- [ ] 静的サイトをSitesへ配布し、返却URLで公開完了を確認する。
