import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1000})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/power'); await pg.wait_for_timeout(2500)
        await pg.locator('.pw-node', has_text='nodeb').locator('button').first.click(); await pg.wait_for_timeout(500)
        await pg.screenshot(path='/home/claude/shots/pw-confirm.png')
        await pg.locator('#modal-foot button.primary, #modal-foot button.danger').last.click(); await pg.wait_for_timeout(6000)
        await pg.screenshot(path='/home/claude/shots/pw2.png')
        print('errs', errs); await b.close()
asyncio.run(main())
