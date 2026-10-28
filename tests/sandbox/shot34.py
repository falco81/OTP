import asyncio, sys, re, time, os
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'] in ('mail_mode','smtp_host','smtp_port','smtp_security','smtp_auth')}
call('settings',{'settings':{'mail_mode':'smtp','smtp_host':'127.0.0.1','smtp_port':2525,'smtp_security':'none','smtp_auth':'none'}})
call('token',{'action':'delete','name':'falco@corpnet.cz'}); time.sleep(1.5)
SINK='/tmp/claude-0/chal/sink.eml'
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':900,'height':1000})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','falco@corpnet.cz'); await pg.fill('#in-pass','falco-password-1'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.click('.way-tile[data-k=mail]'); await pg.wait_for_timeout(300)
        await pg.fill('input[type=email]','falco@corpnet.cz')
        await pg.click('.ways .btn.primary'); await pg.wait_for_timeout(2500)
        first=re.search(r'^\s+(\d{6})\s*$', open(SINK).read(), re.M).group(1)
        await pg.reload(); await pg.wait_for_timeout(2500)
        n=await pg.locator('button:has-text("again"), button:has-text("znovu")').count()
        print('send again after reload:', n)
        if n:
            os.remove(SINK)
            await pg.locator('button:has-text("again"), button:has-text("znovu")').first.click(); await pg.wait_for_timeout(2500)
            m=open(SINK).read() if os.path.exists(SINK) else ''
            second=re.search(r'^\s+(\d{6})\s*$', m, re.M)
            print('a new code went to the same address:', bool(second) and second.group(1)!=first, 'To: falco@corpnet.cz' in m or 'falco@corpnet.cz' in m)
            await pg.fill('input.codein', second.group(1)); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.screenshot(path='/home/claude/shots/portal-again.png')
        print('errors', errs); await b.close()
asyncio.run(main())
t=call('token&name=falco@corpnet.cz').get('token') or {}; print('token made:', t.get('kind'), t.get('dest'))
call('settings',{'settings':keep})
