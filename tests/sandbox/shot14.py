import asyncio, json, sys
sys.argv=['t','none']
exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':1100})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/portal'); await pg.wait_for_timeout(1500)
        await pg.evaluate("showPane('portal')"); await pg.wait_for_timeout(1500)
        await pg.locator('#art-card').screenshot(path='/home/claude/shots/artpick.png')
        await pg.click('#art-slot button[data-slot=admin]'); await pg.wait_for_timeout(500)
        await pg.locator('#art-card').screenshot(path='/home/claude/shots/artpick-admin.png')
        await pg.click('#art-slot button[data-slot=portal]'); await pg.wait_for_timeout(300)
        await pg.click('.art-tile:nth-child(4)'); await pg.wait_for_timeout(1200)
        print('picked:', await pg.inner_text('.art-tile.on .art-cap'))
        p2=await (await b.new_context(ignore_https_errors=True, viewport={'width':900,'height':800})).new_page()
        for a in ['phone']:
            call('art', {'action':'pick','art':a})
            await p2.goto('https://127.0.0.1/'); await p2.wait_for_timeout(900)
            await p2.locator('.signin').screenshot(path='/home/claude/shots/art-%s.png'%a)
        print('errors', errs); await b.close()
asyncio.run(main())
