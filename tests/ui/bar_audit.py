import asyncio, json
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/radius'); await pg.wait_for_timeout(2000)
        panes = await pg.evaluate("Array.from(document.querySelectorAll('#ctl-nav button[data-pane]')).map(b=>b.dataset.pane)")
        for pane in panes:
            await pg.evaluate("p=>showPane(p)", pane); await pg.wait_for_timeout(2200)
            r = await pg.evaluate("""(pane) => {
              const vis = e => e && e.offsetParent !== null && getComputedStyle(e).display!=='none';
              const bar = document.getElementById('save-bar');
              const p = document.getElementById('pane-'+pane);
              const saves = Array.from(p.querySelectorAll('button')).filter(x=>vis(x) && /^(Save|Uložit|Put them back|Add it)/i.test(x.textContent.trim())).map(x=>x.textContent.trim());
              const items = p.querySelectorAll('.set-item').length;
              const inputs = Array.from(p.querySelectorAll('input,select,textarea')).filter(vis).length;
              return {bar: vis(bar), items, inputs, saves};
            }""", pane)
            print(pane, json.dumps(r))
        print('errors', errs)
        await b.close()
asyncio.run(main())
