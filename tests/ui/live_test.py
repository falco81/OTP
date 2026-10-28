import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        # Time pane
        await pg.goto('https://127.0.0.1/admin/#settings/time'); await pg.reload(); await pg.wait_for_timeout(3000)
        await pg.evaluate("Array.from(document.querySelectorAll('#ntp-form select')).sort((a,b)=>b.options.length-a.options.length)[0].id='tzsel'")
        sel = pg.locator('#tzsel')
        await sel.focus()
        opts = await sel.evaluate("s => Array.from(s.options).map(o=>o.value)"); print("opts", len(opts))
        await sel.evaluate("(s,v) => { s.value = v; s.dispatchEvent(new Event('change',{bubbles:true})); s.dataset.mark='x'; }", opts[-1])
        await pg.evaluate("document.querySelector('#ntp-host .ntp-node').dataset.old='1'")
        await pg.wait_for_timeout(12000)
        r = await pg.evaluate("""() => { const s=document.querySelector('#ntp-form select[data-mark]');
          return {same: !!s, focused: document.activeElement===s, val: s&&s.value, oldCardGone: !document.querySelector('#ntp-host .ntp-node[data-old]')} }""")
        print('time', r, opts[-1])
        # blur -> form then can redraw, keep value via draft
        await pg.evaluate("document.activeElement.blur()"); await pg.wait_for_timeout(11000)
        print('time after', await pg.evaluate("Array.from(document.querySelectorAll('#ntp-form select')).sort((a,b)=>b.options.length-a.options.length)[0].value"), await pg.evaluate("!!document.querySelector('#ntp-form select[data-mark]')"))
        # typing in a text box in the form
        t = pg.locator('#ntp-form input[type=text]').first
        await t.click(); await t.fill('typing.example.cz')
        await pg.wait_for_timeout(11000)
        print('typed', await pg.evaluate("document.activeElement.value"), await pg.evaluate("document.activeElement.tagName"))
        # HA pane VIP field
        await pg.goto('https://127.0.0.1/admin/#settings/ha'); await pg.wait_for_timeout(3000)
        inp = pg.locator('#web-vip input[type=text]').nth(1)
        await inp.click(); await pg.keyboard.type('zz')
        await pg.evaluate("document.activeElement.dataset.mark='v'")
        await pg.wait_for_timeout(7000)
        print('vip', await pg.evaluate("({same: document.activeElement.dataset.mark==='v', val: document.activeElement.value})"))
        for pane in ['web','fw','mailq','upgrade','db','backup','network','power','people']:
            await pg.goto('https://127.0.0.1/admin/#settings/'+pane); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/fw'); await pg.wait_for_timeout(2000)
        ta = pg.locator('#fw-access textarea').first
        if await ta.count():
            await ta.evaluate("t=>{t.hidden=false}")
            await ta.focus(); await pg.keyboard.type('10.9.9.0/24'); await pg.evaluate("document.activeElement.dataset.mark='f'")
            await pg.wait_for_timeout(7000)
            print('fw', await pg.evaluate("({same: document.activeElement.dataset.mark==='f', val: document.activeElement.value})"))
        print('errors', errs)
        await b.close()
asyncio.run(main())
