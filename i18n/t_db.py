import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1500,'height':950})
        pg=await ctx.new_page(); pg.on('pageerror', lambda e: print('pageerror', e))
        await pg.goto('https://127.0.0.1/admin/#settings/db'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass','Admin-Pass-123'); await pg.click('#in-go'); await pg.wait_for_timeout(2500)
        try:
            await pg.click('#db-engine-test', timeout=4000)
        except Exception as e:
            print(str(e)[:900])
        await pg.wait_for_timeout(1200)
        await pg.screenshot(path='/home/claude/shots/dbtest.png')
        await pg.goto('https://127.0.0.1/admin/#settings/dir'); await pg.wait_for_timeout(2000)
        try:
            await pg.click('text=Check it >> nth=0', timeout=4000)
        except Exception as e:
            print(str(e)[:900])
        await b.close()
asyncio.run(main())
