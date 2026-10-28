import asyncio, sys, json, re, urllib.request, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'] in ('sms_mode','sms_tel_host','sms_tel_https','sms_tel_user','sms_tel_api')}
call('settings',{'settings':{'sms_mode':'teltonika','sms_tel_host':'127.0.0.1:18110','sms_tel_https':0,'sms_tel_user':'admin','sms_tel_password':'trbsecret','sms_tel_api':'rest'}})
print(call('token',{'action':'delete','name':'falco@corpnet.cz'}).get('message')); time.sleep(1.5)
def sent(): return json.loads(urllib.request.urlopen('http://127.0.0.1:18110/').read())['sent']
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':900,'height':900})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/'); await pg.wait_for_timeout(800)
        if await pg.locator('button:text-is("EN")').count(): await pg.click('button:text-is("EN")'); await pg.wait_for_timeout(1500)
        await pg.fill('#in-name','falco@corpnet.cz'); await pg.fill('#in-pass','falco-password-1'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        print('page lang:', await pg.evaluate('window.OTP_LANG'))
        await pg.click('.way-tile[data-k=sms]'); await pg.fill('.way-dest input','603 111 222'); n=len(sent())
        await pg.click('.ways .btn.primary'); await pg.wait_for_timeout(3000)
        s=sent()[n:]; print('verify SMS:', s[-1]['text'] if s else None)
        c=re.search(r'\b(\d{6})\b', s[-1]['text']).group(1)
        await pg.fill('input.codein',c); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        print('errors', errs); await b.close()
asyncio.run(main())
t=call('token&name=falco@corpnet.cz')['token']; print('token:', t.get('kind'), t.get('lang'))
print(call('token',{'action':'enroll','name':'falco@corpnet.cz'}).get('message'))
call('settings',{'settings':keep})
