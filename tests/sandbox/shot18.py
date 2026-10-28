import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1050})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#tokens'); await pg.wait_for_timeout(2000)
        n=await pg.evaluate("api('tokens').then(function(d){return (d.rows||d.tokens||[])[0].name})")
        await pg.evaluate("tokenPeek(%r)" % n); await pg.wait_for_timeout(2000)
        r=await pg.evaluate("""(function(){var o={};['tw-move','tw-btn'].forEach(function(c){o[c]=Array.prototype.map.call(document.querySelectorAll('.'+c),function(e){var r=e.getBoundingClientRect();return [Math.round(r.left),Math.round(r.right)]})});return o})()""")
        print(r)
        await pg.screenshot(path='/home/claude/shots/tokwin.png')
        print('errors', errs); await b.close()
asyncio.run(main())
