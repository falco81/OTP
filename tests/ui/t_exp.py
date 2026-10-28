import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1400,'height':950}, accept_downloads=True)
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.click('#in-go'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.cookie='otp_lang=en;path=/'")
        await pg.click('button[data-tab=settings]'); await pg.wait_for_timeout(800)
        panes=await pg.eval_on_selector_all('button[data-pane]','els=>els.map(e=>e.dataset.pane)')
        for pn in panes:
            await pg.click('button[data-pane=%s]'%pn); await pg.wait_for_timeout(700)
        await pg.click('button[data-pane=carry]'); await pg.wait_for_timeout(700)
        await pg.click('#ex-whole'); await pg.wait_for_timeout(500)
        pg.on('download', lambda d: print('download', d.suggested_filename))
        print(await pg.evaluate("Array.from(document.querySelectorAll('#modal button')).map(b=>b.className+'|'+b.textContent+'|'+(b.offsetParent!==null))"))
        await pg.locator('#modal button.danger:visible').last.click()
        await pg.wait_for_timeout(3000)
        print('errs', errs); print('toast', await pg.evaluate("(document.getElementById('toast')||{}).textContent"))
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/home/claude/shots/exp_phrase.png')
        print('modal text:', (await pg.inner_text('#modal-box'))[:200].replace('\n',' | '))
        for t in ['tokens','codes','dashboard','events'] :
            if await pg.locator('button[data-tab=%s]'%t).count():
                await pg.click('button[data-tab=%s]'%t); await pg.wait_for_timeout(900)
        print('pageerrors', errs)
        await b.close()
asyncio.run(main())
