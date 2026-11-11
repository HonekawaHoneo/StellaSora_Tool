---
name: codexenvset-setup
description: Use when the user requests installing, enabling, repairing, or checking the CodexEnvSet harness in an environment, including 「CodexEnvSetからハーネスを導入」, or development starts without its expected project connection.
---

# CodexEnvSetの導入と接続

配置・動作検証・このチャットでの指示適用・環境の保存/Publishを分けて確認する。既定工程はCodexEnvSetのdiscovery→requirements→design→implementation→review→done。

1. 実行環境のPython 3.10+、Git、実効Codex home（CODEX_HOMEまたは通常の~/.codex）、ユーザースキルの読込先を調べる。書込権限はホストの手順に従う。別の書ける場所を実効読込先だと扱わない。
2. 既存の固定bundleかCodexEnvSet作業コピーを探す。Skillだけ配信されスクリプトがない場合は、接続GitHubまたはGitで https://github.com/HonekawaHoneo/CodexEnvSet のmainのSHAを確認して取得する。利用者の既存コピーや変更を上書きしない。
3. 配布元のREADMEとdocs/cloud-environment.mdを読み、既存設定を保持して次を実行する。開発対象が分かっていれば--projectを付け、このチャットでも直ちに接続する。

```sh
python3 /absolute/path/to/CodexEnvSet/scripts/install_environment.py --project /absolute/path/to/app
```

対象未指定の環境準備は--prepareを付ける。配布元自身は開発対象にしない。既存環境の新版導入は既存個人設定を保持し、既存アプリの版を自動更新しない。

4. installation_verified=true、probe成功、対象指定時はproject_connection.verified=trueを確認する。ready=false/終了コード3は有効化待ち。Codexの`/hooks`またはSettings > Hooksで本人がフックを確認・承認し、対象cwdでセッションを開始/再開する。信頼記録を代筆したり信頼迂回フラグを使わない。直前の結果のnext_activation_tokenを、次の別nativeツール呼出しのコマンドへリテラルで指定する。現在のsession ID（CODEX_THREAD_IDまたはホストが示すID）で`--check --project /absolute/path/to/app --session-id CURRENT_ID --activation-token NEXT_TOKEN`を実行し、ready=true、host_activation=verified、終了コード0を確認する。シェル変数・置換式でtokenを渡すとフックが照合できない。確認のたびに新tokenを使う。返却されたinstruction_pathsを実際に読み、対象のskill_bindingsに従い必要なSKILL.mdを読む。
5. 開発は対象のハーネスで変更単位をnewまたは既存statusから再開する。工程移行はadvance、検証はrun、独立レビューはreview.jsonへ記録する。別SkillのMarkdown計画や直接テストだけでこの工程を代用しない。
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
