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
        await pg.screenshot(path='/home/claude/shots/s109-backup.png')
        # edit the ssh key box
        cards=pg.locator('.rb-card')
        n=await cards.count()
        await cards.nth(n-1).locator('button:has-text("Edit"), button:has-text("Upravit")').click(); await pg.wait_for_timeout(900)
        await pg.locator('#modal-body').evaluate("e=>e.scrollTop=400")
        await pg.screenshot(path='/home/claude/shots/s109-edit-key.png')
        # make a key (replace) -> confirm over editor
        await pg.locator('#modal button:has-text("Make a key"), #modal button:has-text("Vytvořit klíč")').first.click(); await pg.wait_for_timeout(600)
        await pg.screenshot(path='/home/claude/shots/s109-confirm.png')
        await pg.locator('#modal-foot button').last.click(); await pg.wait_for_timeout(2500)
        print('editor still there', await pg.locator('#modal .rb-panel').count(), await pg.locator('#modal-title').inner_text())
        await pg.screenshot(path='/home/claude/shots/s109-edit-key2.png')
        # ftps editor
        await pg.locator('#modal-foot button').first.click(); await pg.wait_for_timeout(500)
        await cards.nth(1).locator('button:has-text("Edit"), button:has-text("Upravit")').click(); await pg.wait_for_timeout(900)
        await pg.locator('#modal-body').evaluate("e=>e.scrollTop=600")
        await pg.screenshot(path='/home/claude/shots/s109-edit-ftps.png')
        print('errors', errs); await b.close()
asyncio.run(main())
