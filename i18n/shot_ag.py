import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1600,'height':1300})
        await ctx.add_cookies([{'name':'otp_lang','value':'cs','url':'https://127.0.0.1/'}])
        pg=await ctx.new_page(); pg.on('pageerror', lambda e: print('pageerror', e))
        await pg.goto('https://127.0.0.1/admin/#settings/people'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass','Admin-Pass-123'); await pg.click('#in-go'); await pg.wait_for_timeout(2500)
        await pg.click('#ag-find'); await pg.wait_for_timeout(1500)
        print('GROUPS:', (await pg.inner_text('#ag-groups'))[:300]); print('TOAST:', await pg.evaluate("(document.querySelector('.toast')||{}).textContent"))
        await pg.screenshot(path='/home/claude/shots/ag_list.png', full_page=True)
        btns = pg.locator('#ag-groups tr.dgroup').nth(1).locator('.rowtools button')
        print('buttons', await btns.count())
        await btns.nth(2).click(); await pg.wait_for_timeout(500)
        await pg.locator('#ag-groups').scroll_into_view_if_needed()
        await pg.screenshot(path='/home/claude/shots/ag_list.png', full_page=True)
        await pg.click('#ag-try'); await pg.wait_for_timeout(400)
        await pg.fill('#modal-body input[type=text]','CORPNET\\falco'); await pg.fill('#modal-body input[type=password]','falco-password-1')
        await pg.locator('#modal .btn.primary').click(); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/home/claude/shots/ag_try.png')
        await b.close()
        # sign in as falco
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1400,'height':800})
        pg=await ctx.new_page(); await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','falco'); await pg.fill('#in-pass','falco-password-1'); await pg.click('#in-go'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/ag_falco.png'); await b.close()
asyncio.run(main())
