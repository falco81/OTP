import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':950})
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: print('pageerror', e))
        base='https://127.0.0.1'
        await pg.goto(base+'/admin/'); await pg.wait_for_timeout(800)
        await pg.screenshot(path='/home/claude/shots/cs_door.png')
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass','Admin-Pass-123'); await pg.click('#in-go')
        await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/cs_overview.png')
        for tab in ['tokens','requests','codes','test','events','settings']:
            await pg.click("[data-tab=%s]"%tab); await pg.wait_for_timeout(1500)
            await pg.screenshot(path='/home/claude/shots/cs_%s.png'%tab, full_page=False)
        # leftovers in English
        left = await pg.evaluate("""(function(){var out={};function walk(n){if(n.nodeType===3){var t=n.textContent.trim(); if(/[A-Za-z]{3,}\\s+[a-z]{2,}/.test(t)) out[t]=1;} else if(n.nodeType===1 && !/SCRIPT|STYLE|CODE|TEXTAREA/.test(n.tagName)) n.childNodes.forEach(walk);} walk(document.body); return Object.keys(out);})()""")
        pass
        await pg.click("[data-tab=requests]"); await pg.wait_for_timeout(1500)
        rows = pg.locator('#tab-requests tbody tr:visible')
        if await rows.count():
            await rows.first.click(); await pg.wait_for_timeout(1500)
            await pg.screenshot(path='/home/claude/shots/cs_request_peek.png')
        p2 = await ctx.new_page()
        await p2.goto(base+'/'); await p2.wait_for_timeout(1200)
        await p2.screenshot(path='/home/claude/shots/cs_portal.png', full_page=True)
        await b.close()
asyncio.run(main())
