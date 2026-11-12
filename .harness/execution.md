# 現在の入力とSkill適用を工程へ結ぶ

0.17.0の新規作業は `execution_contract=1` を既定とする。現在の入力、対象工程、担当Skillの実読出し、適用先の実ファイルを一つのtokenへ結ぶ。CLIにこの契約を外す開始オプションはない。既存の固定版・工程記録・利用者設定は自動で移行しない。

この手引きは接続済みプロジェクト向け。配布元自身は自己導入せず、そのAGENTS、計画、レビュー、quality.jsonと実Skillを使う。Windowsでは[Windows手順](windows.md)の実際のPython起動方法と引用規則を使う。以下の `python3` はPOSIXの例であり、Windowsネイティブの実行確認を代替しない。

native Hookではcontextを実際のsession_idへ結び、他セッションのtokenによる読出し記録・適用・工程移行を拒否する。任意の名前を別レビュアーの実セッションとして使わない。Cloudの明示contextはこのホスト観測の証明を伴わないため、実際に別コンテキストを使い、記録だけで本人性を証明したと報告しない。

## 現在の入力から開始する

`--request-file` に現在のユーザー発言を省略せず入れたUTF-8ファイルを渡す。`-` なら標準入力から読む。要約、AIが作った作業指示、固定のダミー文を現在の入力として渡さない。圧縮後は実際の再開入力と関係する原文・確定条件へ戻る。

nativeでは実装前のシェル書込みやリポジトリ外へのpatchを許可しない。一時入力はWrite/apply_patchで`.harness/changes/.inputs/request-担当名.txt`へ作成する。並行担当と名前を分け、適用根拠はdiscovery等の保存済み成果物へ結ぶ。自分で新規作成した入力は、最後のbeginで取り込んだ後、完了のadvance前に削除できる。本人の既存入力ファイルは削除しない。Cloudもこの置き場を使える。

```sh
python3 .harness/harness.py --json new search --kind change --author developer-1 --context session-1 --request-file .harness/changes/.inputs/request-developer-1.txt
```

`new` は原依頼を `discovery.request` へ保存し、開始時の引継ぎと `execution.token` を返す。ID・author・contextは実際の対象と担当に置き換える。UIは事前に[UI契約](ui-principles.md)のv3/enforceと `copy_policy: "object-first"`、実Registry、実検証を接続し、`new ... --ui` で宣言する。

既存作業への発言・訂正・進捗質問・再開には `begin` を使う。変更のない通常回答ではIDを省略でき、会話のためだけに `new` で工程を増やさない。複数候補から勝手に対象を選ばない。該当activityは複数指定できる。

```sh
python3 .harness/harness.py --json begin search --context session-1 --request-file .harness/changes/.inputs/request-developer-1.txt --activity code
```

`begin` は新しい `execution.token` と `request_digest`、必要なSkillと原資料の参照を返す。同じcontextの前の未完了tokenは失効する。別contextの並行記録は上書きしない。実行記録は入力のハッシュだけを保持し、会話本文の別ログを作らない。初回の原依頼は既存の `discovery.request` に残す。

native adapterは承認・有効化された実Hookの入力payloadから各prompt・再開の開始へ接続する。注入されたtokenを確認し、実資料を読んで適用する。CloudではホストHookを想定せず、各発言・再開で `begin` を明示実行する。Cloudの導入readyを毎ターンの自動開始・編集前の強制拒否と呼ばない。

## 実際の本文と原資料を読む

新規UIのRegistryは`.harness/ui-registry.json`、最初のwireframeやcandidateは変更IDのinputsへ置ける。newはstateのない入力専用scaffoldだけを引き継ぐ。実装前のブラウザ観察は登録済み`inspection_checks`とinspectを使い、通常checksやUI合格の証跡と区別する。詳細は[UI契約](ui-principles.md)を使う。

返された `required_skills` の全roleについて `skill-read` を実行する。このコマンドは実際のSKILL.md本文と指紋を返して読出しを記録する。同じ物理ファイルへ複数roleが向く場合は、一度の読出しで足りる。担当一覧の表示や「読んだ」という記述だけでは成立しない。

```sh
python3 .harness/harness.py skill-read --turn TOKEN --role response
python3 .harness/harness.py context-read --turn TOKEN --path .harness/changes/search/discovery.json
```

`context-read` は引継ぎの `continuity.context_paths` にあるプロジェクト相対パスを受け取る。関係するdiscovery・requirements・designの実ファイルを読み、最新発言と元の目的・具体条件・問いの妥当性を照合する。全履歴の再読や新しい要約正本は不要。

常用5担当はevidence-first-response、poteto-mode、ponytail、unslop、technical-writing。現在工程とactivityの担当、利用者の追加割当も読む。guideは実際の変更予定パス・変更パスからUIやTypeScript等の担当を補足する。該当作業を非該当と呼び替えて担当を外さない。

## 適用先を実ファイルへ結ぶ

`apply-skills --turn TOKEN --file RELATIVE_PATH` に、現在の入力への適用記録を渡す。次はフィールドの例であり、TOKEN・DIGEST・role・根拠を実値へ置き換える。`skills` は `required_skills` の全roleを過不足なく持つ。

```json
{
  "token": "TOKEN",
  "request_digest": "DIGEST",
  "intent": {
    "goal": "原依頼で確定した検索条件を満たす",
    "relation": "continue",
    "question_check": "検索対象と除外条件は原依頼にあり、追加質問は不要"
  },
  "skills": {
    "response": {
      "applied": "目的と除外条件を原依頼に照合した",
      "evidence": [
        {"path": ".harness/changes/search/discovery.json", "pointer": "/goal"},
        {"path": "docs/search-design.md", "anchor": "検索対象は公開済みの記事とする"}
      ]
    }
  }
}
```

`relation` は `new`、`continue`、`correction`、`status` のいずれか。各roleの `applied` に、実際にどの判断・変更へ適用したかを書く。各 `evidence` は実ファイルの `path` と、実在する引用 `anchor` または非空のJSON値を指す `pointer` の一方を持つ。実行記録自身を根拠にしない。ファイルの実在、参照先、内容指紋を検査する。

```sh
python3 .harness/harness.py apply-skills --turn TOKEN --file .harness/changes/search/skill-application.json
python3 .harness/harness.py execution-status --turn TOKEN
python3 .harness/harness.py guide search --turn TOKEN
```

`ready=true` は必要な読出しと適用参照が現在の内容に成立する状態。意味を理解したこと、記載した判断が正しいこと、担当者の実在・独立性の証明ではない。独立レビューでは原指示、実コード、検証と適用記録の内容を別contextで判断する。

## 成果物の更新と工程移行

工程の成果物を先に埋め、現在の実入力で `begin` し直して最新のSkill・原資料を読み、適用記録を作る。開始後に固定対象のSkill・原資料・設定・工程や適用根拠を変えると、そのtokenは失効する。古いtokenの指紋を手で付け替えず、実入力から入り直す。要求が変わったときは元のrequestを保ち、影響する上流から `reopen` する。

```sh
python3 .harness/harness.py advance search --turn TOKEN
```

`advance` は現在工程のtokenを閉じる。次工程では同じ実際の現在入力から新しい `begin` を行い、次工程の本文と原資料を読んで適用する。状態やtokenを手で変更して工程を進めない。

製品編集はimplementationで上流条件と現在の実行契約が成立した場合だけ行う。実装担当のcontextは `state.context`、独立レビュー担当は `review.context` と一致させ、両者を別contextにする。名前だけを変えた同じ作業を独立レビューと記録しない。

UIの変更が後から判明し、strict作業でUI宣言がない場合は、`reopen ID discovery --ui --reason ...` で原文を保ったままUI方針を固定し、上流を再確認する。新規のUI・UX評価は両UI担当を使う。読取専用評価のためだけにUI変更単位を増やさない。

実装の検証には実際の対象言語・既存構成で使えるtest・lint・securityを `checks` の `kind` として登録する。単に成功を返すコマンドや同じコマンドの分類付替えではなく、対象を検査する実行可能なツールを使う。既存の構造・累積品質と独立レビューも保持する。

```sh
python3 .harness/harness.py run search --turn TOKEN
```

原指示の `request_items` は `span.start`・`span.end` で原文の半開区間を指し、引用textを一致させる。原文の空白以外の全文字をカバーし、引用しない箇所へ条件を隠さない。要求・例示・仮説等の分類とbindingの意味は独立レビューで判断する。

## 完了を保存し、次の入力へ持ち越さない

reviewからの `advance ID --turn TOKEN` はdoneへの移行後、対象だけのsecurity check、通常commit、push、実リモートとの照合を自動で行う。doneとリモート保存の結果をそれぞれ確認する。配送失敗後は原因を直し、`save-change ID` で保存を再開する。`--local-only` は本人がローカル限定を明示した場合だけ使う。PR・マージ・環境Publishは別の許可と結果で扱う。

工程のない応答は `finish --turn TOKEN` で閉じる。閉じた記録は完了時の監査へ使えても、新しい編集・工程移行の許可へ再利用できない。done作業への質問は元資料を明示して読み、新しい製品変更は新IDか必要な `reopen` から開始する。

## 旧固定版で再開する

`begin` や実行契約がない版は、その版の `status`・`check`、既存成果物、利用可能な実Skillを直接読む。未対応を新契約の実施済みと報告せず、更新は明示指示の範囲で行う。更新だけで古い工程記録をstrictへ書き換えない。新規APIの `execution_contract=False` は古い回帰試験の明示fixture用であり、新規CLI作業の迂回入口ではない。
