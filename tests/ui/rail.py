import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})
        pg=await ctx.new_page()
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/clients'); await pg.wait_for_timeout(2500)
        js="Array.from(document.querySelectorAll('#ctl-nav button[data-pane]')).map(b=>Math.round(b.getBoundingClientRect().top))"
        a=await pg.evaluate(js)
        await pg.evaluate("document.getElementById('ctl-nav').classList.add('open')"); await pg.wait_for_timeout(400)
        c=await pg.evaluate(js)
        print('pinned?', await pg.evaluate("document.getElementById('ctl-nav').className"))
        print('diffs', [y-x for x,y in zip(a,c)])
        await b.close()
asyncio.run(main())
