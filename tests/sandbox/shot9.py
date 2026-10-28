import asyncio, time
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/upgrade'); await pg.wait_for_timeout(1500)
        await pg.evaluate("showPane('upgrade')"); await pg.wait_for_timeout(1500)
        pass
        t0=time.time(); n=0; seen=[]
        while time.time()-t0 < 200:
            await pg.wait_for_timeout(4000)
            txt = await pg.evaluate("($('up-plan')||{}).innerText||''")
            line=' | '.join(l for l in txt.split('\n') if '%' in l or 'node' in l.lower())[:220]
            seen.append(line); print('%3ds %s'%(time.time()-t0, line), flush=True)
            if n<6 and ('%' in txt): await pg.locator('#up-plan-card').screenshot(path='/home/claude/shots/up%d.png'%n); n+=1
            if 'done' in txt.split('\n')[0] if txt else False: pass
            if '100 % · 2 of 2' in txt: 
                await pg.locator('#up-plan-card').screenshot(path='/home/claude/shots/up-done.png'); break
        print('errors', errs)
        await b.close()
asyncio.run(main())
