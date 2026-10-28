import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1400,'height':900})
        pg=await ctx.new_page(); pg.on('pageerror', lambda e: print('pageerror', e)); pg.on('dialog', lambda d: print('NATIVE DIALOG', d.message))
        await pg.goto('https://127.0.0.1/admin/#settings/dir'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass','Admin-Pass-123'); await pg.click('#in-go'); await pg.wait_for_timeout(2500)
        await pg.mouse.move(900,600); await pg.wait_for_timeout(500)
        await pg.evaluate("lookupDir('MOCK')"); await pg.wait_for_timeout(500)
        await pg.screenshot(path='/home/claude/shots/ask1.png')
        await pg.keyboard.type('falco'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/home/claude/shots/ask2.png')
        await b.close()
asyncio.run(main())
