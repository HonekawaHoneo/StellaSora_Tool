# Windowsで導入・検証する

0.17.0の受入は、入力別のSkill読出し・適用、厳格工程、完了時の自動保存、UIのobject-first、品質分類も必須にする。旧版の6分類だけの記録は、新機能のWindows確認として受理しない。

0.16.0のGit保護はGit for WindowsのHook shellと実Pythonパスを使う。日本語・空白・引用符、既存のshell/Python/Node/.exe Hook、worktreeごとのcore.hooksPath、commit/merge/cherry-pick/amとpushの拒否・正常保存を実Windowsで確認する。検証にはtest_security.py、test_secure_save.py、test_cloud_activation.pyを含め、Linux成功を実機確認としない。登録checksの既定時間上限はなく、python/python3は起動中のPythonへ解決する。検証は依頼または既存必須チェックの範囲で行い、Actions自動起動は増やさない。

0.12.0はWindows向けの排他制御、PowerShellコマンド、UTF-8、ファイル属性、Codex起動、検証process停止を追加する。Windows実機の接続先がないため、この変更ではWindows実行済みとは報告しない。Linux上の回帰とPowerShell 7の試験はWindows実機検証の代わりにはしない。

## 前提

Windows 10/11のネイティブ環境、CPython 3.10+、Git、Windows PowerShell 5.1またはPowerShell 7を使う。WSLは別のLinux環境として扱う。`py -3`がない場合は実際の`python.exe`へ置き換える。プラグイン直接起動のcommand_windowsはpy launcherを必要とし、環境インストーラは実行したbase Pythonの実パスを登録する。Codex CLIはHookをサポートする版が必要で、試験したCLIは0.159.2。公式npm版の場合はNodeと隣接する@openai/codex/bin/codex.js、またはnativeのcodex.exeを使う。不明なcmd shimをshell=Trueで実行しない。

WindowsでのGit改行変換から固定hashを守るため.gitattributesを同梱する。古い作業コピーが既にCRLFへ変換されている場合は、変更を保存したうえで別の新しい取得先を使う。既存ファイルを強制復元して個人変更を消さない。短い取得先の例:

```powershell
# PowerShell 5.1も、このセッション内のnative入出力をUTF-8へ揃える。
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
git -c core.autocrlf=false clone https://github.com/HonekawaHoneo/CodexEnvSet.git C:\src\CodexEnvSet
Set-Location C:\src\CodexEnvSet
py -3 -X utf8 scripts/install_environment.py --project 'C:\src\対象 アプリ'
```

実効homeはCODEX_HOMEまたは$HOME/.codex、Skillの既定先は$HOME/.agents/skills。明示した別homeを実効読込先と偽らない。既存config・認証・個人profile・他のHook・対象の固定版は保持する。導入先が読み取り専用、長すぎるパス、管理ポリシーでPowerShellやPythonを実行できない場合は原因を解決してから再確認する。ACLやExecutionPolicy、Hookの信頼設定を自動変更しない。

## 有効化する

初回は通常ready=false/終了コード3。本人がCodexの`/hooks`またはSettings > Hooksでコマンドを確認・承認し、対象cwdで新規開始/再開する。次の別nativeツールから現在session IDと直前のnext_activation_tokenをリテラル指定する。

```powershell
Set-Location 'C:\src\対象 アプリ'
py -3 -X utf8 C:\src\CodexEnvSet\scripts\install_environment.py --check --project 'C:\src\対象 アプリ' --session-id CURRENT_ID --activation-token NEXT_TOKEN
```

NEXT_TOKENは32桁の小文字16進数に置換する。シェル変数・式では事前Hookが照合できないため、新しい値を直接指定する。ready=true/host_activation=verified/終了コード0を確認する。古い成功、無効/未承認Hook、別sessionを流用しない。cmd.exeから環境の設定・導入も実行できるが、返却されたbootstrap_commandはPowerShell向けであり、PowerShellへ貼り付ける。

## 旧版を明示更新する

0.11以前にはPOSIX専用のruntimeがあり、Windowsでそのまま実行できない。既存対象の版は自動更新しない。新しい取得元から本人が実際の固定版を指定する。

```powershell
Set-Location C:\src\CodexEnvSet
py -3 -X utf8 scripts/install.py --project 'C:\src\対象 アプリ' --update-from 0.11.0
py -3 -X utf8 scripts/install_environment.py --project 'C:\src\対象 アプリ'
```

環境のHookコマンドが変わるため再承認し、必要なら環境を保存/Publishして新しいチャットで再確認する。破損対象のcwdで修復コマンドまで拒否された場合は、信頼した取得元のcwdから対象を明示して修復する。既存のWindows非対応版への--check失敗を、新版の接続成功と読み替えない。

## Windows上で受入試験する

取得元の作業コピーで次を実行する。検証スクリプトはテスト専用temp環境を使い、実ユーザーのCodex設定・認証・信頼承認は更新しない。環境変数は実行後に戻す。実行ポリシーでスクリプトが拒否される場合は本人の管理手順に従う。Bypassを指定して回避しない。

```powershell
Set-Location C:\src\CodexEnvSet
& .\scripts\verify_windows.ps1
& .\scripts\verify_windows.ps1 -NativeHooks
```

- coreではimport、別processとのlock競合/解放、日本語・空白・記号のパス、UTF-8 BOM、設定保持、mode、process tree停止、PowerShell stdin/終了コード、autocrlfとsession証跡を検査する。
- -NativeHooksは公式CLIとローカルHTTP/SSE model fixtureを使い、未承認の未実行、承認済みfixtureのready=trueとtoken再利用拒否、破損後のnative PreToolUse拒否を検査する。実モデルのAPIには接続しない。承認は使い捨てfixtureだけに設定し、実利用者の承認を代行しない。fixture子Codexはsandbox=danger-full-accessで、そのローカルmodelが発行するテストコマンドだけを一時領域で実行する。
- 実行結果とログは表示されたtemp Evidenceディレクトリへ保存する。`-EvidenceRoot`にはcheckout外の親ディレクトリを指定する。毎回異なるGUIDの子ディレクトリを作り、開始時に確認状態をfalseで記録する。過去の成功やログは上書きせず、再実行失敗の結果へ流用しない。
- `result.json`はrun ID、実際のOSとPythonとGitの版・実行パス、Git revision、ソース全ファイルのSHA-256 manifestとそのdigest、開始・終了時刻を持つ。各checkは同じrun IDとargv、開始・終了時刻、終了コード、skipの有無、ログのSHA-256を持つ。未実施はpending、実行中はrunning、失敗やskipはfailedとして残す。全必須checkを完了して指紋を再照合したときだけcompleteになる。
- skipや失敗は確認済みにしない。`-NativeHooks`なしの結果は`requested_native_hooks=false`と`native_fixture_verified=false`であり、実利用環境の`user_environment_activation`も常に別途確認する。

固定bundleにはテスト一式を配布しないため、このscriptは取得元checkoutで実行する。従来の全テストにはPOSIX/過去版のfixtureもある。focusedの成功をWindowsで全テストが成功したと報告しない。Windows実機が使えるようになった際は、上記ログ・OS/Python/Codex版と実利用環境の有効化結果を保存する。

受入記録の利用前にも、対象checkoutから次を実行する。`EVIDENCE_DIRECTORY`は表示されたGUIDの子ディレクトリへ置き換える。`require_native=True`はnative fixtureまで必要な場合に使う。coreだけを確認する場合は`False`にする。

```powershell
py -3 -X utf8 -c "import sys;from pathlib import Path;sys.path.insert(0,'runtime');import common;common.validate_platform_receipt(Path.cwd(),Path(sys.argv[1]),require_native=True)" 'EVIDENCE_DIRECTORY'
```

ソースの追加・削除・内容変更、ログの不足・改変、別runのcheck混入、必須checkの不足、中断・失敗・skipは記録を失効させる。固定した有効日数は設けず、同じソースと実行ログの一致を必要条件とする。checkoutへ変更が入った後は実Windowsで再実行する。

この検査はJSONの整合性と鮮度を調べる。JSON内のWindowsという文字列や自己申告を実機実行の認証には使わない。Linux上のreceipt回帰試験もWindowsの受入試験ではない。今回の作業環境には実Windows接続先がなく、PowerShellスクリプトとnative HookのWindows実行は未確認。Windowsホストでの上記実行結果と実利用環境の有効化が残る受入条件である。

## 任意の構造検査

固定版jscpd 5.4.0/Tach 0.35.3にはWindows x64/arm64のwheelがあり、requirements-quality.txtにそのhashも含まれる。実際のWindowsでの解析成功は別途確認が必要。先に[構造検査の設定](structural-quality.md)を対象へ取り込み、変更単位をimplementationまで進める。検査用CPython 3.12のvenvを作り、そのpython.exeをproject.jsonのcheck argvへ設定する。既存の独自設定を丸ごと置換しない。

```powershell
Set-Location 'C:\src\対象 アプリ'
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --require-hashes -r .harness\templates\requirements-quality.txt
$previousQualityPath = $env:PATH
try {
    $env:PATH = (Join-Path (Get-Location) '.venv\Scripts') + [IO.Path]::PathSeparator + $previousQualityPath
    & .\.venv\Scripts\python.exe -X utf8 .harness\harness.py --json run CHANGE_ID
} finally {
    $env:PATH = $previousQualityPath
}
```

GitHub Actionsは通常起動しない。既存必須チェックまたは利用者の明示依頼がある場合だけ、既存の手動CI・本人承認へ接続する。
