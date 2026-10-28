import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050}, accept_downloads=True); pg=await ctx.new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/backup'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/guide0.png')
        await pg.locator('.rb-hero-acts button').last.click(); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/home/claude/shots/guide1.png')
        await pg.locator('.md-doc').evaluate("e=>e.scrollTop=700"); await pg.wait_for_timeout(300)
        await pg.screenshot(path='/home/claude/shots/guide2.png')
        async with pg.expect_download() as dl:
            await pg.locator('#modal button', has_text='RESTORE.md').click()
        d=await dl.value; print('download', d.suggested_filename); await d.save_as('/tmp/guide.md')
        print('errs', errs); await b.close()
asyncio.run(main())
