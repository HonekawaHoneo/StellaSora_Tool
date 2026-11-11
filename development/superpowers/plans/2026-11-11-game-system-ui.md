# 星ノ塔のゲーム仕様を反映するUI Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan inline, then request one final review.

**Goal:** 研究効果の使用回数と、素質再抽選・音符セット購入による消費コインを区別して表示する。

**Architecture:** 既存の静的サイトと保存形式を維持し、計算モデルに研究効果の残り回数を導出する関数を加える。既存PRの作業ブランチで実装・検証・レビューし、GitHubと既存Siteを更新する。

**Tech Stack:** HTML、CSS、JavaScript、Node.js標準テスト。依存関係の追加なし。

**Spec:** `development/superpowers/specs/2026-11-11-star-tower-design.md` と直前の調査・ユーザー指示。

## Global Constraints

- `trait3`、`enhancement2`、`reroll`、6価格の音符カウンターIDと保存キーを維持する。
- 研究上限は難易度8以上・対応研究解放時のLv3素質10回、＋2強化5回。上限超過した旧保存値を切り捨てない。
- 音符5個セットは90／72／45コイン、15個セットは400／320／200コイン。通常→20%引き→半額の順。
- 合計は素質再抽選40コイン×回数＋音符セットの価格×購入回数。素質購入・強化マシン・イベントの支出は対象外。
- 全リセットで目標コインを保持し、差額は負の値もそのまま表示する。
- コンパクトな表示と、画面幅・高さへの対応を維持する。

## Review Focus

- 使用回数と残り回数の取り違え、上限到達・超過の扱い。
- 旧保存値の復元・保持と、ID・保存キーの互換性。
- コイン価格と音符個数、購入回数の混同。
- 全9カウンターの操作先、差額、全リセット後の残り回数。
- 小さな画面での研究条件・購入単位・価格表示のはみ出し。

### Task 1: 研究効果の残り回数

**Files:** `dist/counter.js`, `tests/counter.test.cjs`

**Interfaces:** `researchUsage(state,id)` → `{used,limit,remaining,excess}` または研究対象外なら `null`。回数自体の変更・復元は従来どおり。

- [x] 初期上限10／5、使用後の残数、上限到達、旧保存の超過値保持、研究対象外を検証するテストを先に追加する。
- [x] `npm test`で新テストが未実装により失敗することを確認する（既存6件成功、新規4件失敗）。
- [x] 最小のモデル変更を実装し、`npm test`で全10件成功を確認する。

### Task 2: 単位・購入単位・使用回数の表示

**Files:** `dist/index.html`, `dist/app.js`, `dist/styles.css`, `README.md`, spec。

**Interfaces:** Task 1の研究残数を表示し、既存の計算・保存・操作を利用する。

- [x] 研究効果の使用回数・残数・適用条件を表示する。
- [x] 再抽選、音符5個／15個セット、価格と支出の単位をコインとして表示する。
- [x] 目標コインと差額、集計対象を明確にし、操作ラベルと説明も更新する。
- [x] テスト全件・構文・HTML参照・差分を検証し、管理されたプレビューを試す（relayのport4173起動タイムアウトにより実画面は未検証）。
- [x] 独立した最終レビューでモデル・DOMの配置／操作・旧保存値・上限超過・差額・リセットを確認し、修正が必要な指摘なし。
- [ ] コミット・pushし、既存PR・Site・ローカルZIPを更新する。
