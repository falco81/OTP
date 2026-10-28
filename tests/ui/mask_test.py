import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/db'); await pg.wait_for_timeout(2500)
        await pg.click('#db-download'); await pg.wait_for_timeout(600)
        await pg.click('#dbk-p1'); await pg.keyboard.type('secretpass12')
        print('typed shows', await pg.evaluate("Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').get.call(document.getElementById('dbk-p1'))"), 'value', await pg.evaluate("document.getElementById('dbk-p1').value"))
        await pg.keyboard.press('Escape')
        await pg.goto('https://127.0.0.1/admin/#settings/mail'); await pg.wait_for_timeout(2500)
        print('kept smtp', await pg.evaluate("(()=>{const i=document.querySelector('.set-item[data-key=smtp_password] input'); return i?Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').get.call(i):'none'})()"))
        await pg.goto('https://127.0.0.1/admin/#test'); await pg.wait_for_timeout(1500)
        print('rt-pass type', await pg.evaluate("document.getElementById('rt-pass').type"))
        print('errors', errs)
        await b.close()
asyncio.run(main())
