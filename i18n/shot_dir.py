import asyncio,sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1920,'height':1000})
        await ctx.add_cookies([{'name':'otp_lang','value':'en','url':'https://127.0.0.1/'}])
        pg=await ctx.new_page(); await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass','Admin-Pass-123'); await pg.click('#in-go'); await pg.wait_for_timeout(2000)
        for pane in sys.argv[2:]:
            await pg.goto('https://127.0.0.1/admin/#settings/'+pane); await pg.wait_for_timeout(1800)
            await pg.screenshot(path=sys.argv[1]+'_'+pane+'.png')
        await b.close()
asyncio.run(main())
