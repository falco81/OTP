import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/people'); await pg.wait_for_timeout(3000)
        await pg.locator('#lo-card').scroll_into_view_if_needed()
        await pg.locator('#lo-card').screenshot(path='/home/claude/shots/lo1.png')
        print(await pg.locator('#lo-table').inner_text())
        print("errs", errs); await b.close(); return
        # clear the locked one on nodeb (the other node)
        await pg.locator('#lo-table tr.lo-locked button').first.click(); await pg.wait_for_timeout(9000)
        print('--- after clear one:'); print(await pg.locator('#lo-table').inner_text())
        await pg.click('#lo-tools button'); await pg.wait_for_timeout(400)
        await pg.locator('#modal button', has_text='Vymazat vše').click(); await pg.wait_for_timeout(1500)
        print('--- after all:', await pg.locator('#lo-table').inner_text())
        await pg.goto('https://127.0.0.1/admin/#settings/realms'); await pg.wait_for_timeout(2500)
        await pg.locator('#pane-realms .card').first.screenshot(path='/home/claude/shots/realms.png')
        print('errs', errs); await b.close()
asyncio.run(main())
