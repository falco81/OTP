import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1000})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/dir'); await pg.wait_for_timeout(1500)
        await pg.evaluate("showPane('dir')"); await pg.wait_for_timeout(1200)
        await pg.evaluate("api('directories').then(function(d){editDir(d.directories[0])})"); await pg.wait_for_timeout(1000)
        await pg.screenshot(path='/home/claude/shots/dir-weak.png')
        print('errors', errs); await b.close()
asyncio.run(main())
