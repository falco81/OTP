import asyncio, json
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/time'); await pg.wait_for_timeout(3000)
        st = "() => { const b=document.getElementById('save-bar'); return {shown: getComputedStyle(b).display!=='none', dirty: b.classList.contains('dirty'), said: document.getElementById('set-said').textContent, pend: Object.keys(PENDING)} }"
        print('time clean', await pg.evaluate(st))
        inp = pg.locator('#ntp-form input[type=text]').first
        await inp.click(); await pg.keyboard.type('x')
        print('time typed', await pg.evaluate(st))
        await pg.evaluate("showPane('network')"); await pg.wait_for_timeout(2500)
        print('network', await pg.evaluate(st))
        await pg.evaluate("showPane('power')"); await pg.wait_for_timeout(1500)
        print('power', await pg.evaluate(st))
        await pg.evaluate("showPane('time')"); await pg.wait_for_timeout(2500)
        print('time back', await pg.evaluate(st), await pg.evaluate("document.querySelector('#ntp-form input[type=text]').value"))
        await pg.click('#set-reset'); await pg.wait_for_timeout(1500)
        print('time reset', await pg.evaluate(st), await pg.evaluate("document.querySelector('#ntp-form input[type=text]').value"))
        await pg.evaluate("showPane('texts')"); await pg.wait_for_timeout(2500)
        print('texts', await pg.evaluate(st))
        ta = pg.locator('#pane-texts [contenteditable=true], #pane-texts textarea, #pane-texts input[type=text]').first
        if await ta.count():
            await ta.click(); await pg.keyboard.type('Z'); await pg.wait_for_timeout(500)
            print('texts typed', await pg.evaluate(st))
            await pg.click('#set-reset'); await pg.wait_for_timeout(1500)
            print('texts reset', await pg.evaluate(st))
        await pg.screenshot(path='/home/claude/shots/texts-bar.png')
        print('errors', errs)
        await b.close()
asyncio.run(main())
