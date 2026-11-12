---
name: codexenvset-setup
description: Use when the user requests installing, enabling, repairing, or checking the CodexEnvSet harness in an environment, including 「CodexEnvSetからハーネスを導入」, or development starts without its expected project connection.
---

# CodexEnvSetの導入と接続

配置・動作検証・このチャットでの指示適用・環境の保存/Publishを分けて確認する。既定工程はCodexEnvSetのdiscovery→requirements→design→implementation→review→done。

## Cloud CodexとHook非対応ホスト

0.17.0の新規作業は対象の`.harness/execution.md`へ接続する。実際の原依頼はnew --request-fileへ渡し、各発言・再開はbegin --context ... --request-file ...を明示実行する。skill-read/context-read/apply-skillsで実読出しと適用先を現在のtokenへ結び、advance/run --turnを使う。Cloudホストが自動begin・編集前拒否を行うとは報告しない。旧固定版と既存工程記録は自動変更せず、その版のstatus/check・実Skill・既存成果物で再開する。review→doneは対象検査・commit/push・実リモート照合を行い、保存失敗はsave-changeで再開する。

0.16.0以降は共通の必須担当を使う。応答・全体進行はevidence-first-response、poteto-mode、ponytail、unslop、technical-writingを常用する。実装・レビュー・UI/UXはguideの該当activityを指定し、返されたSkillを必ず読む。Gitのpre-commit/pre-pushによる検査はCodexのcommand Hookと別であり、Cloudでもgit_security_guard.verifiedを確認する。旧固定版にこの欄がなければ保護済みと報告せず、本人が指定した更新範囲で導入する。

Cloudでローカルcommand Hookを使えない場合や、ホームへ書けず対象リポジトリだけ書ける場合は、0.13.0以降の配布元から次を実行する。対象を明示し、ホームへの配置・/hooks・信頼承認・activation tokenを要求しない。

```sh
python3 /absolute/path/to/CodexEnvSet/scripts/install_environment.py --cloud --project /absolute/path/to/app
python3 /absolute/path/to/CodexEnvSet/scripts/install_environment.py --cloud --check --project /absolute/path/to/app
```

終了コード0、ready=true、activation_mode=cloud-explicit、project_connection.verified=trueを確認する。host_activation=not_applicable、native_hook_enforcement=falseであり、ローカルHookが有効になったとは報告しない。read-onlyの--checkは未導入を初期化しない。指定スキルが解決できなければ割当と参照先を修復し、別Skillへ勝手に置き換えない。

返却されたinstruction_pathsとskill_pathsの実ファイルをこのチャットで読む。project_connection.workflowは配置ではなく現在の工程の引継ぎを示す。0.14.0以降では対象のharness.py guide [変更ID]を使い、required_skills・artifact・blockers・can_edit_productを確認して既定工程を進める。UI作業はguide --uiとnew --uiを使う。用途から自明な説明は削除し、項目名は保つ。レイアウト・配置全般→オブジェクト自体の見た目・サイズ→色分けの順で解決する。折り畳み・sticky等は配置の例であり、必須手法ではない。Q&Aはそれでも伝えられない操作上不可欠な情報だけの最終手段とし、ツールチップへ一括退避しない。実画面の証跡・別コンテキストのレビューを省略しない。readyを工程実施・完了に読み替えず、報告前は対象IDのguideでwork_complete=trueを確認する。旧固定版でworkflow.supported=falseなら、その版のstatus/checkと既存工程に従い、新しいguideの動作確認済みとは報告しない。更新は本人の明示範囲で行う。

0.17.0の新規作業は各ユーザー発言と圧縮・中断後の再開で実入力によるbeginを実行し、そのtokenでguideを確認し、required_skills.responseと現在工程のSkill、continuity.context_pathsの関係する原指示・要件・設計を読む。最新発言と保持する目的・具体条件・問いの妥当性を照合する。全会話を毎回読み直さず、保存先と差分を使う。進捗質問で元の作業を置き換えず、実際の要求変更だけ原文を保って記録し、既存reopenへ戻す。旧版にcontinuityがなければ既存成果物へ直接戻り、毎ターンの自動強制があるとは報告しない。

新しいチャットでは対象のAGENTSと--cloud --checkを使って再接続する。セットアップで使う場合は対象Gitのチェックアウト後に実行する。対象の固定版と既存設定は保持する。Cloudで編集直前の自動拒否は使えないが、工程移行・検証・独立レビューの既存CLIゲートは維持する。配布元自体の準備、対象の保存、環境のPublishは区別する。

## ローカルHook対応ホスト

1. WindowsネイティブかPOSIXかを確認する。Windowsではdocs/windows.mdを読み、以下のpython3コマンドを`py -3 -X utf8`または実際のpython.exeへ置き換える。WSLの成功はWindowsの検証にしない。実行環境のPython 3.10+、Git、実効Codex home（CODEX_HOMEまたは通常の~/.codex）、ユーザースキルの読込先を調べる。書込権限はホストの手順に従う。別の書ける場所を実効読込先だと扱わない。
2. 既存の固定bundleかCodexEnvSet作業コピーを探す。Skillだけ配信されスクリプトがない場合は、接続GitHubまたはGitで https://github.com/HonekawaHoneo/CodexEnvSet のmainのSHAを確認して取得する。利用者の既存コピーや変更を上書きしない。
3. 配布元のREADMEとdocs/cloud-environment.mdを読み、既存設定を保持して次を実行する。開発対象が分かっていれば--projectを付け、このチャットでも直ちに接続する。

```sh
python3 /absolute/path/to/CodexEnvSet/scripts/install_environment.py --project /absolute/path/to/app
```

対象未指定の環境準備は--prepareを付ける。配布元自身は開発対象にしない。既存環境の新版導入は既存個人設定を保持し、既存アプリの版を自動更新しない。

4. installation_verified=true、probe成功、対象指定時はproject_connection.verified=trueを確認する。ready=false/終了コード3は有効化待ち。Codexの`/hooks`またはSettings > Hooksで本人がフックを確認・承認し、対象cwdでセッションを開始/再開する。信頼記録を代筆したり信頼迂回フラグを使わない。直前の結果のnext_activation_tokenを、次の別nativeツール呼出しのコマンドへリテラルで指定する。現在のsession ID（CODEX_THREAD_IDまたはホストが示すID）で`--check --project /absolute/path/to/app --session-id CURRENT_ID --activation-token NEXT_TOKEN`を実行し、ready=true、host_activation=verified、終了コード0を確認する。シェル変数・置換式でtokenを渡すとフックが照合できない。確認のたびに新tokenを使う。返却されたinstruction_pathsを実際に読み、対象のskill_bindingsに従い必要なSKILL.mdを読む。
5. 開発は対象のハーネスで実入力からnewまたはbeginを行い、native Hookが返す現在のtokenも確認する。実読出し・適用記録後の工程移行はadvance --turn、検証はrun --turn、独立レビューは別contextのreview.jsonへ記録する。別SkillのMarkdown計画や直接テストだけでこの工程を代用しない。
6. 実行環境に応じて保存・Publishと新しいチャットでの再検証を行う。readyは対象・セッション・固定bundleに結ぶ直近の実行証跡とnative loaderの有効/信頼状態を確認した結果であり、将来のチャットの証明へ流用しない。非対応ホストや実効読込先へ配布できない環境では未成立と報告する。

| 状態 | 対応 |
| --- | --- |
| 配置・probe・対象接続が成功、ready=false | 導入準備済み。有効化・信頼承認・実セッション検証を完了する |
| ready=true、host_activation=verified | 指示を読み、同じチャットで既定工程を続ける |
| 接続が失敗・未導入・共通指示が見つからない | 原因を解決するまで製品コードの変更を開始しない |
| ホームへ書けず対象だけ書ける | 許可範囲でinstall.py --projectを使いensure_project.py --checkで検証。プロジェクト限定と報告し、環境全体への導入完了とは呼ばない |
| Python/Git・配布元アクセス・実効読込先が利用不可 | 制約と必要な設定を報告。無関係な場所への配置や別ワークフローで成功に読み替えない |

読取専用の説明・監査だけなら対象を初期化しない。権限・ホスト制約・利用者の明示条件を優先し、保護ルールを迂回しない。
破損対象のcwdでは修復用コマンドもフックに拒否される。信頼した配布元のcwdから対象を明示して診断・修復するか、本人がホストのHooks設定を一時的に無効化して復元する。拒否を避けるための一般的なシェル許可は追加しない。復元後に再有効化・ready確認を行う。
