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
        was = await pg.evaluate("NTP.d.conf.timezone")
        await pg.evaluate("""() => { const s=Array.from(document.querySelectorAll('#ntp-form select')).sort((a,b)=>b.options.length-a.options.length)[0]; s.value=s.options[2].value; s.dispatchEvent(new Event('change',{bubbles:true})); }""")
        await pg.click('#set-save'); await pg.wait_for_timeout(7000)
        print('was', was, 'now', await pg.evaluate("NTP.d.conf.timezone"), await pg.evaluate("Object.keys(PENDING)"))
        await pg.evaluate("(w) => { const s=Array.from(document.querySelectorAll('#ntp-form select')).sort((a,b)=>b.options.length-a.options.length)[0]; s.value=w; s.dispatchEvent(new Event('change',{bubbles:true})); }", was)
        await pg.click('#set-save'); await pg.wait_for_timeout(7000)
        print('back', await pg.evaluate("NTP.d.conf.timezone"))
        print('errors', errs)
        await b.close()
asyncio.run(main())
