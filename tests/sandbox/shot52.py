import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1000})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/backup'); await pg.wait_for_timeout(3000)
        await pg.screenshot(path='/home/claude/shots/s109-backup.png', full_page=False)
        await pg.evaluate("document.querySelector('.ctl-main').scrollTop=700"); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/s109-backup2.png')
        await pg.click('#rb-add-host button'); await pg.wait_for_timeout(600)
        await pg.screenshot(path='/home/claude/shots/s109-kinds.png')
        await pg.locator('.rb-kind-tile').nth(3).click(); await pg.wait_for_timeout(800)
        await pg.screenshot(path='/home/claude/shots/s109-edit-sftp.png')
        print('errors', errs); await b.close()
asyncio.run(main())
