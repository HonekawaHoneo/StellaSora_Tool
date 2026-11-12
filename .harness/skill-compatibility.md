# 実スキルのCodex接続規約

cumulativeが有効ならcumulative-quality.mdも既存工程から読む。baselineの固定履歴、設計の責務・根因・旧処理、独立した累積レビューを同じ変更単位へ接続する。別ハーネスを重ねず、観測所見を合格へ読み替えない。

structural_qualityが有効な対象では、各工程の契約を`.harness/structural-quality.md`から明示的に読む。discoveryの実baseline・再利用候補、designの直接変更と影響範囲、別コンテキストの構造レビューを既存工程へ統合し、別ワークフローや追加の承認を重ねない。品質基準の弱化は本人承認。上流本文を変更してこの契約を迂回しない。

このファイルは取り込んだ実スキルとCodexEnvSetの接続部分を定義する。
上流の原本は各スキルのUPSTREAM.mdとupstream-lock.jsonに保存する。
SKILL.mdはCodex向けの名前・説明とこの接続規約を加えた版で、上流の本文をそのまま含む。
上流本文のプラットフォーム固有の指定には、以下の対応を適用する。

## 工程の接続

### 常用担当と条件別の必須担当

0.17.0の新規作業は[実行契約の手引き](execution.md)へ接続する。実際の入力でbeginし、required_skillsの本文をskill-read、原指示・確定条件をcontext-readで読み、全roleの適用先をapply-skillsの実ファイル参照へ結ぶ。同じ実ファイルは一度の読出しで足りる。担当一覧や自己申告を実施済みの根拠にしない。nativeは実Hook入力から接続し、Cloudは各発言・再開で明示実行する。

各ユーザー発言・再開でevidence-first-response、poteto-mode、ponytail、unslop、technical-writingを必ず使う。自然な日本語、意味・条件・根拠の保持、最小十分な実行に適用する。短い質問でも担当は省かず、不要な工程説明や文書は増やさない。guideは既定の常用Skillと該当作業の必須Skillを固定参照として返し、利用者の独自割当は追加担当として保つ。独自のreview/UI担当で必須担当を置換しない。同じ実ファイルの重複読込みは不要。

| 該当する作業 | guide --activity | 必須の追加担当 |
| --- | --- | --- |
| コードの設計・実装 | code | implementation-planning。ponytailは常用 |
| コードのレビュー | review | ponytail-review、quality-review、blast-radius、no-comments |
| UI・UXの作成・変更・評価 | ui / ux | semantic-ui-design、ui-implementation-harness。読取専用レビューでも省かない |
| 構造・型・境界の検討 | architecture | architect。該当する24原則のleafもpoteto-modeから選ぶ |
| 性能の計測・主張 | performance | benchmark-checklist、principle-explain-the-number |
| TypeScript | typescript | typescript-best-practices |
| 変更の波及確認 | impact | blast-radius |
| 操作検証手順の作成・保守 | verification / verification-maintenance | create-verification-skill / maintain-verification-skill |
| 文脈復帰・長期作業 | context / long-running | recallとprinciple-guard-the-context-window / show-me-your-workとprinciple-guard-the-context-window |
| 再発する誤りの是正 | correction | correct、根本原因・構造化の原則 |
| 複数案・反証・並列作業 | design-options / adversarial / parallel | arena / interrogate / swarm |
| 調査・説明・振り返り等 | how / why / teach / sharpen / recap / planning / reflect / personalize / bot-ui | 各作業に対応する同梱Skill |

activityは複数指定できる。実際の変更予定パス・変更パスにUI/UX・TypeScript等が含まれる場合も該当担当を追加し、非該当との自己申告で外さない。設計・実装の現在工程はcode、review/doneはreview、UI変更の記録はUI担当を自動で追加する。進行中変更なしの読取専用レビューは`guide --activity review`を使い、変更単位を作る必要はない。条件が合う担当は任意扱いにせず、非該当の全Skillを毎回読み込むこともしない。既存のホスト権限・利用可能ツール・上流原本の固定を保ち、使用したという自己申告を意味理解の証明にしない。

読取専用のUI/UX評価は既存画面と両Skillで調査でき、調査のためだけにv3の変更単位を作らない。guideのUI未接続blockerは製品編集や検証済みの判定を許可しない意味であり、観察自体を禁止しない。新規UI変更と原則検証済みの完了には既定のv3/enforceと証跡が必要。

| 工程・役割 | 実スキル | 成果物と境界 |
| --- | --- | --- |
| 全体進行 | poteto-mode | state.jsonで現在地を確認し、共通工程の中で必要なプレイブック・補助スキルを選ぶ |
| 調査・要件 | grill-me → grilling | 環境から分かる事実を調べ、未解決の意思決定を質問する。discovery.jsonとrequirements.jsonへ記録する |
| 設計・実装 | ponytail | 要件を満たす最小の設計・実装。design.jsonとimplementation.jsonを更新し、runで検証する |
| 独立レビュー | ponytail-review | 別の人・別セッションで実施し、実際の指摘・判定をreview.jsonへ記録する |
| UI専門判断 | semantic-ui-design | 設計・実装・独立レビューから併用する。意味、部品、トークン、階層、密度、表現の過不足を扱い、既存工程は増やさない |

common-workflowは共通工程の案内と既存利用者向けの入口として残す。
requirements-discovery、implementation-planning、quality-reviewは成果物契約の補助として残し、実スキルと組み合わせる。
原指示と目的の契約はprotocol.mdを正本とし、標準担当からこの3つの既存補助Skillを工程ごとに明示的に読む。探索で本質と確定条件を分け、設計・実装では既存資産へ具体化し、レビューで双方を照合する。別工程や別成熟度分類は追加せず、単純な確定指示は短い記録で進める。既存の根本原因・最小十分性・構造品質の判断を再利用する。
実スキルのプレイブックは工程ごとに必要な部分を行う。実装前に共通の要件・設計ゲートを飛ばさない。
完了判定と移行はharness.pyのcheck/advance、検証証跡はrunを使う。state.jsonを手で書き換えない。
上流の「PRを開く」「マージする」は、変更の依頼範囲とホストの権限に従う。工程完了のために不要な外部操作を追加しない。

## ツールとモデル

完了・中断時の保存先はrules.mdのGit保存契約を使う。上流の「commit」「ローカル反映」だけで指定Gitリモートへの保存完了とはしない。既存の許可範囲でpushし、backup-checkの実リモート照合結果を確認する。

| 上流表記 | Codexでの扱い |
| --- | --- |
| Skill tool、`/skill-name` | 対応するスキルを明示的に使う。Skill専用ツールがない場合は隣接フォルダのSKILL.mdを読み、その手順に従う |
| Task、Agent、generalPurpose、poteto-agent | ホストが許可する委譲ツールを使う。poteto-agentはpoteto-modeへのファイル参照と同梱の役割定義を渡す一般エージェントとして扱う |
| AskQuestion、AskUserQuestion | ホストの質問ツールを使う。調査で分かる事実を質問せず、利用者の判断が必要な事項をまとめる |
| Grok / Claudeの既定モデル名 | そのまま指定しない。既定はinherit-parentでモデル指定を省略する。別モデルは実際に利用可能で、ユーザーやホストが許可した場合だけ使う |
| `.cursor/rules/pstack-models.mdc`、Cursorのモデル一覧 | Codexのモデル設定と実際のツール能力を使う。Cursorのホーム設定を新設・書き換えしない |
| writing-skillsの参照接続改訂 | コマンド・参照・フィールドの配線だけを変える場合は、改訂前に失敗する参照・構文・適用先の実検査を作り、改訂後に再実行する。意味判断や行動を変える場合は実際の独立した行動評価を行う。機械的な文字列検査をAIの意味理解や遵守の証明と呼ばない。未実施の圧力試験・委譲は実施済みと記録しない |
| create-skill | 利用可能なスキル作成手順を使う。なければスキルの形式・参照・ライセンスを直接検証し、同名ツールを使ったとは記録しない |
| cursor-team-kitのdeslop | 当該スキルが利用可能なら使う。なければ同梱unslop・no-commentsと実際のdiff/lintで対応し、Codexでの代替と記録する |
| control-cli / control-ui | 利用可能なCLI・ブラウザ操作で実物を検証する。使えない操作面を検証済みと扱わない |

委譲はホストの指示が許す場合に使う。禁止・未提供なら親が実装を担当し、独立レビューを別セッションへ引き継ぐ。
同じモデルの別コンテキストによるレビューを、異なるモデルによる評価と呼ばない。
pstackのエージェント役割原本はプロジェクトの `.harness/pstack/agents/` に配置する。ネイティブなサブエージェント登録を行ったという意味ではない。

## 許可・質問・言語

ユーザーの依頼、AGENTS指示、ホストの権限制御を優先する。上流のAutonomy節だけで許可範囲を拡張しない。
既に許可された範囲の作業は進める。外部メッセージ送信・デプロイ・マージ・破壊的操作は、ユーザーとホストの許可に従う。
grillingの質問・共有理解の確認は、要件を変える未解決の意思決定に用いる。既に回答・合意した事項を再承認待ちに戻さない。
上流の英語の出力例は構造の例として使い、利用者への説明は会話の言語で行う。

## スクリプトと補助スキル

pstackの補助スキル、原則、プレイブック、参照、スクリプトも固定版で同梱する。
読み込むのは現在の作業に必要なものだけ。poteto-mode以外の実スキルは原則として暗黙呼び出しを無効にし、工程から明示的に選ぶ。
Pythonの工程CLIと導入には外部依存を追加しない。
UIのブラウザ検証は導入先の既存ツールを接続する。Prototypeを試作に再利用する。Visual parityの差分ゼロは外観維持の移行だけに適用し、意味を改善するUI変更には要求しない。Subtract Before You Addを必要な視覚表現の省略理由にしない。UI用のSkillを配置しただけで自動起動と見なさず、全体進行と設計・レビューから明示的に選ぶ。
pstackの任意の監視・オーケストレーションスクリプトにはBunやGitHub CLI等が必要な場合がある。起動する前に依存と権限を確認する。今回の導入では起動・自動実行しない。
上流ファイルの同梱と構造検証を、全プレイブック・全モデルの実行検証と混同しない。

## v0.4.0の出力と配送への接続

通常回答の契約はrules.mdの「結論、結果、検証、必要な判断」とする。上流が要求する原則名・全レビュー・工程の実況は成果物へ記録し、通常回答に毎回展開しない。詳しいレビューを依頼された場合はその成果物を提示する。文法を崩す短縮や、意味・根拠の削除は行わない。

poteto-modeを全体進行の入口、ハーネスを工程と品質ゲートの正本とする。上流のgrillingで未解決の判断を確認した後、既に合意した事項を別の設計スキルで再質問・再承認待ちに戻さない。

独立レビューには、ホストで許可された新しいコンテキストのエージェントも使える。実装会話の全履歴を引き継がず、対象の成果物・差分・検証と実スキルのパスを渡す。実際のレビュアーとコンテキストIDを記録する。委譲ツールが提供されなければ別セッションへの引き継ぎを行う。

上流のCursor `/loop` はCodexの機能として仮定しない。稼働セッションの待機機構と配送CLIの一回実行を組み合わせる。Grok・Claudeなどの上流モデル名を追加せず、親モデルの継承を続ける。

PR・マージはrules.mdのautonomyと本人の許可範囲に従う。利用可能なGitHub接続ツールを優先し、接続がない場合の実行手段がghである。`ship-check`のforge-stateを現在のGitHub状態から作り、マージAPIのexpected_head_shaに結果を渡す。確認できない状態をCLEANやAPPROVEDとして補完しない。GitHubの必須チェック・レビュー・マージキューは無効化しない。

## UI実装の任意接続（0.5.0・段階1）

v0.9.0の新規UI作業はui-principles.mdのv3へ接続する。既存v1/v2設定と独自checksは明示移行まで保持する。semantic-ui-designとui-implementation-harnessのreferences/principle-checks.mdを設計・実装・独立レビューで使い、10原則を同じcaseと証跡へ対応づける。v1の互換経路や未接続を原則検証済みと報告しない。v3は見える印と実起動領域、全copyの根拠、期待値自体の構造化判断を既存工程へ加える。status/labelで目的検査を省略せず、期待値との一致だけで妥当性を合格にしない。以下は元の担当分担であり、v2/v3は別の工程を追加しない。

UI変更では、project.jsonのskill_bindings.ui_implementationが設定されていれば、
全体進行の担当がそのSkillを設計・実装・レビューの該当部分で明示的に読む。
同梱の候補はui-implementation-harness。明示的に使用を依頼された場合も利用できる。
この追加キーは担当への指示であり、harness.pyの新しい工程や自動検査ではない。
既存の標準4担当・利用者の割当は保持し、非UI作業には追加しない。

意味・階層・密度・視覚表現はUI Design、全体構造・認可・一般品質はアプリ側、
UIの構成・共通操作・状態・横断依存・実処理接続はUI専門判断が担当する。
作成中のDesignには確定した責務と受入条件で接続し、完成後に正本と改訂を照合する。
一般テストと証跡は既存checks/run、工程移行とレビューは既存protocolへ戻す。

Superpowers等がホストで利用可能なら、原因分析はsystematic-debugging、完了前照合は
verification-before-completion、テストはそのプロジェクトで選択済みの担当へ接続する。
この配布に外部Skillを追加した意味ではない。同じ対象へtddとtest-driven-developmentを
二重適用せず、既存の要件・計画を別Skillで再承認待ちへ戻さない。
Browser/Playwrightは実行可能な一経路を主担当とし、同じ試験をSkill名だけ変えて反復しない。
