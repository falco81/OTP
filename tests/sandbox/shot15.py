import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1100})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/portal'); await pg.wait_for_timeout(1500)
        gap=await pg.evaluate("(function(){var a=$('art-card').getBoundingClientRect(), c=$('sect-portal').closest('.card').getBoundingClientRect(); var i=document.querySelectorAll('#pane-import .card'); var r=i[1].getBoundingClientRect().top - 0; return [Math.round(c.top-a.bottom)];})()")
        print('gap px', gap, 'errors', errs); await b.close()
asyncio.run(main())
