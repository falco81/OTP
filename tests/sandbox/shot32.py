import asyncio, sys, os, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
G='/tmp/claude-0/chal/'
for a in ('anna@firma.cz','petr@firma.cz'):
    call('token',{'action':'mail','name':'mq.user@corpnet.cz','mail_to':a,'mail_lang':'cs'})
os.remove(G+'greylist'); open(G+'reject','w').write('1')
call('token',{'action':'mail','name':'mq.user@corpnet.cz','mail_to':'neexistuje@firma.cz','mail_lang':'cs'})
os.remove(G+'reject')
call('token',{'action':'mail','name':'mq.user@corpnet.cz','mail_to':'jana@firma.cz','mail_lang':'cs'})
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/mailq'); await pg.wait_for_timeout(2500)
        await pg.mouse.move(1000,5)
        await pg.screenshot(path='/home/claude/shots/mq-list.png')
        await pg.locator('#mq-table tbody tr').first.click(); await pg.wait_for_timeout(1200)
        await pg.screenshot(path='/home/claude/shots/mq-one.png')
        print('errors', errs); await b.close()
asyncio.run(main())
