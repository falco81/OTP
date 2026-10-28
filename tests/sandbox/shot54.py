import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1000})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/backup'); await pg.wait_for_timeout(2500)
        await pg.locator('.rb-card').nth(1).locator('button:has-text("Backups there"), button:has-text("Zálohy tam")').click(); await pg.wait_for_timeout(3000)
        await pg.screenshot(path='/home/claude/shots/s109-there.png')
        await pg.locator('#modal tbody tr').first.locator('button').nth(1).click(); await pg.wait_for_timeout(800)
        await pg.screenshot(path='/home/claude/shots/s109-putback.png')
        await pg.locator('#modal-foot button.danger').click(); await pg.wait_for_timeout(300)
        await pg.locator('#modal-foot .sure-strip button.danger').click(); await pg.wait_for_timeout(1500)
        for i in range(120):
            await pg.wait_for_timeout(2000)
            t=await pg.locator('#rbr-says').inner_text() if await pg.locator('#rbr-says').count() else ''
            if t.startswith('Put back') or 'failed' in t or 'Vráceno' in t: break
        print('says', t)
        await pg.screenshot(path='/home/claude/shots/s109-restored.png')
        print('errors', errs); await b.close()
asyncio.run(main())
