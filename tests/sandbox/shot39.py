import asyncio, sys, json
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})).new_page()
        pg.on('request', lambda r: print('REQ', r.method, r.url[-40:], (r.post_data or '')[:80]) if r.method=='POST' else None)
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/backup'); await pg.wait_for_timeout(2500)
        await pg.locator('#rb-runs').scroll_into_view_if_needed()
        await pg.screenshot(path='/home/claude/shots/runs1.png')
        n0=await pg.locator('#rb-runs tbody tr').count()
        await pg.locator('#rb-runs tbody tr').first.locator('.rowtools button').click(); await pg.wait_for_timeout(1200)
        print('rows', n0, '->', await pg.locator('#rb-runs tbody tr').count(), '|', await pg.locator('#toast').inner_text())
        await pg.click('#rb-runs-tools button'); await pg.wait_for_timeout(500)
        await pg.screenshot(path='/home/claude/shots/runs2.png')
        print('btns', await pg.locator('#modal button').all_inner_texts()); await pg.locator('#modal button', has_text='Vymazat seznam').click(); await pg.wait_for_timeout(300); await pg.locator('#modal .sure-strip button.danger').click(); await pg.wait_for_timeout(1200)
        print('after clear:', await pg.locator('#rb-runs').inner_text(), '|', await pg.locator('#toast').inner_text())
        # the answering node changes under the page
        await pg.goto('https://127.0.0.1/admin/#settings/ha'); await pg.wait_for_timeout(2500)
        async def swap(route):
            r=await route.fetch(); j=await r.json()
            if 'settings' in j and 'panes' in j: j['node']='otherone'
            await route.fulfill(response=r, json=j)
        await pg.route('**/*api=settings*', swap)
        await pg.evaluate("loadSettings(false)"); await pg.wait_for_timeout(1500)
        print('toast:', await pg.locator('#toast').inner_text())
        await pg.screenshot(path='/home/claude/shots/moved.png')
        print('errs', errs)
        await b.close()
asyncio.run(main())
