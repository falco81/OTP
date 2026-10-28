import asyncio, sys
from playwright.async_api import async_playwright
L = sys.argv[1] if len(sys.argv) > 1 else 'en'
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1600,'height':1000})
        await ctx.add_cookies([{'name':'otp_lang','value':L,'url':'https://127.0.0.1/'}])
        pg=await ctx.new_page(); pg.on('pageerror', lambda e: print('pageerror', e)); pg.on('dialog', lambda d: print('DIALOG', d.message))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass','Admin-Pass-123'); await pg.click('#in-go'); await pg.wait_for_timeout(2500)
        async def shot(n, full=False):
            await pg.mouse.move(1200,900); await pg.wait_for_timeout(400)
            await pg.screenshot(path='/home/claude/shots/t_%s_%s.png'%(L,n), full_page=full)
        await pg.click('button[data-tab=requests]'); await pg.wait_for_timeout(1500); await shot('log')
        await pg.click('button[data-tab=tokens]'); await pg.wait_for_timeout(1500); await shot('tokens')
        await pg.evaluate("tokenPeek('falco@corpnet.cz')"); await pg.wait_for_timeout(1500); await shot('tokpeek')
        await pg.evaluate("document.getElementById('modal-body').scrollTop=2000"); await pg.wait_for_timeout(300); await shot('tokpeek2')
        await pg.evaluate("whoisPeek('falco@corpnet.cz','token')"); await pg.wait_for_timeout(1500); await shot('whois')
        await pg.evaluate("closeModal()")
        for pane in ['dir','realms','people','db','clients','tokens','portal','isemon','about','radius']:
            await pg.goto('https://127.0.0.1/admin/#settings/'+pane); await pg.wait_for_timeout(1800); await shot('p_'+pane, True)
        await pg.goto('https://127.0.0.1/admin/#settings/realms'); await pg.wait_for_timeout(1800)
        await pg.evaluate("editRealm(REALMS.realms[0])"); await pg.wait_for_timeout(800); await shot('realmedit')
        await b.close()
asyncio.run(main())
