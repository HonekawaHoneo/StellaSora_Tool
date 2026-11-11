# GitHub Pagesとセキュリティ検出の実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 既存カウンターをGitHub Pagesへ安全に公開し、問題を検出・確認できるようにする。

**Architecture:** distの4ファイルを検証してdocsへ同期し、main /docsから直接公開する。PR・push・週次で検査し、公開前の成功チェックはmain保護で必須にする。

**Tech Stack:** 既存JavaScript、Python標準ライブラリー、GitHub Actions、Gitleaks、CodeQL。

**Spec:** development/superpowers/specs/2026-11-11-pages-security-design.md

## Global Constraints

- ランタイム・ビルドに外部パッケージを追加しない。
- 独自のPages/OIDC権限を使わない。Actionsは40桁SHAで固定する。
- APIキー・個人情報・サイト管理設定・git履歴をPagesの公開物に含めない。
- 対象は元のStellaSora_Tool。fork先は変更しない。

## Review Focus

- distへの意図しない追加ファイル・リンクは公開前に失敗する。
- CSPの欠落・緩和と外部リソース参照は検出する。
- 既存のカウンター、保存、フォントサイズ調整はCSP下でも動作する。
- 秘密情報検査は履歴・未コミットファイルの両方を対象にし、検出を実験で確かめる。
- PagesのサブパスでCSSとJSが読み込め、スマートフォン幅でも操作できる。

### Task 1: 公開物の検証とブラウザー制限

**Files:** scripts/build-site.py、tests/test_site_build.py、dist/index.html、package.json

- [x] 危険な追加ファイル、リンク、CSP欠落・緩和、外部参照を拒否する失敗テストを書く。
- [x] Python標準ライブラリーのHTMLParserと厳密な公開物一覧でbuild-site.pyを実装する。
- [x] CSPとno-referrerをmetaとして追加し、既存の計算テストと新しい検査を通す。
- [x] ローカルHTTPでChromiumを動かし、操作・保存・サブパス・CSPを確認する。

### Task 2: 自動検出とPagesデプロイ

**Files:** .github/workflows/pages.yml、.github/workflows/codeql.yml、.github/dependabot.yml、scripts/scan-secrets.sh、README.md、SECURITY.md、.gitignore、docsの公開物

- [x] Gitleaksの固定バイナリー検証・履歴と作業ツリー検査を実装し、実データの検査とダミー秘密情報の検出を確認する。
- [x] 最小権限で検査するActionsと、main保護を必須にする公開手順を作る。
- [x] CodeQL（JavaScript・Actions）の週次検査とDependabotを追加する。
- [x] 設定・通知・検出時の対応・制約を文書化する。
- [ ] YAML/actionlint、全テスト、履歴検査、独立レビューを通してブランチをpush・PR化する。可能な設定操作とデプロイを完了し、実行できない設定だけを具体的に案内する。

### Task 3: mainブランチからの直接公開へ変更（ユーザー指定）

- [x] docsをアプリ専用にし、開発記録はdevelopmentへ移す。
- [x] sync_pages/check_pagesの検証テストを先に追加し、公開用コピーの余分なファイル・リンク・変更差分を拒否する。
- [x] docsを同期し、公開先main /docsの説明へ更新する。独自デプロイjobは削除し、CIの検査は維持する。
- [ ] 全テスト・スキャン・独立レビューとGitHub CIの成功を確認し、PRをmainへマージする。公開設定とデプロイの状態を別途確認する。
