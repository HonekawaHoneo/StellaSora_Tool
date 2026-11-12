# マージ前CIの秘密情報検出

現在の依頼は「マージして」。既存のcompletion=reviewやGitHub保護設定は変更しない。

GitHub PR#4、head d8db514、base main273e4a。Test/public assetsとCodeQLは成功、Secret scanは22件で失敗。Gitleaks8.30.1の公式固定版とSHA256を照合し、全Git履歴で再現した。

21件は7種類のUUIDv4 hexで、全て実際の工程レコードに対応する。生成元は.harness/execution.pyのuuid.uuid4().hexで、工程の発言・Skill適用の照合用であり、ネットワーク認証やAPI権限を持たない。残り1件はdevelopment/ui/summary-tokens.jsonのファイルSHA256で実ファイルの値と一致。実秘密・不明値は0。

既定ルールは維持する。generic-api-keyの例外は公開工程のcanonical token行をUUIDv4 version/variant・artifact pathへ限定し、eventはskill_application_verifiedの完全な行形式だけにする。snapshotは従来同様に固定path/key/SHA256だけを許容する。無関係のkey/path/値、非v4、イベントへの別key混入、異なるSHA、他の既定ruleを実Gitleaksで検出する対照試験を加える。保護無効化・全面パス除外・検出結果の握りつぶしは行わない。
