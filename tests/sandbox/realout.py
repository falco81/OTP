import asyncio, time
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True)).new_page()
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/upgrade'); await pg.wait_for_timeout(1500)
        # end this session on the daemon side, behind the page's back
        await pg.evaluate("fetch('?api=sessions',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:'{}'})")
        sid=await pg.evaluate("api('sessions').then(function(d){return d})")
        import json
        rows=(sid.get('rows') or sid.get('sessions') or [])
        t=time.time()
        await pg.evaluate("api('logout',{}).catch(function(){})")  # server session gone; the cookie is dropped too, like a run-out session
        await pg.evaluate("loadUpgrade()")
        await pg.wait_for_selector('#in-name', timeout=20000)
        print('back at the sign-in after %.1f s' % (time.time()-t)); await b.close()
asyncio.run(main())
