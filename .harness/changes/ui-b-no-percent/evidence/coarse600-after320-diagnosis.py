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
from pprint import pprint
results=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    prior=browser.new_context(viewport={'width':320,'height':720},has_touch=True,is_mobile=False)
    pr=prior.new_page();pr.goto(url);pr.wait_for_timeout(500);prior.close()
    for mobile in [False,True]:
        ctx=browser.new_context(viewport={'width':600,'height':720},has_touch=True,is_mobile=mobile)
        page=ctx.new_page();page.goto(url);page.wait_for_timeout(500)
        def observe(stage):
            result=page.evaluate("""() => {const el=document.querySelector('[data-id=trait3] .increment'); const matches=[];function scan(rules,media=[]){for(const r of rules){if(r.type!==1&&r.cssRules)scan(r.cssRules,[...media,r.conditionText]);else if(r.selectorText&&el.matches(r.selectorText)&&r.style.width)matches.push({selector:r.selectorText,width:r.style.width,height:r.style.height,media:media.map(q=>({q,matches:matchMedia(q).matches}))})}}for(const s of document.styleSheets)scan(s.cssRules);return {innerWidth,clientWidth:document.documentElement.clientWidth,coarse:matchMedia('(pointer: coarse)').matches,coarse600:matchMedia('(pointer: coarse) and (min-width:600px)').matches,computed:{width:getComputedStyle(el).width,height:getComputedStyle(el).height},matches}}""")
            result.update({'stage':stage,'is_mobile':mobile});results.append(result)
        observe('initial')
        page.reload();page.wait_for_timeout(500);observe('reload')
        page.locator('[data-id=trait3] .increment').tap();page.wait_for_timeout(100);observe('tap')
        page.set_viewport_size({'width':601,'height':720});page.wait_for_timeout(100);observe('resize601')
        page.set_viewport_size({'width':600,'height':720});page.wait_for_timeout(100);observe('resize600')
        ctx.close()
    browser.close()
server.shutdown()
(OUT/'coarse600-after320-diagnosis.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
pprint(results)
