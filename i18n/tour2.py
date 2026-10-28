import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1600,'height':1000})
        await ctx.add_cookies([{'name':'otp_lang','value':'en','url':'https://127.0.0.1/'}])
        pg=await ctx.new_page(); pg.on('pageerror', lambda e: print('pageerror', e))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass','Admin-Pass-123'); await pg.click('#in-go'); await pg.wait_for_timeout(2500)
        await pg.click('button[data-tab=requests]'); await pg.wait_for_timeout(1500)
        await pg.mouse.move(1200,950); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/t2_log.png')
        await pg.goto('https://127.0.0.1/admin/#settings/dir'); await pg.wait_for_timeout(1800)
        await pg.evaluate("editDir(DIRS[0])"); await pg.wait_for_timeout(800)
        await pg.screenshot(path='/home/claude/shots/t2_diredit.png')
        await b.close()
asyncio.run(main())
