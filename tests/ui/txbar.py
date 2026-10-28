import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/texts'); await pg.wait_for_timeout(3500)
        st="()=>({bar:getComputedStyle(document.getElementById('save-bar')).display, h:document.querySelector('.tx-shell').style.height, mainScroll:document.querySelector('.ctl-main').scrollHeight-document.querySelector('.ctl-main').clientHeight})"
        print('clean', await pg.evaluate(st))
        await pg.click('.tx-line >> nth=0'); await pg.keyboard.type('X'); await pg.wait_for_timeout(800)
        print('dirty', await pg.evaluate(st))
        await pg.screenshot(path='/home/claude/shots/txbar.png')
        await pg.click('#set-reset'); await pg.wait_for_timeout(1500)
        print('reset', await pg.evaluate(st)); print('errors', errs)
        await b.close()
asyncio.run(main())
