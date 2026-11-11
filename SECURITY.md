# セキュリティと検出結果の確認

このアプリはサーバー・ログイン・APIキーを使わない静的サイトです。カウンターと目標値はブラウザー内のlocalStorageに保存し、アプリから外部へ送信しません。公開元GitHubには配信時の通常のアクセス情報が届きます。

## 自動チェック

- **Validate and publish**: push・PR・週次に計算テスト、公開物検査、Gitleaksを実行します。秘密情報はgit全履歴（取得した全ref）と作業ツリーを検査し、ログの検出値を秘匿化します。検査の失敗時はPagesへの新規デプロイを停止します。既に公開中の版は残ります。
- **CodeQL**: JavaScriptとGitHub Actionsをpush・PR・週次に解析します。検出結果はリポジトリの **Security → Code scanning** に出ます。アラートの存在自体はActionsを失敗にしないため、結果を確認して対処してください。
- **Dependabot**: SHAで固定したGitHub Actionsの更新PRを週次で提案します。GitleaksのバージョンとSHA256は `scripts/scan-secrets.sh` に固定しています。更新時は[公式リリース](https://github.com/gitleaks/gitleaks/releases)の対応するチェックサムを確認して両方を更新してください。

Actionsの失敗はリポジトリの **Actions** から確認できます。GitHub個人設定の **Notifications → Actions / Security alerts** で、失敗・セキュリティアラートの通知を有効にしてください。このリポジトリのWatch設定も確認してください。通知の配送は各アカウントの設定に依存します。

## 管理者が設定する項目

1. **Settings → General → Default branch** を `main` にします。週次検査は既定ブランチ上のワークフローで実行されます。
2. **Settings → Pages → Source** を **GitHub Actions** にし、公開後は **Enforce HTTPS** を有効にします。デプロイ用 `github-pages` environment の許可ブランチを `main` に制限します。ドメインや追加のシークレットは不要です。
3. **Settings → Rules → Rulesets** でmainへの直接pushを制限し、PRレビューと `Tests and public assets`、`Secret scan`、2種類のCodeQLの成功を必須にします。既存ルールは削除・緩和しないでください。CodeQLの検出内容はSecurityでも確認します。
4. **Settings → Code security and analysis**（UIではCode security / Secret Protectionと分かれる場合があります）で利用可能な **Dependency graph / Dependabot alerts / Secret scanning / Push protection** を有効にします。CodeQLはリポジトリ内のadvancedワークフローを使い、default setupとの二重実行を避けます。
5. **Settings → Actions → General** の標準トークン権限はread-onlyのままにし、fork PRへのwrite token・シークレット送信は有効にしません。既存のActions制限は緩和せず、必要な公式Actionsだけを許可します。

このファイルを追加しただけでは、管理者設定や個人の通知設定が有効になるわけではありません。

## 検出時の対応

秘密情報を検出した場合、実際に使える認証情報なら発行元で直ちに失効・再発行します。ファイルから消すだけでは履歴の漏えいは解消しません。ログや公開Issueに秘密の値を貼らず、履歴の除去が必要なら影響する利用者と調整します。秘密情報が公開サイトに含まれた疑いがある場合は、Pagesを非公開化してから調査し、安全な版を再公開してください。

CodeQLやDependabotのアラートは対象箇所と影響を確認し、修正をPRで検証します。原因未確認のまま検査を無効にしたり、広い除外ルールを追加したりしないでください。

脆弱性の報告は、利用可能なら **Security → Advisories → Report a vulnerability** から非公開で行ってください。非公開報告が利用できない場合も、秘密情報や悪用手順を公開Issueに貼らないでください。

## 制約

公開物検査はこの静的アプリ専用です。HTML冒頭のdoctype・html・head・charset・CSP・referrerを承認済みの順序と内容に固定し、間の空白以外の変更は失敗させます。HTML5と簡易パーサーの解釈差でCSPが無効になるケースを避けるためです。公開ファイルの追加やこの前置きの変更は、検査の更新とブラウザーでの再確認を含めてレビューしてください。

自動検査はすべての秘密情報・脆弱性を検出する保証ではありません。Pagesのmeta CSPでは `frame-ancestors` などHTTPヘッダー専用の防御を設定できません。localStorageは同じ `honekawahoneo.github.io` originの他のサイトと共有されるため、機密情報を保存しないでください。デプロイ権限のある管理者による改変は、ブラウザー側の制限では防げません。
