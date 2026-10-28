import asyncio, sys, time
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
call('token',{'action':'delete','name':'falco@corpnet.cz'}); r=call('token',{'action':'enroll','name':'falco@corpnet.cz'}); print('enroll', r.get('ok'))
st=call('token',{'action':'get','name':'falco@corpnet.cz'}) if False else None
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1200})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/'); await pg.wait_for_timeout(800)
        await pg.locator('#langpick button', has_text='EN').first.click(); await pg.wait_for_timeout(300)
        await pg.fill('#in-name','falco@corpnet.cz'); await pg.fill('#in-pass','falco-password-1'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        if await pg.locator('input.codein').count():   # first token waiting
            c=call('token',{'action':'code_now','name':'falco@corpnet.cz','first':True}).get('code')
            await pg.fill('input.codein', c); await pg.locator('input.codein').press('Enter'); await pg.wait_for_timeout(1500)
            await pg.reload(); await pg.wait_for_timeout(2000)
        await asyncio.sleep(31)
        c=call('token',{'action':'code_now','name':'falco@corpnet.cz','first':True}).get('code')
        await pg.locator('input[type=password]').fill('falco-password-1')
        boxes=pg.locator('.card input[type=text]')
        await boxes.first.fill(c)
        await pg.locator('.card button.primary').first.click(); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/replace1.png', full_page=True)
        await pg.locator('button', has_text='keep the old token').click(); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/home/claude/shots/replace2.png', full_page=True)
        print('errs', errs); await b.close()
asyncio.run(main())
