import asyncio, sys, re, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'] in ('mail_mode','smtp_host','smtp_port','smtp_security','smtp_auth')}
call('settings',{'settings':{'mail_mode':'smtp','smtp_host':'127.0.0.1','smtp_port':2525,'smtp_security':'none','smtp_auth':'none'}})
print(call('token',{'action':'delete','name':'falco@corpnet.cz'}).get('message')); time.sleep(1.5)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':900,'height':1000})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/'); await pg.wait_for_timeout(800)
        if await pg.locator('button:text-is("CS")').count(): await pg.click('button:text-is("CS")'); await pg.wait_for_timeout(1500)
        await pg.fill('#in-name','falco@corpnet.cz'); await pg.fill('#in-pass','falco-password-1'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.click('.way-tile[data-k=mail]'); await pg.wait_for_timeout(300)
        await pg.fill('.way-dest input[type=email]','falco@corpnet.cz')
        sels=pg.locator('.way-prefs select'); await sels.nth(0).select_option('en'); await sels.nth(1).select_option('text')
        await pg.screenshot(path='/home/claude/shots/p-prefs.png', full_page=True)
        await pg.click('.ways .btn.primary'); await pg.wait_for_timeout(2500)
        m=open('/tmp/claude-0/chal/sink.eml').read()
        print('verify mail english:', 'Checking this address' in m, '| html part:', 'text/html' in m)
        c=re.search(r'^\s+(\d{6})\s*$', m, re.M).group(1)
        await pg.fill('input.codein',c); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        print('errors', errs); await b.close()
asyncio.run(main())
t=call('token&name=falco@corpnet.cz')['token']; print('token:', t.get('kind'), t.get('lang'), t.get('mail_fmt'))
print(call('token',{'action':'enroll','name':'falco@corpnet.cz'}).get('message'))
call('settings',{'settings':keep})
