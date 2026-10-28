import asyncio, json
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/ha'); await pg.reload(); await pg.wait_for_timeout(3000)
        before=await pg.evaluate("api('web').then(d=>JSON.stringify([d.vip.fqdn,d.vip.mode,d.vip.vrid]))")
        await pg.fill('#vip-fqdn','vip2.example.cz'); await pg.fill('#vip-vrid','52')
        await pg.click('.vip-return .seg button:last-child'); await pg.wait_for_timeout(300)
        mid=await pg.evaluate("api('web').then(d=>JSON.stringify([d.vip.fqdn,d.vip.mode,d.vip.vrid]))")
        await pg.evaluate("document.querySelector('#ha-vip-card').scrollIntoView()")
        await pg.screenshot(path='/home/claude/shots/vipd.png')
        said=await pg.evaluate("$('set-said').textContent")
        await pg.click('#set-save'); await pg.wait_for_timeout(2500)
        after=await pg.evaluate("api('web').then(d=>JSON.stringify([d.vip.fqdn,d.vip.mode,d.vip.vrid]))")
        print('before',before,'mid',mid,'said',said,'after',after, 'pending', await pg.evaluate("JSON.stringify(Object.keys(PENDING))"))
        # put back test
        await pg.fill('#vip-fqdn','zzz.example.cz'); await pg.click('#set-reset'); await pg.wait_for_timeout(2000)
        print('after reset field', await pg.evaluate("$('vip-fqdn').value"), await pg.evaluate("JSON.stringify(Object.keys(PENDING))"))
        # restore
        await pg.fill('#vip-fqdn','otp-vip.example.cz'); await pg.fill('#vip-vrid','51')
        await pg.click('.vip-return .seg button >> nth=0'); await pg.wait_for_timeout(300)
        await pg.click('#set-save'); await pg.wait_for_timeout(2500)
        # history clear
        await pg.click('#ha-history'); await pg.wait_for_timeout(1200)
        await pg.click('#modal-foot .btn.danger'); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/hclear.png')
        await pg.click('#modal-foot .sure-strip .btn.danger'); await pg.wait_for_timeout(1500)
        print('rows after clear', await pg.evaluate("document.querySelectorAll('.ha-hist-item').length"))
        # mail CA pending
        await pg.goto('https://127.0.0.1/admin/#settings/mail'); await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.fill('#mca-pem','junk'); await pg.wait_for_timeout(200)
        print('mail pending', await pg.evaluate("JSON.stringify(Object.keys(PENDING))"), await pg.evaluate("$('mca-save').hidden"))
        await pg.click('#set-save'); await pg.wait_for_timeout(1500)
        print('after bad save pending', await pg.evaluate("JSON.stringify(Object.keys(PENDING))"))
        await pg.click('#set-reset'); await pg.wait_for_timeout(800)
        print(errs); await b.close()
asyncio.run(main())
