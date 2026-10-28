import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        for t in ['overview','tokens','requests','test','enrolment','events']:
            await pg.click('button[data-tab=%s]'%t); await pg.wait_for_timeout(1200)
        for pn in ['radius','clients','realms','dir','tokens','portal','isemon','people','db','mail','ha','web','fw','upgrade','carry','about']:
            await pg.goto('https://127.0.0.1/admin/#settings/'+pn); await pg.wait_for_timeout(200)
            await pg.evaluate("showPane('%s')"%pn); await pg.wait_for_timeout(900)
        await pg.evaluate("showPane('realms')"); await pg.wait_for_timeout(1200)
        await pg.click('#pane-realms table tbody tr >> nth=0'); await pg.wait_for_timeout(1200)
        ta = pg.locator('#modal textarea.re-ta').last
        await ta.scroll_into_view_if_needed(); await ta.click()
        await pg.keyboard.press('Control+End'); await pg.keyboard.press('Enter')
        await pg.keyboard.type('Forti'); await pg.wait_for_timeout(400)
        await pg.screenshot(path='/home/claude/shots/re1.png')
        await pg.keyboard.press('Escape'); await pg.keyboard.press('Control+a'); await pg.keyboard.press('Delete')
        await pg.keyboard.press('Control+Space'); await pg.wait_for_timeout(400)
        await pg.screenshot(path='/home/claude/shots/re2.png')
        await pg.keyboard.type('tunnel-t'); await pg.wait_for_timeout(300); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(400)
        await pg.screenshot(path='/home/claude/shots/re3.png')
        await pg.keyboard.press('ArrowDown'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(200)
        await pg.keyboard.press('Enter'); await pg.keyboard.type('Service-Type = Nope'); await pg.wait_for_timeout(300)
        await pg.keyboard.press('Escape')
        await pg.screenshot(path='/home/claude/shots/re4.png')
        print('value', repr(await ta.input_value()))
        print('errors', errs)
        await b.close()
asyncio.run(main())
