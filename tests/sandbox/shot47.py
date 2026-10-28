import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1200})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/network'); await pg.wait_for_timeout(3000)
        await pg.screenshot(path='/home/claude/shots/net1.png', full_page=True)
        await pg.locator('.net-nodes button', has_text='nodeb').click(); await pg.wait_for_timeout(800)
        await pg.locator('#net-host button', has_text='Ověřit').first.click() if await pg.locator('#net-host button', has_text='Ověřit').count() else await pg.locator('#net-host button', has_text='Check it').first.click()
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/home/claude/shots/net2.png', full_page=True)
        await pg.goto('https://127.0.0.1/admin/#settings/power'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/pw1.png', full_page=True)
        print('errs', errs); await b.close()
asyncio.run(main())
