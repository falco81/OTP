import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1900,'height':1000})).new_page()
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.evaluate("localStorage.setItem('otp-rail-pinned','1')"); await pg.goto('https://127.0.0.1/admin/#settings/texts'); await pg.reload(); await pg.wait_for_timeout(3000)
        print(await pg.evaluate("""(function(){var l=document.querySelector('.tx-list');var out=[];for(var e=l.parentElement;e;e=e.parentElement){var cs=getComputedStyle(e);out.push((e.id||e.className).toString().slice(0,40)+' ov='+cs.overflowY+'/'+cs.overflowX+' h='+e.clientHeight+'/'+e.scrollHeight)};return out.join('\\n')})()"""))
        await pg.evaluate("document.querySelector('.ctl-main') && (document.querySelector('.ctl-main').scrollTop=0)")
        await pg.wait_for_timeout(400)
        print(await pg.evaluate("JSON.stringify(document.querySelector('.tx-list').getBoundingClientRect())"))
        await pg.evaluate("document.querySelector('.tx-ed').scrollTop=700")
        await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/s108-texts.png')
        await b.close()
asyncio.run(main())
