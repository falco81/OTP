import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/ha'); await pg.reload(); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('#ha-vip-card').scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/vip.png')
        await pg.evaluate("document.querySelector('#ha-lb').scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/lb2.png')
        await pg.click('#ha-stop'); await pg.wait_for_timeout(500)
        await pg.click('#modal-foot .btn.danger'); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/sure.png')
        await pg.click('#modal-foot .sure-strip .btn:not(.danger)')
        await pg.evaluate('closeModal()')
        await pg.goto('https://127.0.0.1/admin/#settings/fw'); await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('#fw-body').scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/fw5.png')
        print(errs); await b.close()
asyncio.run(main())
