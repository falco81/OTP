import asyncio, sys, json, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
call('settings',{'settings':{'admin_show_key':1}})
for nm,extra in [('bk.app@corpnet.cz',{}),('bk.mail@corpnet.cz',{'kind':'mail','dest':'bk.mail@firma.cz'}),('bk.sms@corpnet.cz',{'kind':'sms','dest':'+420777999888'})]:
    call('token',{'action':'delete','name':nm}); call('token',dict({'action':'enroll','name':nm},**extra))
lk=call('tokens-backup',{'q':'name:bk.*','passphrase':'correct-horse-battery'})
open('/tmp/claude-0/fwt/bk.json','w').write(lk['file'])
call('token',{'action':'delete','name':'bk.sms@corpnet.cz'})
app_before=call('token',{'action':'code_now','name':'bk.app@corpnet.cz','first':True}).get('code')
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('request', lambda r: print('REQ', r.method, r.url.split('?')[-1][:40], (r.post_data or '')[:0]) if 'token-import' in r.url else None); pg.on('console', lambda m: print('CONSOLE', m.text[:200]))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        print('header:', await pg.locator('header .host').inner_text())
        await pg.locator('#ov-names > *').first.click(); await pg.wait_for_timeout(2500)
        print('facet ->', repr(await pg.locator('#rq-q').input_value()), await pg.locator('#rq-result').input_value(), '|', await pg.locator('#rq-hours .tp-words').inner_text(), '| clear lit:', await pg.locator('.sb-clear.on').count())
        await pg.screenshot(path='/home/claude/shots/drill2.png')
        await pg.click('#rq-q ~ .sb-clear'); await pg.wait_for_timeout(1500)
        print('clear ->', repr(await pg.locator('#rq-q').input_value()), repr(await pg.locator('#rq-result').input_value()), '|', await pg.locator('#rq-hours .tp-words').inner_text())
        await pg.goto('https://127.0.0.1/admin/#overview'); await pg.wait_for_timeout(2500)
        bars=pg.locator('#ov-chart rect[fill=transparent]')
        n=await bars.count(); clicked=False
        for i in range(n-1,-1,-1):
            cur=await bars.nth(i).evaluate("e=>getComputedStyle(e).cursor")
            if cur=='pointer':
                await bars.nth(i).click(); clicked=True; break
        await pg.wait_for_timeout(2500)
        print('bar ->', clicked, '|', await pg.locator('#rq-hours .tp-words').inner_text(), '|', await pg.locator('#rq-said').inner_text())
        await pg.goto('https://127.0.0.1/admin/#settings/import'); await pg.wait_for_timeout(1500)
        await pg.set_input_files('#imp-files','/tmp/claude-0/fwt/bk.json'); await pg.wait_for_timeout(1500)
        await pg.locator('#modal input[type=password]').fill('correct-horse-battery'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/bk-pick2.png')
        row=pg.locator('#modal tr', has_text='bk.mail@corpnet.cz')
        await row.locator('.bk-seg button.danger').first.click(); await pg.wait_for_timeout(400)
        print('said:', await pg.locator('#modal .said').inner_text())
        await pg.screenshot(path='/home/claude/shots/bk-pick3.png')
        await pg.locator('#modal-foot button.primary').click(); await pg.wait_for_timeout(1200)
        await pg.screenshot(path='/home/claude/shots/bk-confirm.png')
        await pg.locator('#modal-foot button.danger').last.click(); await pg.wait_for_timeout(2500)
        print('result:', (await pg.locator('#imp-out').inner_text())[:300])
        print('errors', errs); await b.close()
asyncio.run(main())
print('app kept as it was:', call('token',{'action':'code_now','name':'bk.app@corpnet.cz','first':True}).get('code')==app_before or 'n/a (time step)')
print('sms restored:', (call('token&name=bk.sms@corpnet.cz').get('token') or {}).get('dest'))
