import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1100})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/portal'); await pg.wait_for_timeout(2000)
        await pg.locator('#art-card').screenshot(path='/home/claude/shots/arts-all.png')
        await pg.goto('https://127.0.0.1/admin/#settings/ha'); await pg.wait_for_timeout(2000)
        await pg.locator('#ha-cli-fold').scroll_into_view_if_needed(); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/hafold.png')
        print('open by default:', await pg.evaluate("$('ha-cli-fold').open"), 'errors', errs); await b.close()
asyncio.run(main())
