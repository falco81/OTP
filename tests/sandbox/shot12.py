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
        xs=[]
        import time
        for st in [('done','installing',{'part':2,'part_words':'PHP, and php2shell'}),('done','draining',{}),('waiting','waiting',{}),('done','checking',{})]:
            js = """(function(){var d=JSON.parse(JSON.stringify(UP.last)); var now=Date.now()/1000;
              d.plan=d.plan||{}; d.plan.state='running'; d.plan.version='9.9.9'; d.plan.at=now-30; d.plan.drain_s=20;
              d.plan.steps=[{name:'otp2',state:'%s',at:now-5,said:'1.0.69, checked, back in service with a much longer text to see wrapping', tail:['==> x']},
                            Object.assign({name:'otp1',state:'%s',at:now-3,asked:now-40,said:'in maintenance; the balancer and the VPN go to the other node'}, %s)];
              drawUpgrade(d); clearTimeout(UP.timer);
              return Array.prototype.map.call(document.querySelectorAll('table.up-plan-table thead th'), function(t){return Math.round(t.getBoundingClientRect().left)});})()""" % (st[0], st[1], json.dumps(st[2]))
            xs.append(await pg.evaluate(js)); await pg.wait_for_timeout(200)
        print('column x per state:', xs)
        await pg.locator('#up-plan-card').screenshot(path='/home/claude/shots/upfixed.png')
        print('errors', errs); await b.close()
asyncio.run(main())
