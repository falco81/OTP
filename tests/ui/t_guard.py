import asyncio
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1500,'height':1100})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.click('#in-go'); await pg.wait_for_timeout(2500)
        await pg.click('button[data-tab=settings]'); await pg.wait_for_timeout(800)
        await pg.click('button[data-pane=guard]'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/guard.png', full_page=True)
        await pg.fill('#gd-find','u036'); await pg.wait_for_timeout(600)
        print('filtered rows:', await pg.locator('#gd-table tbody tr').count())
        await pg.locator('#gd-tools button').click(); await pg.wait_for_timeout(500)
        await pg.locator('#modal button.primary:visible').last.click(); await pg.wait_for_timeout(2500)
        await pg.fill('#gd-find',''); await pg.wait_for_timeout(1500)
        print('rows after clear:', await pg.locator('#gd-table tbody tr').count(), await pg.inner_text('#gd-table'))
        print('errs', errs)
        await b.close()
asyncio.run(main())
