import json, hashlib, subprocess
from pathlib import Path
root=Path('.harness/changes/ui-b-no-percent')
d=json.loads((root/'design.json').read_text());u=d['ui']; cases={c['id']:c for c in u['cases']}
receipt_path=root/'evidence/5ad3a5a87f844375a18c5ba1ec39dab3.json'
r=json.loads(receipt_path.read_text())
metrics={s:json.loads((root/f'evidence/5ad3a5a87f844375a18c5ba1ec39dab3/summary-browser/{s}.json').read_text()) for s in ['mobile-320','desktop-1280']}
fp=json.loads(subprocess.check_output(['python3','.harness/harness.py','fingerprint','ui-b-no-percent'],text=True))
assert all(fp[k]==r[k] for k in ['project_digest','artifacts_digest'])
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='2b2d15fd37e51af2f5b59edcd50c258b49905ea8'
observations={
'meaning':['本人原文とB案・現在の320/1280画像を設計より先に観察した。差額330、合計170、編集可能な目標500を別の金額として識別できる。研究の残数10/5と取得/使用0は異なる役割で、研究の枠は支出の枠から独立する。','価格20%引きは割引条件であり、削除要求の集計達成率と区別した。4 visual caseのsummaryBox/spendingBoxを両幅で独立に評価し、金額・編集と研究/支出の区別が読めた。'],
'structure':['320pxは集計→研究→再抽選→音符5個→15個、1280pxは全幅の集計の下に研究を左、支出を右に置く。B案の比較軸と一致する。','DOM順も差額・合計・目標で、研究と支出がcompact-workspaceの兄弟。全幅でsummary/researchはstatic、独自300px高でscrollY200に対しsummaryのyが200移動した。'],
'reuse':['dist/counter.jsのCOUNTERS、researchUsage、setCount、保存形式は差分なし。既存input/buttonとrenderを再利用し、研究の残数・超過だけ同じ計算結果のDOMへ接続した。','長数の既存longクラスをCSS :has()で2段に接続し、新しい同期や別モデルを追加していない。dist/docsはreceiptのpages-syncで一致。'],
'visual_hierarchy':['差額は紫35/32pxで上位、合計と目標は25/22px、研究残数23/25pxを取得/使用19/18pxより大きくした。操作ボタンのSVGは14pxで、タッチ領域を大きな記号そのものへ拡大していない。','灰の研究、橙の再抽選、紫の音符は見出しと境界・所属も伴う。B案の枠と比較順を保ち、達成率削除で空の百分率行を残さない。'],
' tokens':['actual appColor=rgb(39,42,59)、差額valueColor=rgb(113,97,201)がRegistryのJSON scalarと一致し、対象の役割も通常本文と差額に対応する。','実際のsummary-tokens.jsonは色2項目のみ。ハッシュを秘密情報と誤認した除外は当該行・完全一致の2パス・generic-api-keyのANDだけで、別値/パス/PATの検出を独立に再実行した。'],
'density_typography':['320pxの集計149.25px、アプリ1043.984375px、ラベル11px/行高18px、目標欄126×44px、研究残数23px。1280pxは集計109px、アプリ531px、目標欄290.515625×33px、研究残数25px。単位・割引・研究条件は最小11px。','この用途では短い識別ラベルを11px、金額と残数を大きくするB案の密度が成立する。PC音符28×32pxと14px記号は価格カードを圧迫せず、touchでは40×40pxを確保する。独自coarse検査で全幅全入口を再確認した。'],
'copy':['全159itemを現在のtext/target/surfaceと対応するreceiptの全状態inventoryへ照合し、実出典のpointerも解決して正確な文言一致を確認した。値、単位、対象名、短い操作・状態・エラー名であり、本文の補足説明はない。','body/qa/tooltip/accessible_nameの全4面をproviderのTreeWalker・title/data-tooltip・AX name/description/value取得と照合した。qa/tooltipは全8状態×両幅で空。ARIAの進捗値34%/100%は既存progressbarのデータで可視の達成率表示ではない。'],
'states_actions':['receiptでは目標170の到達0と100%バー、未設定時の非表示、目標100で超過-70、保存失敗でも170の計算を継続する。独自操作では170/500のバー幅比0.34が一致し、可視達成率はない。','全9カウンターの増減・直接入力・研究上限超過・保存/再読込・目標を保つリセットを独自coarse4幅でも確認した。同期ローカル処理なので送信前取消と遅延応答は存在せず、各クリックを1回として数える判定は妥当。'],
'accessibility':['receiptのラベル/AX、Tab/focus、幅境界390/479/480/599/600/768/959/960、640px×DSF2の200%相当リフローと操作は成功。見える目標ラベルと編集印、フォーカス輪郭を実画像で確認した。','独自coarse320/600/960/1280で全9入口にtap・入力し、長い値でも横はみ出しなし。研究MAX_SAFE_INTEGERは0残数と正しい超過値を折返しで表示する。実機の支援技術やnative browser zoomの全面適合は主張しない。'],
'scope_connections':['変更は既存1画面のDOM/CSSと研究render。COUNT ID、価格、10/5上限、保存キーを維持し、ローカルstorageへ本接続している。独自検査で4幅とも保存/再読込・reset後の目標500と全回数0を確認。','秘密情報除外の追加は検出された配色hashの根因へ限定され、検査スクリプトは許容12・検出必須14。公開・PR・マージ・commit/pushや共通基盤変更は実行していない。']}
observations['tokens']=observations.pop(' tokens')
review={'reviewer':'codex-independent-reviewer-review_ui_b','context':'/root/review_ui_b','decision':'passed','summary':'B案の両幅実装、固定表示撤回、可視達成率削除を確認した。計算・価格条件・進捗バー・状態・保存互換性を維持し、具体的な要求違反は見つからなかった。','checked_requirements':['adopt-b','no-fixed-percent','preserve-behavior','verified-delivery'],'findings':[],'limitations':['独立レビューは実装履歴を複製せず委譲された別エージェントコンテキストで行った。同じモデルの別コンテキストであり、記録やCLI readyだけを独立性・意味理解の証明とはしない。','自動試験はChromiumとエミュレーション。200%はviewport640/DSF2による相当リフローであり、native browser zoom・実機支援技術の全面適合は未検証。','指定によりadvance、commit/push、PR作成、公開、マージは未実行。verified-deliveryの安全なリモート保存は親の後続工程で行う。'], 'project_digest':fp['project_digest'],'artifacts_digest':fp['artifacts_digest'],'base_sha':'2b2d15fd37e51af2f5b59edcd50c258b49905ea8','intent_review':{'purpose':{'status':'passed','evidence':'原文を画像観察前に読んだ。B案の研究/支出の所属と残数優先表示が両幅に移り、最新訂正どおり固定表示と可視達成率が消えた。evidence/independent-initial-observation.jsonと現在のreceipt、独自reviewer-browser/results.json。'},'sources':[{'source':'SRC-1','status':'passed','evidence':'B案mobile/desktop参照画像と現画面を先に見た。320は集計→研究→支出、1280は集計下で研究/支出の左右。研究残数と取得/使用を別表示し、価格は通常→20%引き→半額。'},{'source':'SRC-2','status':'passed','evidence':'元のsticky文は削除されず引用として保持され、後続SRC-3による撤回としてbinding=false。独自4幅でsummary/researchのstaticとスクロール追従を測り、撤回を実装した。'},{'source':'SRC-3','status':'passed','evidence':'summaryとresearchを全幅で固定しない。低い300pxウィンドウでscrollYとsummary位置変化が逆符号同量になり、視覚表示を固定するJSもない。'},{'source':'SRC-4','status':'passed','evidence':'#progress-percentを削除し、renderの可視百分率代入を削除。bodyの%は価格条件20%引きのみ。進捗バーと到達/超過/未設定、ARIA値は保持し、原指示の対象を価格条件へ拡張していない。'}],'minimality':{'status':'passed','evidence':'既存COUNTERS/state/researchUsageと全イベント・保存キー・価格モデルを維持し、B案のDOM/CSSと表示更新だけを変更。sticky機構は削除し新しい同期機構・依存・Q&Aを追加しない。Gitleaks対処は同じ公開色hashの2完全一致パスとキー行だけをAND除外し、対照試験を加えた。'}},'independent_observation_ref':'.harness/changes/ui-b-no-percent/evidence/independent-initial-observation.json','additional_verification':{'browser_results':'.harness/changes/ui-b-no-percent/evidence/reviewer-browser/results.json','secret_results':'.harness/changes/ui-b-no-percent/evidence/reviewer-secret-check.json','comment_audit':{'agent':'/root/review_ui_b/comments_audit','added_comment_lines':0,'lint_typescript_suppressions':0,'findings':[]},'coarse600_diagnosis':{'evidence':'.harness/changes/ui-b-no-percent/evidence/reviewer-browser/coarse600-screenshot-diagnosis.json','observation':'初期検査のfull_page撮影はPlaywright側でpointer:coarseをtrueからfalseへ変え、600pxのbuttonを40pxから32pxにした。reloadでcoarse=true/40pxへ戻った。撮影の前後と実mediaを分けて再現した。viewport撮影に直した独自検査でcoarse=true・40×40pxと実操作を再確認する。','product_defect':False}},'ui':{'status':'passed','receipt_ref':{'path':receipt_path.as_posix(),'sha256':hashlib.sha256(receipt_path.read_bytes()).hexdigest()},'checked_scenarios':[s['id'] for s in u['scenarios']],'observations':[],'principles':[],'expectation_assessments':{'measurements':[],'controls':[],'copy':[]},'copy_surface_inventory':[]}}
for scenario in u['scenarios']:
 s=scenario['id'];m=metrics[s]
 review['ui']['observations'].append({'scenario':s,'understood':scenario['meanings'],'excess':[],'missing':[],'assessment':('320pxでは差額を先頭、研究の残数を支出から分離し、その下で橙の再抽選・紫の音符価格が縦に続く。' if s=='mobile-320' else '1280pxでは全幅の差額/合計/目標と、研究を左・支出を右に置くB案の階層が読める。')+f' 集計{m["summaryHeight"]}px、アプリ{m["appHeight"]}px。達成率数値なし、価格20%引きあり、通常スクロール。進捗・到達・未設定・保存失敗の状態とラベルを画像/実測に照合した。'})
for p in u['principles']:
 review['ui']['principles'].append({'id':p['id'],'case_ids':p['case_ids'],'observations':observations[p['id']],'status':'passed','excess':[],'missing':[]})
measure_reasons={'labelSize':'短い日本語の項目ラベルはB案と同じ控えめな11pxで金額より優先度が低く、名称は省略されない。12px上限も金額と階層を分ける範囲として妥当。','labelLine':'18px行高は11pxラベルと11px編集印を切らずに収め、余分な説明行を作らない。','rowHeight':'ラベル18pxと入力44/33pxを同じ金額群に収めるための高さ。モバイル62px、PC51pxで密度と入力を両立する。','targetWidth':'モバイル126pxとPC290.515625pxは通常値を比較しやすくし、安全整数16桁は既存fitNumberで収める。研究/金額の表示領域を奪わない。','summaryInset':'支出内の12pxは再抽選と音符を外の研究から分け、カードと枠を接触させない最小の余白。13px上限は用途に合う。','summaryHeight':'通常fixtureで149.25/109pxに収まり、数値行を削除したB案をコンパクトに保つ。状態増加は別scenarioの文言/操作で検証される。','appHeight':'320pxで1044px弱は9カウンターと研究を比較できるB案の密度で、1050px上限に収めるためにラベルや操作を削っていない。PC531pxも単画面作業に合う。','unitMinFont':'単位は11pxで、18/23pxの価格数値と隣接する短い語。数値を主にする階層を保ち、見分ける名前は消えない。','discountMinFont':'通常/20%引き/半額は各11pxの短いバッジ。色を外しても文言で区別でき、全カードを比較するB案の密度に合う。','researchMinFont':'上限・条件・単位は11px以上で、残数の主数字23/25pxと取得/使用済み入力を補う対象ラベル。','remainingNumberSize':'残数は主に読む数として23/25px、取得/使用済みの入力18/19pxより上位。22〜26pxはモックと作業用途を保ち、記号や見出しの過大化はない。'}
for p in u['principles']:
 if p['id']=='density_typography':
  for m in p['details']['measurements']:
   values={c:metrics[cases[c]['scenario']][m['id']] for c in m['case_ids']}
   review['ui']['expectation_assessments']['measurements'].append({'id':m['id'],'case_ids':m['case_ids'],'expectations':{c:cases[c]['expectation'] for c in m['case_ids']},'bounds_appropriate':True,'evidence':f'{m["target"]}: receipt実測 '+json.dumps(values,ensure_ascii=False)+'。初期画面と独自4幅操作に照合。','rationale':measure_reasons[m['id']]})
  for control in p['details']['controls']:
   ids=set(control['activation_case_ids'])
   for part in ['visual','hit']:
    ids.update(control[part]['width_case_ids']);ids.update(control[part]['height_case_ids'])
   values={c:next(result['actual'] for sc in r['ui']['scenarios'] for result in sc['case_results'] if result['id']==c) for c in ids}
   cid=control['id']
   rationale='目標欄は値と編集印を持つネイティブ入力で、モバイル44px高・PC33px高の面自体が起動する。' if cid=='edit-target-control' else '回数だけをリセットする短い操作名と36/40px高の面を保ち、目標値を残すことは実操作と再読込で確認した。' if cid=='reset-counts' else '回数入力は同じ対象の増減ボタンに挟まれ、通常の数字を表示する幅と32/40px高を確保する。5桁以降は2段で読み取り幅を確保し、16桁研究値も読めた。' if cid.endswith('-input') else '14pxの＋/−記号と、PC音符28×32px・その他32px・狭幅/touch40pxのボタン面は別の寸法。B案の価格比較と誤操作回避を両立し、さらに大きい記号にする必要はない。'
   review['ui']['expectation_assessments']['controls'].append({'id':cid,'case_ids':sorted(ids),'expectations':{c:cases[c]['expectation'] for c in ids},'visual_appropriate':True,'hit_appropriate':True,'activation_associated':True,'evidence':control['hit']['target']+'の幅/高さとactivationの実測 '+json.dumps(values,ensure_ascii=False)+'。独自coarse4幅でも同対象をtap/入力して状態・保存を確認した。','rationale':rationale})
copy=next(p['details'] for p in u['principles'] if p['id']=='copy')
def pointer(ref):
 value=json.loads(Path(ref['path']).read_text())
 for k in ref['pointer'].split('/')[1:]:
  k=k.replace('~1','/').replace('~0','~');value=value[int(k)] if isinstance(value,list) else value[k]
 return value
purpose_reason={'identity':'対象・単位・項目の名前を示す。削ると値や所属を識別できず、短い名前と配置で足りる。','data':'現在値または状態に対応する実データ。削ると回数・金額・上限・進捗の事実を失う。','action_label':'何を変える操作かを識別する短い操作名。＋/−記号だけのボタンには対象と方向の読み上げ名が必要。','state_label':'未設定/到達/超過の状態を短く命名する。色や0だけでは区別できない状態を表し、手順説明は付けない。','error_label':'無効な値の数値制約または保存失敗の状態名。説明文や新しいQ&Aへ置換せず、状態の最小の名称を保つ。'}
for item in copy['items']:
 assert pointer(item['source_ref'])==item['text']
 matches=[]
 for s,m in metrics.items():
  for k,v in m.items():
   if k=='copyItems' or k.startswith('copyItems'):
    matches.extend(f'{s}/{k}' for x in v[item['surface']] if x['text']==item['text'] and x['target']==item['target'])
 assert matches,item['id']
 reason=purpose_reason[item['purpose']]
 if item['text']=='20%引き':reason+=' これは価格区分であり、本人が削除した集計達成率には該当しない。'
 if item['surface']=='accessible_name': reason+=' 可視文言の代用として隠した説明ではなく、その操作/領域/値のアクセシブルな名前または値。'
 if item['text'] in ['目標コインから消費コイン合計を引いた差額','素質再抽選と音符セット購入の消費コイン合計']:reason+=' 金額が何を集計するかを識別する名詞句で、操作手順や背景説明の文章ではない。'
 review['ui']['expectation_assessments']['copy'].append({'id':item['id'],'case_ids':item['case_ids'],'text':item['text'],'purpose':item['purpose'],'source_ref':item['source_ref'],'purpose_appropriate':True,'source_supported':True,'necessary':True,'redundancy_justified':True,'observed_purpose':item['purpose'],'observed_surface':item['surface'],'supplemental_prose':False,'wording_evidence':f'{item["target"]}に「{item["text"]}」を観測。'+('本文で直接値・ラベルを表示。' if item['surface']=='body' else 'AX name/description/valueとして対象へ結ぶ。'),'evidence':f'現在receiptの{sorted(set(matches))}でtextとtargetが一致。source_refの実JSON pointerも同じ文言。','rationale':reason+' 同じ語の反復は別価格/別研究/別操作対象の名前や状態別データであり、同じ対象への補足説明の重ね書きはない。'})
for surface,ids in copy['surface_inventory_case_ids'].items():
 review['ui']['copy_surface_inventory'].append({'surface':surface,'case_ids':ids,'complete':True,'no_hidden_explanations':True,'evidence':f'両幅の通常/到達/入力エラー/長値/未設定/保存失敗/回数エラー/resetの{surface}全inventoryを確認。'+('全て空配列で、本文説明の移設はない。' if surface in ['qa','tooltip'] else 'TreeWalker/値' if surface=='body' else 'AX name/description/valueとaria-valuetextのDOM補完')+'。providerの取得対象を狭めるselectorや除外による未申告文言はなく、本文と対象の短い名前・データのみ。'})
(root/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'decision':review['decision'],'measurements':len(review['ui']['expectation_assessments']['measurements']),'controls':len(review['ui']['expectation_assessments']['controls']),'copy':len(review['ui']['expectation_assessments']['copy']),'path':str(root/'review.json')},ensure_ascii=False))
