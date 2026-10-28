import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1000}); pg=await ctx.new_page()
        reqs=[]; pg.on('request', lambda r: reqs.append(r.url) if 'upload' in r.url or 'upgrade-package' in r.url else None)
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/upgrade'); await pg.wait_for_timeout(2000)
        await pg.set_input_files('#up-file','/home/claude/build/out/otp-1.0.96.tar.gz'); await pg.wait_for_timeout(5000)
        print('requests:', reqs)
        print('said:', (await pg.locator('#modal-body').inner_text())[:200] if await pg.locator('#modal:not([hidden])').count() else 'no modal')
        print('errors', errs); await b.close()
asyncio.run(main())
