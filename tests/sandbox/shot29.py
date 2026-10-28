import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'] in ('sms_mode','sms_tel_host','sms_tel_user','sms_tel_https')}
call('settings',{'settings':{'sms_mode':'teltonika','sms_tel_host':'192.168.47.254','sms_tel_user':'admin','sms_tel_https':1}})
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/codes'); await pg.wait_for_timeout(2000)
        await pg.mouse.move(1000,5)
        await pg.screenshot(path='/home/claude/shots/sms-tel.png', full_page=True)
        for m in ('teltonika','http','spool','off'):
            await pg.select_option('#set-sms_mode', m); await pg.wait_for_timeout(500)
            await pg.evaluate("document.querySelector('#set-sms_mode').scrollIntoView({block:'start'})"); await pg.wait_for_timeout(300)
            await pg.screenshot(path='/home/claude/shots/sms-%s.png'%m)
        await pg.set_viewport_size({'width':1280,'height':900}); await pg.select_option('#set-sms_mode','teltonika'); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('#set-sms_mode').scrollIntoView({block:'start'})"); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/sms-1280.png')
        print('errors', errs); await b.close()
asyncio.run(main())
call('settings',{'settings':keep})
