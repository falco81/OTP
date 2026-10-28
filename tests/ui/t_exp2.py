import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1400,'height':950}, accept_downloads=True)
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append('console:'+m.text))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.click('#in-go'); await pg.wait_for_timeout(2500)
        r=await pg.evaluate("api('export&secrets=1').then(d=>Object.keys(d).join(','), e=>'ERR '+e.message)")
        print('api:', r)
        await pg.click('button[data-tab=settings]'); await pg.wait_for_timeout(800)
        await pg.click('button[data-pane=carry]'); await pg.wait_for_timeout(700)
        DL={}
        async def keep(d):
            path='/tmp/claude-0/expbundle.json'; await d.save_as(path); DL['p']=path
        pg.on('download', lambda d: asyncio.ensure_future(keep(d)))
        await pg.click('#ex-whole'); await pg.wait_for_timeout(600)
        await pg.locator('#modal button.danger:visible').last.click()
        await pg.wait_for_timeout(500)
        await pg.locator('#modal button.danger:visible').last.click()
        await pg.wait_for_timeout(3000)
        print('modal:', (await pg.inner_text('#modal-box'))[:300].replace('\n',' | '))
        phrase=(await pg.inner_text('#modal-box .keytext')).strip()
        await pg.evaluate('closeModal()')
        await pg.set_input_files('#ex-file', DL['p']); await pg.wait_for_timeout(1500)
        await pg.fill('#modal-box input[type=password]', phrase)
        await pg.locator('#modal button.primary:visible').last.click(); await pg.wait_for_timeout(4000)
        print('toast:', await pg.evaluate("(document.getElementById('toast')||{}).textContent"))
        await pg.screenshot(path='/home/claude/shots/imp.png')
        print('errs', errs)
        await b.close()
asyncio.run(main())
