import asyncio, json, time
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
T0=time.time()
def plan(stage):
    # stage 0..6 : otp1 then otp2
    st=[('waiting','waiting'),('draining','waiting'),('installing','waiting'),('checking','waiting'),('done','draining'),('done','installing'),('done','done')][stage]
    now=time.time()
    steps=[{'name':'otp1','state':st[0],'at':T0+stage*10+1,'said':'otp1 '+st[0]},
           {'name':'otp2','state':st[1],'at':T0+stage*10+2,'said':'otp2 '+st[1]}]
    for s in steps:
        if s['state']=='installing': s.update(part=2, part_words='nginx')
    state='done' if stage==6 else 'running'
    return {'id':'P2','version':'9.9.9','at':T0,'state':state,'drain_s':20,'steps':steps}
OLD={'id':'P1','version':'9.9.8','at':T0-86400,'state':'done','steps':[{'name':'otp1','state':'done','at':T0-86000},{'name':'otp2','state':'done','at':T0-85900}]}
seq=[]  # what each poll gets
stage=0
script=['A0','A1','net','B0','502','A2','401','B1','A3','oldplan','A4','net','net','B3','A5','hide','A6','B5','A6','A6']
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1000})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        base=await pg.evaluate("api('upgrade')")
        reloads=[]; pg.on('framenavigated', lambda f: reloads.append(f.url) if f==pg.main_frame else None)
        it={'i':0}; who401={'n':0}
        async def route(r):
            url=r.request.url
            if 'api=whoami' in url and who401['n']>0:
                who401['n']-=1; return await r.fulfill(status=401, body='{"ok":false,"error":"x"}', content_type='application/json')
            if 'api=upgrade' not in url or r.request.method!='GET': return await r.continue_()
            i=it['i']; it['i']+=1
            step=script[min(i,len(script)-1)]
            seq.append(step)
            if step=='net': return await r.abort('connectionreset')
            if step=='502': return await r.fulfill(status=502, body='<html>bad gateway</html>', content_type='text/html')
            if step=='401': who401['n']=2; return await r.fulfill(status=401, body='{"ok":false,"error":"not signed in"}', content_type='application/json')
            if step=='hide':
                return await r.abort('connectionreset')
            d=json.loads(json.dumps(base)); node=step[0]; 
            d['node']='otp1' if node=='A' else 'otp2'
            d['nodes']=[{'name':'otp1','version':'1.0.73','alive':True,'me':node=='A'},{'name':'otp2','version':'1.0.73','alive':True,'me':node=='B'}]
            d['plan']=OLD if step=='oldplan' else plan(int(step[1]))
            await r.fulfill(status=200, body=json.dumps(d), content_type='application/json')
        await pg.route('**/admin/?api=*', route)
        await pg.goto('https://127.0.0.1/admin/#settings/upgrade'); await pg.wait_for_timeout(500)
        await pg.evaluate("showPane('upgrade')")
        hist=[]
        for k in range(70):
            await pg.wait_for_timeout(1000)
            if seq and seq[-1]=='hide' and not hist or (seq and seq[-1]=='hide' and hist[-1][0]!='hidden'):
                await pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:function(){return true}});document.dispatchEvent(new Event('visibilitychange'))")
                hist.append(('hidden',)); await pg.wait_for_timeout(5000)
                await pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:function(){return false}});document.dispatchEvent(new Event('visibilitychange'))")
                continue
            rows=await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('table.up-plan-table tbody tr'),function(t){return t.cells[0].innerText.trim()+':'+t.cells[1].innerText.trim()}).join(' ')+' | '+(UP.last&&UP.last.plan&&UP.last.plan.version)+' | '+$('up-retry').textContent.slice(0,20)")
            hist.append((len(seq), seq[-1] if seq else '', rows))
            if len(seq)>=len(script)+1: break
        prev=None
        for h in hist: 
            if h!=prev: print(h)
            prev=h
        print('polls', len(seq), 'reloads', reloads, 'errors', errs)
        await b.close()
asyncio.run(main())
