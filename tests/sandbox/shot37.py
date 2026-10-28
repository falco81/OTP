import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        items=pg.locator('#ov-names > *')
        print('facet items', await items.count())
        if await items.count():
            await items.first.click(); await pg.wait_for_timeout(2500)
            print('hash', pg.url.split('#')[1])
            for sel in ('#rq-q','#rq-result','#rq-client','#rq-kind'):
                if await pg.locator(sel).count(): print(sel, repr(await pg.locator(sel).input_value()))
            await pg.screenshot(path='/home/claude/shots/drill.png')
        print('errors', errs); await b.close()
asyncio.run(main())
