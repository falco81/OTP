import asyncio, json
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1000})
        pg=await ctx.new_page()
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/network'); await pg.wait_for_timeout(3000)
        for pane in ['network','time','about','ha','dir','web']:
            print(pane, await pg.evaluate("p=>Array.from(document.querySelectorAll('#pane-'+p+' .set-item')).map(x=>x.dataset.key+(x.offsetParent?'':'(hidden)'))", pane))
        await b.close()
asyncio.run(main())
