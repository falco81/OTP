import asyncio, sys, re, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
for n,k,d,l in (('falco@corpnet.cz','mail','falco@corpnet.cz','en'),('sms.user@corpnet.cz','sms','+420777123456','')):
    call('token',{'action':'delete','name':n}); time.sleep(0.3)
    print(call('token',{'action':'enroll','name':n,'kind':k,'dest':d,'lang':l}).get('message'))
call('token',{'action':'mail_fmt','name':'falco@corpnet.cz','value':'text'})
def q(extra):
    d=call('tokens&q=&state=&limit=500&offset=0'+extra); return d.get('q_error'), sorted(r['name'] for r in d['rows']), d['counts'].get('kind_mail'), d['counts'].get('kind_sms')
from urllib.parse import quote
for e in ('&kind=mail','&kind=sms','&kind=totp','&q='+quote('kind:sms'),'&q='+quote('lang:en'),'&q='+quote('mail:text'),'&q='+quote('to:+420*'),'&q=777123','&q='+quote('kind:fax')):
    r=q(e); print(e, r[0], r[1][:4], len(r[1]), r[2], r[3])
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#tokens'); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/home/claude/shots/tk-table.png')
        await pg.select_option('#tk-kind','mail'); await pg.wait_for_timeout(1200)
        print('rows after kind=mail:', await pg.locator('#tk-table tbody tr').count())
        await pg.select_option('#tk-kind',''); await pg.wait_for_timeout(1000)
        for n,f in (('falco@corpnet.cz','tk-mail'),('sms.user@corpnet.cz','tk-sms')):
            await pg.fill('#tk-q', n.split('@')[0]); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(1200)
            await pg.locator('#tk-table tr', has_text=n).first.click(); await pg.wait_for_timeout(1200)
            sc=await pg.evaluate("""()=>{const r=[];document.querySelectorAll('*').forEach(e=>{const s=getComputedStyle(e);if(/(auto|scroll)/.test(s.overflowY)&&e.scrollHeight>e.clientHeight+2&&e.offsetParent)r.push((e.className||e.tagName)+' '+e.scrollHeight+'/'+e.clientHeight)});return r.concat([document.documentElement.scrollHeight+'/'+innerHeight])}""")
            print(n,'scrollers:',sc)
            await pg.screenshot(path='/home/claude/shots/%s.png'%f)
            await pg.keyboard.press('Escape'); await pg.wait_for_timeout(600)
        await pg.goto('https://127.0.0.1/admin/#settings'); await pg.wait_for_timeout(1200)
        await pg.click('button[data-pane=codes]'); await pg.wait_for_timeout(1000)
        await pg.screenshot(path='/home/claude/shots/set-codes.png')
        print('errors', errs); await b.close()
asyncio.run(main())
