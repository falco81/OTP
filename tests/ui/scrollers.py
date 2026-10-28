import asyncio, sys
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
pane=sys.argv[1] if len(sys.argv)>1 else 'texts'
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})
        pg=await ctx.new_page()
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/'+pane); await pg.wait_for_timeout(3500)
        r = await pg.evaluate("""() => Array.from(document.querySelectorAll('*')).filter(e => { const s=getComputedStyle(e); return /(auto|scroll)/.test(s.overflowY) && e.scrollHeight > e.clientHeight+2 && e.offsetParent; }).map(e => (e.id||'')+'.'+e.className+' '+e.clientHeight+'/'+e.scrollHeight+' '+getComputedStyle(e).maxHeight)""")
        print('\n'.join(r))
        await pg.evaluate("document.querySelector('.ctl-main').scrollTop=600"); await pg.wait_for_timeout(300)
        print('list top after scroll', await pg.evaluate("document.querySelector('.tx-list') && document.querySelector('.tx-list').getBoundingClientRect().top"))
        await pg.screenshot(path='/home/claude/shots/scr-'+pane+'.png')
        await b.close()
asyncio.run(main())
