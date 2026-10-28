import asyncio, sys, glob, re, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
SP='/tmp/otpspool'
print(call('token',{'action':'delete','name':'falco@corpnet.cz'}).get('message'))
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':900,'height':1100})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','falco@corpnet.cz'); await pg.fill('#in-pass','falco-password-1'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/p1-choose.png', full_page=True)
        await pg.click('.way-tile[data-k=sms]'); await pg.wait_for_timeout(300)
        await pg.fill('.way-dest input', '603 111 222')
        await pg.screenshot(path='/home/claude/shots/p2-sms.png', full_page=True)
        before=set(glob.glob(SP+'/otp-*'))
        await pg.click('.ways .btn.primary'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/p3-verify.png', full_page=True)
        new=[f for f in glob.glob(SP+'/otp-*') if f not in before]
        txt=open(new[0]).read(); print('SMS:', repr(txt))
        c=re.search(r'\b(\d{6})\b', txt.split('\n\n',1)[1]).group(1)
        await pg.fill('input.codein','000000'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(1500)
        print('wrong said:', await pg.inner_text('.said'))
        await pg.fill('input.codein',c); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.screenshot(path='/home/claude/shots/p4-done.png', full_page=True)
        await pg.click('text=Hotovo') if await pg.locator('text=Hotovo').count() else await pg.click('text=Done')
        await pg.wait_for_timeout(1200)
        await pg.screenshot(path='/home/claude/shots/p5-state.png', full_page=True)
        print('errors', errs); await b.close()
asyncio.run(main())
t=call('token&name=falco@corpnet.cz').get('token') or {}; print('token:', t.get('kind'), t.get('dest'), t.get('state'), t.get('scratch_left'))
