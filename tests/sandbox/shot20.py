import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
arts=['twostep','recovery']
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':700,'height':900}, device_scale_factor=2)).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        for a in arts:
            print(a, call('art',{'slot':'portal','action':'pick','art':a}).get('portal',{}).get('art'))
            await pg.goto('https://127.0.0.1/'); await pg.wait_for_timeout(1200)
            await pg.locator('svg.signart').screenshot(path='/home/claude/shots/n-%s.png'%a)
        call('art',{'slot':'portal','action':'reset'})
        print('errors', errs); await b.close()
asyncio.run(main())
