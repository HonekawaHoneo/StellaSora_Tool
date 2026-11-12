import json, threading, functools, hashlib
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright
ROOT=Path.cwd()
OUT=ROOT/'.harness/changes/ui-b-no-percent/evidence/reviewer-browser'
OUT.mkdir(exist_ok=True)
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'dist')))
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}/'
key='stella-sora-star-tower-v1'
results=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    for width in [320,600,960,1280]:
        ctx=browser.new_context(viewport={'width':width,'height':720},has_touch=True,is_mobile=False)
        page=ctx.new_page();page.goto(url);page.evaluate('(key)=>localStorage.setItem(key,JSON.stringify({target:500,counts:{reroll:2,note90:1}}))',key);page.reload()
        page.wait_for_function('document.querySelector("#remaining").textContent === "330"')
        page.wait_for_timeout(300)
        record={'width':width,'coarse':page.evaluate('matchMedia("(pointer:coarse)").matches'),'media':page.evaluate('({innerWidth,clientWidth:document.documentElement.clientWidth,coarse600:matchMedia("(pointer:coarse) and (min-width:600px)").matches,sheets:[...document.styleSheets].map(s=>({href:s.href,coarse:[...s.cssRules].filter(r=>r.conditionText?.includes("pointer")).map(r=>({condition:r.conditionText,matches:matchMedia(r.conditionText).matches}))}))})')}
        assert record['coarse']
        page.screenshot(path=str(OUT/f'coarse-{width}.png'),full_page=False)
        record['initial']=page.evaluate("() => { const box=s=>{const b=document.querySelector(s).getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height}}; return {coarse:matchMedia('(pointer:coarse)').matches,coarse600:matchMedia('(pointer:coarse) and (min-width:600px)').matches,body:document.body.innerText, summary:box('.summary'),research:box('.record-group'),spending:box('.spending'),overflow:document.documentElement.scrollWidth>innerWidth,progress:document.querySelector('#progress-fill').getBoundingClientRect().width/document.querySelector('#progress').getBoundingClientRect().width,positions:['.summary','.record-group'].map(s=>getComputedStyle(document.querySelector(s)).position),buttons:[...document.querySelectorAll('.count-button')].map(e=>{const r=e.getBoundingClientRect();return {width:r.width,height:r.height}})} }")
        assert record['initial']['coarse']
        assert not record['initial']['overflow']
        assert record['initial']['positions']==['static','static']
        assert abs(record['initial']['progress']-.34)<.002
        print('width-start',width,flush=True)
        assert all(b['height']>=39.9 and b['width']>=39.9 for b in record['initial']['buttons'])
        ids=['trait3','enhancement2','reroll','note90','note72','note45','note400','note320','note200']
        record['allEntrypoints']=[]
        for id in ids:
            inp=page.locator('#count-'+id); prior=int(inp.input_value())
            page.locator('[data-id='+id+'] .increment').tap();assert int(inp.input_value())==prior+1
            page.locator('[data-id='+id+'] .decrement').tap();assert int(inp.input_value())==prior
            inp.fill('12345'); inp.press('Tab');assert inp.input_value()=='12345'
            fit=inp.evaluate("el=>{const c=document.createElement('canvas').getContext('2d'),s=getComputedStyle(el); c.font=`${s.fontWeight} ${s.fontSize} ${s.fontFamily}`; return {value:el.value,width:el.clientWidth,font:s.fontSize,text:c.measureText(el.value).width}}")
            assert fit['text']<=fit['width']+1
            record['allEntrypoints'].append({'id':id,'increment':True,'decrement':True,'directLong':fit})
            inp.fill(str(prior));inp.press('Tab')
        for id,excess in [('trait3','9,007,199,254,740,981'),('enhancement2','9,007,199,254,740,986')]:
            inp=page.locator('#count-'+id);inp.fill('9007199254740991');inp.press('Tab');card=page.locator('[data-id='+id+']')
            assert card.locator('.research-excess').inner_text()=='超過 '+excess+'回'
            assert card.locator('.remaining-number').inner_text()=='0'
        record['researchMax']=page.locator('.record-group').evaluate("e=>{const r=e.getBoundingClientRect(); return {text:e.innerText,width:r.width,scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,items:[...e.querySelectorAll('.research-remaining')].map(x=>({width:x.clientWidth,scrollWidth:x.scrollWidth,height:x.clientHeight}))}}")
        assert all(x['scrollWidth']<=x['width'] for x in record['researchMax']['items'])
        page.screenshot(path=str(OUT/f'research-max-{width}.png'),full_page=False)
        page.reload();assert page.locator('#count-trait3').input_value()=='9007199254740991'
        page.locator('#reset').tap();assert page.locator('#target').input_value()=='500'
        assert all(page.locator('#count-'+id).input_value()=='0' for id in ids)
        page.reload();assert page.locator('#target').input_value()=='500'
        assert all(page.locator('#count-'+id).input_value()=='0' for id in ids)
        record['storageResetReload']=True
        page.set_viewport_size({'width':width,'height':300});page.evaluate('scrollTo(0,0)');before=page.locator('.summary').bounding_box()['y'];page.evaluate('scrollTo(0,200)');after=page.locator('.summary').bounding_box()['y'];scroll=page.evaluate('scrollY');assert abs(after-before+scroll)<1 and scroll>0
        record['scroll']={'before':before,'after':after,'scroll':scroll}
        results.append(record);ctx.close()
    browser.close()
server.shutdown()
(OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':True,'widths':[r['width'] for r in results],'entrypoint_checks':sum(len(r['allEntrypoints']) for r in results),'research_max_safe_integer':True,'storage_reload_reset':True,'normal_scroll':True},ensure_ascii=False))
