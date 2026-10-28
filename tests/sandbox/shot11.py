import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1300})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/fw'); await pg.wait_for_timeout(1000)
        await pg.evaluate("showPane('fw')"); await pg.wait_for_timeout(2500)
        det=pg.locator('details.fw-other').first
        await det.evaluate("d => d.open = true"); await pg.wait_for_timeout(400)
        await det.screenshot(path='/home/claude/shots/fwfull.png')
        print('errors', errs); await b.close()
asyncio.run(main())
