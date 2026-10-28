import asyncio, json
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/upgrade'); await pg.wait_for_timeout(800)
        await pg.evaluate("showPane('upgrade')"); await pg.wait_for_timeout(2000)
        js = """(function(who, fresh){var d=JSON.parse(JSON.stringify(UP.last||{})); var now=Date.now()/1000;
          d.node=who; d.nodes=[{name:'otp1',version:'1.0.69',alive:true,me:who==='otp1'},{name:'otp2',version:'1.0.70',alive:true,me:who==='otp2'}];
          if(who==='otp2') d.nodes.reverse();
          d.plan={id:'p1',state:'running',version:'1.0.70',at:now-100,drain_s:20,steps:[
            {name:'otp2',state:'done',at:now-50,said:'1.0.70, checked, back in service'},
            fresh?{name:'otp1',state:'installing',at:now-5,part:3,part_words:'nginx',said:'installing'}
                 :{name:'otp1',state:'waiting',at:now-60,said:'waiting'}]};
          d.last_log={text:'==> log of '+who, at:now}; drawUpgrade(d); clearTimeout(UP.timer);
          var r={}; document.querySelectorAll('table.up-plan-table tbody tr').forEach(function(tr){r[tr.cells[0].innerText.trim()]=tr.innerText.replace(/\\s+/g,' ').slice(0,80)});
          r._nodes=Array.prototype.map.call(document.querySelectorAll('#up-nodes tbody tr'),function(t){return t.cells[0].innerText.trim()});
          return r;})"""
        seq=[('otp2',True),('otp1',False),('otp2',True),('otp1',False)]
        for who,fresh in seq:
            r=await pg.evaluate(js+"(%s,%s)"%(json.dumps(who),'true' if fresh else 'false')); print(who, r)
        await pg.evaluate("$('up-retry').textContent='A node is restarting or the web address is moving to the other node - asking again…'")
        await pg.wait_for_timeout(500); print('retry:', await pg.inner_text('#up-retry'))
        await pg.locator('#up-plan-card').screenshot(path='/home/claude/shots/upvip.png')
        print('errors', errs); await b.close()
asyncio.run(main())
