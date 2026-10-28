import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':900})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/db'); await pg.wait_for_timeout(3000)
        await pg.locator('#db-link-note').scroll_into_view_if_needed(); await pg.evaluate("window.scrollBy(0,-200)")
        await pg.screenshot(path='/home/claude/shots/s107-db.png')
        await pg.goto('https://127.0.0.1/admin/#settings/ha'); await pg.wait_for_timeout(2500)
        await pg.locator('.hal').screenshot(path='/home/claude/shots/s107-bar.png')
        print(await pg.locator('#ha-addr-card .small.muted').first.inner_text())
        print('errors', errs); await b.close()
asyncio.run(main())
