<!-- codex-development-framework:start -->
## 共通開発工程（0.17.0 / 6d4b30c06ac8）

開発依頼では `.harness/rules.md` と `.harness/protocol.md` を読み、共通工程に従う。
各ユーザー発言と圧縮・中断後の再開時はPOSIXで `python3 .harness/harness.py guide`、Windowsで `py -3 -X utf8 .harness/harness.py guide` を実行する。UI作業は `guide --ui`。
返されたrequired_skillsを実際に読み、現在工程のartifactを作ってadvanceする。can_edit_productがfalseの間は製品を編集しない。導入のreadyを工程実施・完了と混同しない。
応答・全体進行ではevidence-first-response、poteto-mode、ponytail、unslop、technical-writingを常用する。実装・レビュー・UI/UXとその他の該当作業はguide --activityで必須担当を確認して使う。
responseとcontinuity.context_pathsから原指示・要件・設計を必要な範囲で読み直し、最新発言と目的・具体条件・問いの妥当性を照合する。進捗質問後も元の作業を続け、実際の要求変更だけ原文を保って記録して上流からreopenする。
指示の目的を理解し、確定要求・制約を保って最小十分に実装し、目的と元の指示の双方から検証する。
プロジェクト固有設定は `.harness/project.json`、固定版は `.harness/framework.lock.json`。
専門スキルはproject.jsonのskill_bindingsに従って使う。実スキルの接続規約は `.harness/skill-compatibility.md`。
UIの作成・変更・レビューは両UI担当を使う。新規UI変更はv3/enforceを準備してnew --uiで開始する。用途から自明な説明は削除し、項目名は保つ。配置全般→オブジェクトの見た目・サイズ→色分けの順で解決する。折り畳み・sticky等は配置の例であり、必須手法ではない。Q&Aはそれでも伝えられない操作上不可欠な情報だけの最終手段とし、ツールチップへ一括退避しない。
工程状態と証跡は `.harness/changes/`。Windowsは `py -3 -X utf8 .harness/harness.py status <id>`、POSIXは `python3 .harness/harness.py status <id>` で確認する。
工程移行はCLIのadvanceで検証し、失敗した条件を修正する。
保存はsecure-save.mdに従い、選択したファイルを検査してsaveで自動commit・pushし、実リモートを照合する。Git security guardが未成立なら保護済みとせず、--no-verify等で迂回しない。既定の試験上限は設定しない。
0.17以降の新規作業はexecution.mdの実行契約を使う。newに元依頼の--request-fileを渡し、各入力・再開はbeginで現在のcontextへ接続する。Skill本文はskill-read、原指示等はcontext-readで読み、実ファイルの根拠をapply-skillsで検査する。guide/advance/runには現在の--turnを渡す。記録が不足・失効している間は製品を編集しない。読出しを意味理解の証明と呼ばない。新規UIはv3/enforceとcopy_policy=object-firstが必要。通常のdone移行は安全な自動保存まで進み、失敗時はsave-changeで再開する。ローカル限定の本人指定だけ--local-onlyを使う。
現在のユーザー指示と既存プロジェクト指示に従い、許可済みの作業を継続する。
<!-- codex-development-framework:end -->
