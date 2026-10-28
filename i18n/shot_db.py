import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1500,'height':1400})
        await ctx.add_cookies([{'name':'otp_lang','value':'en','url':'https://127.0.0.1/'}])
        pg=await ctx.new_page(); pg.on('pageerror', lambda e: print('pageerror', e))
        await pg.goto('https://127.0.0.1/admin/#settings/db'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass','Admin-Pass-123'); await pg.click('#in-go'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/db1.png', full_page=True)
        await pg.goto('https://127.0.0.1/admin/#settings/realms'); await pg.wait_for_timeout(2000)
        await pg.locator('#pane-realms tbody tr').nth(0).click(); await pg.wait_for_timeout(800)
        await pg.locator('.groupbrowser .btn').first.click(); await pg.wait_for_timeout(1500)
        await pg.locator('.groupbrowser tr.dgroup').nth(0).locator('.rowtools .btn').click(); await pg.wait_for_timeout(300)
        await pg.locator('#modal-body').evaluate('e=>e.scrollTop=e.scrollHeight'); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/realm_pick.png')
        await b.close()
asyncio.run(main())
