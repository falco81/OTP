import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
print(call('realms',{'action':'save','realm':{'name':'corp2.local','suffix':'corp2.local','directory':'MOCK','lookup':'sam','auth_mode':'otp','groups':[{'group':'ISE Admins'}],'methods':['totp']}}).get('message'))
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1100})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/realms'); await pg.wait_for_timeout(2500)
        await pg.locator('tr', has_text='corp.test').first.click(); await pg.wait_for_timeout(1000)
        box=pg.locator('#modal input[placeholder="example.local, example.com"]')
        await box.fill('corp.local, corp2.local')
        await pg.locator('#modal-foot button.primary').click(); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/home/claude/shots/absorb.png')
        await pg.locator('#modal button', has_text='Take it in').last.click() if await pg.locator('#modal button', has_text='Take it in').count() else None
        await pg.wait_for_timeout(2000)
        await pg.locator('#pane-realms .card').first.screenshot(path='/home/claude/shots/realms3.png')
        print('errs', errs); await b.close()
asyncio.run(main())
r=[x for x in call('realms')['realms'] if x['name']=='corp.test'][0]; print(r['aliases'], [g['group'] for g in r['groups']], [x['name'] for x in call('realms')['realms']])
