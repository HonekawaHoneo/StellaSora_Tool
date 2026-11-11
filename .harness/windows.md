# Windowsで導入・検証する

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
- 実行結果とログは表示されたtemp Evidenceディレクトリへ保存する。-EvidenceRootで親ディレクトリを指定しても、毎回異なるGUIDの子ディレクトリを作り、開始時に確認状態をfalseで記録する。過去の成功やログは上書きせず、再実行失敗の結果へ流用しない。skipや失敗は確認済みにしない。-NativeHooksなしの結果はnative_fixture_verified=falseであり、実利用環境のuser_environment_activationも常に別途確認する。

固定bundleにはテスト一式を配布しないため、このscriptは取得元checkoutで実行する。従来の全テストにはPOSIX/過去版のfixtureもある。focusedの成功をWindowsで全テストが成功したと報告しない。Windows実機が使えるようになった際は、上記ログ・OS/Python/Codex版と実利用環境の有効化結果を保存する。

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
