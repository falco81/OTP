import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1100})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/upgrade'); await pg.reload(); await pg.wait_for_timeout(3500)
        await pg.locator('#up-web-card').screenshot(path='/home/claude/shots/up-web.png')
        print('bar on upgrade', await pg.evaluate("getComputedStyle(document.getElementById('save-bar')).display"))
        await pg.goto('https://127.0.0.1/admin/#settings/db'); await pg.wait_for_timeout(3000)
        await pg.click('#db-download'); await pg.wait_for_timeout(800)
        await pg.locator('#modal').screenshot(path='/home/claude/shots/db-dl.png')
        print('errors', errs)
        await b.close()
asyncio.run(main())
