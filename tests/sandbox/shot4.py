import asyncio, json
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/fw'); await pg.reload(); await pg.wait_for_timeout(2500)
        n0=await pg.evaluate("FW.draft.rules.length")
        # access change
        await pg.click('#fw-access .fw-acc-row >> nth=0 >> .seg button >> nth=1'); await pg.wait_for_timeout(200)
        await pg.fill('#fw-access .fw-acc-row >> nth=0 >> textarea', '10.0.0.0/8, 192.168.0.0/16')
        # delete a rule, toggle auto
        await pg.evaluate("document.querySelectorAll('#fw-body .fw-table tbody tr')[1].querySelector('.acts button:last-child').click()")
        await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('.fw-auto-card input').click()"); await pg.wait_for_timeout(300)
        # add a rule
        await pg.click('#fw-body .fw-h .btn'); await pg.wait_for_timeout(400)
        await pg.fill('#modal input.mono >> nth=0', '8080'); await pg.click('#modal-foot .btn.primary'); await pg.wait_for_timeout(800)
        await pg.screenshot(path='/home/claude/shots/fwd1.png')
        server=await pg.evaluate("api('firewall').then(d=>JSON.stringify([d.conf.rules.length, d.conf.off, d.access.portal]))")
        print('draft', await pg.evaluate("JSON.stringify([FW.dirty, FW.draft.rules.length, FW.draft.off, FW.draft.access.portal])"), 'n0', n0, 'server', server)
        await pg.click('#set-save'); await pg.wait_for_timeout(1500)
        server=await pg.evaluate("api('firewall').then(d=>JSON.stringify([d.conf.rules.length, d.conf.off, d.access.portal]))")
        print('after save', server, await pg.evaluate("FW.dirty"), await pg.evaluate("$('set-said').textContent"))
        # change + put back
        await pg.evaluate("document.querySelector('.fw-auto-card input').click()"); await pg.wait_for_timeout(300)
        await pg.click('#set-reset'); await pg.wait_for_timeout(1500)
        print('after reset', await pg.evaluate("JSON.stringify([FW.dirty, FW.draft.off])"))
        await pg.screenshot(path='/home/claude/shots/fwd2.png')
        print(errs); await b.close()
asyncio.run(main())
