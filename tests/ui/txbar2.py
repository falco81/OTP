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
        vis="()=>{const b=document.getElementById('save-bar').getBoundingClientRect(); return {inEd: !!document.querySelector('.tx-ed > #save-bar'), shown: getComputedStyle(document.getElementById('save-bar')).display, inView: b.top < window.innerHeight && b.bottom > 0, top: Math.round(b.top)}}"
        print('clean top', await pg.evaluate(vis))
        await pg.evaluate("document.querySelector('.tx-ed').scrollTop=1e6"); await pg.wait_for_timeout(300)
        print('clean bottom', await pg.evaluate(vis))
        await pg.screenshot(path='/home/claude/shots/txbar-bottom.png')
        await pg.evaluate("document.querySelector('.tx-ed').scrollTop=0"); await pg.wait_for_timeout(200)
        await pg.click('.tx-line >> nth=0'); await pg.keyboard.type('X'); await pg.wait_for_timeout(600)
        print('dirty top', await pg.evaluate(vis))
        await pg.click('.tx-item >> nth=1'); await pg.wait_for_timeout(1500)
        print('after switch msg (modal?)', await pg.evaluate("!!document.querySelector('.modal:not([hidden]), #modal:not([hidden])')"))
        await pg.goto('https://127.0.0.1/admin/#settings/radius'); await pg.wait_for_timeout(1500)
        print('radius', await pg.evaluate("()=>({inEd: !!document.querySelector('.tx-ed #save-bar'), parent: document.getElementById('save-bar').parentNode.className})"))
        print('errors', errs)
        await b.close()
asyncio.run(main())
