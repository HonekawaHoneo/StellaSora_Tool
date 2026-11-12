# 検査後にコミット・pushする

0.16.0以降の共通保存経路。ローカルとCodex CloudでGitとPythonを使う。Codexのcommand Hookに依存せず、Git自身のHookを導入する。

```sh
python3 .harness/harness.py --json save --message "変更内容" --path src/app.py --path tests/test_app.py
# 配布元自身は自己導入せず、同じ保存処理を使う。
python3 runtime/harness.py --json save --message "変更内容" --path runtime/example.py
```

Windowsは実際のPythonか`py -3 -X utf8`を使う。Gitの作業者情報と認証は利用者の設定を使い、変更しない。作業ブランチへ通常pushし、force push・マージを追加しない。

## 保存する内容

1. 指定ファイルと実効push先を確認する。ディレクトリ一括指定、Gitメタデータ、対象外パス、無関係なstage済みファイルを拒否する。
2. 一時indexへ対象だけをstageし、実際のGit blob/treeを検査する。作業ツリーやgitignoreだけを根拠に安全としない。
3. 検査済みindexを排他で反映し、treeを固定して通常のcommitを行う。既存Hookが対象や内容を変えれば拒否する。
4. 送信履歴を検査し、通常pushする。後のコミットで削除されていても、送信される過去コミットに秘密があれば止める。
5. 実リモートのSHAとローカルHEADを照合する。push失敗後の再実行は空コミットを増やさず、同じコミットを送る。

未関係の未追跡・無視ファイルはstageしない。未保存作業が残れば`selected_paths_saved`、`all_work_saved=false`と残りのパスを返す。全作業の保存確認である従来のbackup-checkは未保存ファイルを拒否する。問題ファイルを自動削除したり、検出を無視した部分コミットを行ったりしない。

## Gitの検査

定義した機密設定・秘密鍵等のパスと、高確度の認証情報形式・認証情報リテラル代入を検査する。結果はパスと規則名だけで、秘密値は表示しない。読めないオブジェクト、LFSポインタ、gitlink等は安全とせず拒否する。

commit・merge・cherry-pick・amに関係する入口とpre-pushへ検査を接続する。既存Hookを残して連鎖し、コミットではその後のindexを検査する。pushではアップロード可能な既存Hookより先に送信履歴を検査する。既存Hookの引数・stdin・失敗を保つ。

検査コードとlauncherはGitメタデータ内の固定コピーで実行し、実効core.hooksPath・実行属性・内容の指紋を照合する。グローバル設定・ホームは変更しない。worktree固有設定が有効なら、そのworktreeの導入状態を確認する。

新規導入・明示更新時に接続する。確認だけの`--check`は書換えない。CloudのGitメタデータが新しい場合は`--cloud --project`で固定版のguardを接続し直す。旧固定版にsecurityモジュールがなければsupported=falseを返し、保護済みとしない。

```sh
python3 .harness/security.py verify /absolute/path/to/project
python3 .harness/security.py check-index /absolute/path/to/project
```

`git_security_guard.verified=true`は実効接続と固定コピーの検証であり、その時点の全コードの安全性判定ではない。改変・更新中断を検出したら拒否する。同じ固定版の破損を自動上書きせず、残った設定と指紋を調べて本人が指定した範囲で明示修復する。

## 保証する範囲

接続を検証したGit経路と定義した秘密情報検査は、両環境で同じコードを使う。任意コードの無欠陥、未知の秘密形式、画像等に隠された情報、利用者自身の`--no-verify`・設定変更・Git plumbingによる迂回まで無条件保証しない。安全性・権限・データ破壊等は必須の独立レビューと対象の検証も使う。

Windows向けlauncherはGit for Windowsのshellと実Pythonパスを使う。Linuxの空白・日本語・引用符・worktree試験をWindows実機確認の代わりにしない。
