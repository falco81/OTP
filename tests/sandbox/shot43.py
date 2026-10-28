import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
call('token',{'action':'delete','name':'falco@corpnet.cz'}); print(str(call('token',{'action':'enroll','name':'falco@corpnet.cz','kind':'sms','dest':'+420777111333'}))[:80])
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for lang in ('en','cs'):
            ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1000}); pg=await ctx.new_page()
            await pg.goto('https://127.0.0.1/'); await pg.wait_for_timeout(800)
            await pg.locator('#langpick button', has_text=lang.upper()).first.click(); await pg.wait_for_timeout(400)
            await pg.fill('#in-name','falco@corpnet.cz'); await pg.fill('#in-pass','falco-password-1'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
            await pg.screenshot(path='/home/claude/shots/codes-%s.png'%lang)
        await b.close()
asyncio.run(main())
