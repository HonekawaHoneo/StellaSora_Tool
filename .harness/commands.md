# CLIとプロジェクト設定

0.17.0の開始・発言ごとの再開・実読出し・適用JSONは[実行契約の手引き](execution.md)を正本とする。新規CLI作業は実行契約が既定で、旧固定版と既存工程記録は自動変更しない。Cloudは各発言・再開でbeginを明示実行する。

## 必須担当と検査後の保存

```sh
python3 .harness/harness.py guide --activity code
python3 .harness/harness.py guide --activity review --activity ux
python3 .harness/harness.py guide --activity performance --activity typescript --activity impact
python3 .harness/harness.py --json save --message "変更内容" --path src/app.py --path tests/test_app.py
```

guideは常用5担当と現在工程・activityの必須Skillを返す。独自割当があっても既定常用担当を省かず、同じファイルは重複して読まない。saveは対象だけを一時indexで検査し、通常commit・push・実リモート照合を行う。未関係のstageは拒否し、残る未保存ファイルは結果へ示す。[検査・既存Hook・保証範囲](secure-save.md)を参照。

## リモートへの保存確認

```sh
python3 .harness/harness.py --json backup-check --remote origin
# 配布元自身から:
python3 runtime/harness.py --json backup-check --remote origin
```

コード・設定・必要な工程成果物をコミットし、作業ブランチをpushしてから実行する。品質工程の開始・終了とは独立した読み取り専用の確認で、PRやマージは行わない。設定済みリモートのpush先へ`git ls-remote`で接続し、現在のブランチのSHAとローカルHEADの一致を検査する。未コミット、未push、異なるHEAD、detached HEAD、保存先不明、接続失敗は終了コード1となる。

成功結果は`status=remote_saved`、`remote`、ローカルの`branch`、保存先の`remote_branch`、`head_sha`、`remote_sha`、`observed_at`を返す。設定されたpush refspecとpush.default=upstreamも確認する。複数・ワイルドカード等で保存先が曖昧な場合は停止するため、実際にpushした保存先を`--branch <保存先ブランチ>`で明示する。リモートURLや認証情報は出力しない。品質ゲート、PR、マージ、環境のPublishを合格とする検査ではない。利用者がローカル保存だけを指定した場合はリモート保存を約束せず、その範囲を報告する。

## v0.5.0の構造検査

`structural_quality`が有効なら、設定を整えてから`new ... --base <固定SHA>`、`baseline <id>`を実装前に実行する。設定例はexamples/project-python.json、詳細は[構造品質ゲート](structural-quality.md)。通常のstatus/check/advance/runの順序は変わらない。

`ci [<id>] --base <固定SHA>`はCI自身で再検証する。idを省略するとGit差分のreview.jsonから1件選び、0件・複数件を拒否する。構造検査有効時は基準SHAを開始記録・レビューと一致させ、対象のコード・設定を先にコミットする。

`verification_inputs`はGitignore対象の追加ファイルも内容指紋に含める。structural_qualityなしの既存プロジェクトは従来の工程を使える。更新だけで新しい検査や権限を付与しない。
UIの任意設定・Registry・画面証跡の契約は [UI設計](ui-design.md) を参照してください。既存のchecksへブラウザ検証を接続し、共通のrun/check/advance/ciを使います。

## v0.8.0の累積評価

累積評価もopt-inです。[累積品質の設定・レビュー契約](cumulative-quality.md)と`examples/project-cumulative.json`を使い、登録した責務と固定Git基準を明示します。導入済みの独自設定は更新で変更しません。

```sh
# 候補を標準出力へ生成する。責務のpurposeを記入してから方針として採用する。
python3 .harness/structure.py policy --config .harness/project.json --base FIXED_SHA --project-id my-app
# 配布元の単独入口。導入先の通常工程は既存baseline/run/review/ciを使う。
python3 runtime/structure.py scan --config quality.json --base FIXED_SHA
```

結果は`quality_status`と`quality_enforced`で品質判定と強制状態を区別します。enforceのREVIEW REQUIREDは深いレビュー前のdoneを拒否します。PASSでanchorや導入時負債を更新しません。単独scanの`--review`も登録した挙動検証を実行し、今回のコード・方針・履歴にレビューを結び付けます。

```sh
python3 .harness/ui_contract.py prepare change-id --before .harness/changes/change-id/evidence/before/before.json
```

prepareは実装前の定義元とbefore画像の指紋を保存し、design.json.ui.registry_snapshotへ設定するpathとsha256を返します。before画像の撮影は導入先の既存ブラウザ手段が担当します。承認済みの共有定義変更には `--candidate <Registry JSON> --approval-ref <承認記録>` と必要な `--approve-source <既存定義元>` を指定します。画像取得、共有ルールの承認、工程移行を実行したとは扱いません。

UI providerに渡される環境変数は `CODEXENVSET_CHANGE_ID`、`CODEXENVSET_CHECK_ID`、`CODEXENVSET_EVIDENCE_DIR`。providerは実行先に `<check-id>.ui.json` と画像等を出力します。非0終了・timeoutはモードにかかわらず失敗です。observeで品質上の問題を観測するproviderは実行結果とUI品質判定を分けて報告します。

任意の実ブラウザデモは配布元で `python3 scripts/demo_ui.py --output /tmp/my-ui-pilot`。空の出力先を指定します。Playwright/Chromiumが必要です。独立レビューを捏造せずreview工程で止まります。

プロジェクトルートから実行します。`--project <path>`、`--json`はサブコマンドより前に指定します。

```sh
python3 .harness/harness.py new search --kind change --author developer-1 --context session-1 --request-file .harness/changes/.inputs/request-developer-1.txt
python3 .harness/harness.py begin search --context session-1 --request-file .harness/changes/.inputs/request-developer-1.txt --activity code
# TOKENは今回返されたexecution.token。実読出しとapply-skills後に移行する。
python3 .harness/harness.py status search
python3 .harness/harness.py --json check search
python3 .harness/harness.py fingerprint search
python3 .harness/harness.py reopen search design --reason '影響範囲の見直し'
```

工程移行は`python3 .harness/harness.py advance search --turn CURRENT_PHASE_TOKEN`、implementation/reviewの検証は`python3 .harness/harness.py run search --turn CURRENT_IMPLEMENTATION_TOKEN`を使う。各tokenはその工程の実読出し・適用記録が成立した実値とし、advance後は次工程で入り直す。done後のCIは`python3 .harness/harness.py ci search`。詳細な実行順はexecution.mdへ戻る。

| コマンド | 内容 |
| --- | --- |
| new | --request-fileの原依頼をdiscovery.requestへ保存し、新しい変更とexecution.tokenを返す。UIは--ui |
| begin | 実際の現在入力を--request-file（または-の標準入力）で受け、--contextと対象工程・Skillに結ぶtokenを返す。activityは複数指定可 |
| inspect | 登録済みinspection_checksを実装前に実行。現在の--turnを使い、ソース不変・終了コード・ログを記録する。UI合格や工程移行にはしない |
| skill-read / context-read | --turnのSkill実本文、またはguideにある原資料の相対--pathを読み、実読出しを記録 |
| apply-skills | --turnと--fileの適用JSONを検査。全roleの判断と実ファイルのanchor/pointer・指紋を要求 |
| execution-status / finish | --turnの成立状態を確認、または成立した記録を閉じる。閉じたtokenは次の編集に使えない |
| status | 工程・作業者・完了記録を表示。成果物の合格判定は行わない |
| check | 現在の工程まで全条件を検証。未完成なら終了コード1 |
| advance | --turnの実行契約と工程条件を検査してtokenを閉じ、次の工程へ移行。review→doneでは対象検査・commit・push・実リモート照合も実行 |
| save-change | doneへの移行後、失敗した対象変更の保存を再開。--local-onlyはadvanceで本人の明示指定時だけ使用 |
| run | implementation/reviewでは現在の--turnを検査し、登録済み検証を実行。doneは完了時の適用根拠を再検査 |
| fingerprint | 実装・上流成果物の現在の指紋を表示。レビュー結果への転記に使う |
| reopen | 現在以前の工程へ戻り、そこから後の完了記録を取り消す。成果物と履歴を残す |
| ci | 指定変更IDのdoneと全条件を検証し、登録検証をその場で再実行 |

## 設定

`.harness/project.json`はプロジェクトが所有します。例えばNode.jsアプリの場合:

```json
{
  "schema_version": 1,
  "checks": [
    {"id": "tests", "kind": "test", "argv": ["npm", "test", "--", "--run"]},
    {"id": "lint", "kind": "lint", "argv": ["npm", "run", "lint"]},
    {"id": "security", "kind": "security", "argv": ["npm", "run", "security"]}
  ],
  "snapshot_ignore": ["coverage/*", "dist/*"],
  "skill_bindings": {
    "orchestrator": "poteto-mode",
    "requirements": "grill-me",
    "design": "ponytail",
    "review": "ponytail-review"
  }
}
```

コマンドは例です。0.17.0の新規実行契約はtest・lint・securityのkindを要求します。対象言語・既存構成で実際に利用でき、対象を検査するスクリプトとオプションを確認して登録します。単に成功を返すコマンドで分類を埋めません。
この版の標準割当は、原本・依存・ライセンスとともに導入される実スキルです。
argvはシェル文字列ではなく引数の配列です。パイプ・環境変数の展開・複数コマンドの連結を自動解釈しません。
必要なら、プロジェクトが所有する検証用スクリプトをargvから実行します。
runは全checksを要求し、design.traceabilityでは各要件をその中の検証IDに対応づけます。
コマンドがコードを変更すると証跡を失効させます。出力ディレクトリがある場合だけ、その生成物をsnapshot_ignoreへ明記します。

## 成果物

テンプレートは工程移行時にCLIが作成します。全フィールドを読んで実際の判断を記載してください。
`.harness/changes/<id>/state.json`を手で編集して工程を進めないでください。
完了済み成果物を変更するとreopenが必要です。
開始後に実際に変わったソースパスは、すべてimplementation.changed_pathsへ記載します。
削除はchanged_pathsとdeleted_pathsの両方へ記載し、開始時にあったファイルの削除であることを確認します。

evidenceには検証出力とJSON証跡、events.jsonlには工程移行・失敗・戻しの履歴が保存されます。
記録は署名付きではありません。信頼できる履歴はGitとCIの結果を合わせて管理してください。

## 更新

共通リポジトリで改善し、VERSION、ランタイムのVERSION、プラグイン版を更新して検証します。
上流原本の更新は固定コミット・ハッシュ・ライセンスを更新し、`python3 scripts/build_skills.py` で接続用入口を再生成します。
Gitのタグまたはコミットを配布版として固定したうえで、その版の導入ツールを実行します。

```sh
python3 scripts/install.py --project /path/to/my-app --update-from 0.1.0
```

同じ版・同じ内容への再導入は何も変更しません。
0.1.0からは以前の標準スキル割当だけを実スキルへ切り替えます。独自の割当と検証コマンドは保持します。
版を据え置いた内容変更、改変済み共通ファイルの上書き、共通ファイル削除を伴う更新は初期版では拒否します。
更新は検証証跡の指紋を変えるため、進行中の変更は実装検証とレビューをやり直します。

## CI

このリポジトリの `.github/workflows/validate.yml` は共通コードのテストとデモを実行します。
対象アプリ向けの例は `examples/project-ci.yml` です。依存関係のセットアップを追加して使います。
CI対象の変更IDを明示し、その変更の証跡と現在コードを検証します。履歴上の全変更を現在コードで検証し直す運用にはしません。
マージ必須チェックへの設定やGitHub上でのActions実行は、リポジトリ管理者の設定と実際の実行確認が必要です。

複数人が同じプロジェクトファイルを並行変更すると、証跡が失効します。
変更単位ごとにブランチやworktreeを使う運用を推奨します。

## 個人設定と配送（0.4.0）

短い自然な日本語、不要な確認の削減、通常回答と詳細成果物の分離は共通ルールで適用する。

個人設定の例は `examples/personal-profile.json`。初回の環境導入で取り込む。

```sh
python3 scripts/install_environment.py --profile examples/personal-profile.json
```

保存先は実効Codex homeの `codexenvset/profile.json`。既存設定は保持する。本人が編集するファイルであり、共通バンドルの指紋には含めない。新規対象の初期化時だけautonomyをproject.jsonへ渡す。既存対象の明示更新で追加する場合は次を使う。既存autonomyは保持する。

```sh
python3 scripts/install.py --project /path/to/app --update-from 0.3.0 --profile /path/to/codexenvset/profile.json
```

```json
{
  "completion": "merged",
  "branch_prefix": "ai/",
  "base_branch": "default"
}
```

上記をproject.jsonのautonomyに設定すると、変更IDfeatureの作業ブランチはai/featureになる。completionはreview、pr、mergedから選ぶ。autonomyを省略した対象の従来動作は変わらない。

### 品質確認から配送まで

コードをコミットし、独立レビュアーが実際に取得したマージ先のSHAをreview.jsonのbase_shaに記録する。品質工程をdoneまで進める。0.17.0のCLIはreview→doneで対象だけを検査し、必要な証跡をcommit/pushして実リモートを照合する。失敗はsave-changeで再開する。証跡だけのコミットでコード指紋が変わらなければレビューを再利用できる。

```sh
python3 .harness/harness.py --json ship-check feature
python3 .harness/harness.py --json ship feature
```

ship-checkは読み取り専用。PRがまだない、品質不足、コード未コミット、head/base不一致、CI・レビュー・保護条件の不足なら終了コード1。成功時はrepository、pr_number、expected_head_sha、base_sha、merge_methodなどをJSONで返す。既にマージ済みならstatus=merged、ready=falseを返す。

shipはPR作成・再利用、待機状態の記録、条件付きマージを一回実行する。completion=prならPR作成で止まる。waitingは成功した配送ではなく、まだCI・レビュー・保護条件が必要な状態。呼び出し側は状態を待ち、取得し直す。コードのCI失敗は原因を修正し、検証・独立レビューをやり直す。

ghが利用できて認証済みである必要がある。マージ方式はリポジトリで許可されたsquash、merge、rebaseの順に選ぶ。マージAPIには検証したheadをshaとして渡す。保護されたブランチの条件を迂回するフラグは使わない。

### 接続ツールからの読み取り専用確認

GitHub接続ツールがあれば、現在の状態を取得して次のJSONをプロジェクト外の一時ファイルへ保存する。取得時刻はタイムゾーン付きISO形式。60秒を超えた状態は拒否する。

```json
{
  "observed_at": "2026-11-09T12:00:00+00:00",
  "repository": {
    "nameWithOwner": "owner/repo",
    "defaultBranchRef": {"name": "main", "target": {"oid": "マージ先のSHA"}},
    "squashMergeAllowed": true,
    "mergeCommitAllowed": true,
    "rebaseMergeAllowed": false
  },
  "pull_request": {
    "number": 7,
    "url": "https://github.com/owner/repo/pull/7",
    "state": "OPEN",
    "isDraft": false,
    "isCrossRepository": false,
    "headRefName": "ai/feature",
    "headRefOid": "PRのhead SHA",
    "baseRefName": "main",
    "baseRefOid": "マージ先のSHA",
    "mergeable": "MERGEABLE",
    "mergeStateStatus": "CLEAN",
    "reviewDecision": "APPROVED",
    "statusCheckRollup": [{"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"}],
    "mergeCommit": null
  }
}
```

```sh
python3 .harness/harness.py --json ship-check feature --forge-state /tmp/current-forge.json
```

これはghのJSONフィールド名に合わせた接続契約。RESTのopen/closed、draft、head/baseなどは実際の値から変換する。マージ可否が未知ならCLEANにせず、未確認状態として渡す。必須レビューがない場合のreviewDecisionは空文字列。StatusContext形式のチェックはstate=SUCCESSを要求する。具体的なマージ先が既定以外なら、追加のbase_shasにそのブランチ名と最新SHAを持たせる。

接続ツールでマージするときは、ship-checkが返すexpected_head_shaをAPIの同名引数に渡す。直前のhead/baseが変われば状態を再取得し、再検証する。実PRのMERGEDとmergeCommitを確認してdelivery.jsonを更新する。結果不明時は実PRを照合し、再作成しない。
