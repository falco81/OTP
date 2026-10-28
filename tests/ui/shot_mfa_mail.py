import asyncio, subprocess, os, time, re
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
env=dict(os.environ, OTP_CONFIG='/etc/otp/config.json')
print(subprocess.run(['python3','/usr/local/lib/otp/otp.py','--admin-2fa','on'],env=env,capture_output=True,text=True).stdout)
time.sleep(10)
def code():
    s=open('/tmp/claude-0/chal/sink.eml').read()
    return re.findall(r'Subject:.*?(\d{6})', s)[-1], s
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':960})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.click('.mfa-way >> nth=1'); await pg.wait_for_timeout(300)
        await pg.fill('.mfa-body input', 'boss@example.cz'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(3500)
        await pg.screenshot(path='/home/claude/shots/mfa-mail-sent.png')
        c, eml = code()
        subj=[l for l in eml.split('\n') if l.startswith('Subject:')]; print('mail', subj)
        await pg.fill('.mfa-code', c); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(3000)
        print('in app', await pg.evaluate("!!document.getElementById('me-btn')"))
        await pg.goto('https://127.0.0.1/admin/#settings/texts'); await pg.wait_for_timeout(3000)
        print('texts list has admin', await pg.evaluate("document.getElementById('pane-texts').innerText.indexOf('Administrace')>=0 || document.getElementById('pane-texts').innerText.indexOf('administration')>=0"))
        await pg.screenshot(path='/home/claude/shots/texts-admin.png')
        print('errors', errs)
        await b.close()
asyncio.run(main())
print(subprocess.run(['python3','/usr/local/lib/otp/otp.py','--admin-2fa','status'],env=env,capture_output=True,text=True).stdout)
print(subprocess.run(['python3','/usr/local/lib/otp/otp.py','--admin-2fa','off'],env=env,capture_output=True,text=True).stdout)
subprocess.run(['python3','/usr/local/lib/otp/otp.py','--reset-2fa','admin'],env=env,capture_output=True)
