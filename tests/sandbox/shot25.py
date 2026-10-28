import asyncio, sys, json, re, urllib.request, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
st=call('settings'); keep={s['key']:s['value'] for s in st['settings'] if s['key'] in ('sms_mode','sms_tel_host','sms_tel_https','sms_tel_user','sms_tel_api')}
call('settings',{'settings':{'sms_mode':'teltonika','sms_tel_host':'127.0.0.1:18110','sms_tel_https':0,'sms_tel_user':'admin','sms_tel_password':'trbsecret','sms_tel_api':'rest'}})
print(call('token',{'action':'enroll','name':'falco@corpnet.cz','kind':'sms','dest':'+420603111222'}).get('message'))
time.sleep(1.5)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1400,'height':1000})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#test'); await pg.wait_for_timeout(1500)
        await pg.fill('#rt-user','falco@corpnet.cz'); await pg.fill('#rt-pass','falco-password-1'); await pg.click('#rt-go'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/rt-chal.png')
        s=json.loads(urllib.request.urlopen('http://127.0.0.1:18110/').read())['sent']; code=re.search(r'\b(\d{6})\b', s[-1]['text']).group(1)
        await pg.fill('.rt-second input', code); await pg.click('.rt-second .btn'); await pg.wait_for_timeout(2000)
        print('result:', await pg.inner_text('.result-big'))
        print('errors', errs); await b.close()
asyncio.run(main())
print(call('token',{'action':'enroll','name':'falco@corpnet.cz'}).get('message'))
call('settings',{'settings':keep})
