import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
print(call('token',{'action':'enroll','name':'falco@corpnet.cz','kind':'mail','dest':'falco@corpnet.cz'}).get('message'))
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':700})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','falco@corpnet.cz'); await pg.fill('#in-pass','falco-password-1'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/reissue-mail.png')
        print('errors', errs); await b.close()
asyncio.run(main())
print(call('token',{'action':'enroll','name':'falco@corpnet.cz'}).get('message'))
