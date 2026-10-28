import asyncio, sys
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
print(call('mail',{'action':'mail_of','user':'marta@corpnet.cz'}))
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1920,'height':1050})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#tokens'); await pg.wait_for_timeout(1200)
        async def state(tag):
            d=pg.locator('#modal input.mono').nth(1)
            print(tag, '|', await d.input_value(), '|', await pg.locator('.dest-said').inner_text())
        for who in ('marta@corpnet.cz','falco@corpnet.cz'):
            await pg.click('#tk-add'); await pg.wait_for_timeout(700)
            await pg.locator('#modal input.mono').first.fill(who); await pg.keyboard.press('Tab'); await pg.wait_for_timeout(1200)
            sel=pg.locator('#modal select').first
            await sel.select_option('sms'); await pg.wait_for_timeout(800); await state(who+' sms')
            if who.startswith('marta'): await pg.screenshot(path='/home/claude/shots/mk-sms.png')
            await sel.select_option('mail'); await pg.wait_for_timeout(500); await state(who+' mail')
            await pg.locator('#modal input.mono').nth(1).fill('jina@example.cz'); await pg.wait_for_timeout(200); await state(who+' typed')
            await sel.select_option('sms'); await pg.wait_for_timeout(300); await state(who+' sms again')
            await pg.keyboard.press('Escape'); await pg.wait_for_timeout(600)
        await pg.goto('https://127.0.0.1/'); await pg.wait_for_timeout(800)
        if await pg.locator('button:text-is("CS")').count(): await pg.click('button:text-is("CS")'); await pg.wait_for_timeout(1200)
        await pg.fill('#in-name','marta@corpnet.cz'); await pg.fill('#in-pass','marta-password-1'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        if await pg.locator('.way-tile[data-k=mail]').count():
            await pg.click('.way-tile[data-k=mail]'); await pg.wait_for_timeout(400)
            print('portal sms:', await pg.locator('input[type=email]').first.input_value())
        else:
            print('portal: no sms tile')
        await pg.screenshot(path='/home/claude/shots/portal-sms.png')
        print('errors', errs); await b.close()
asyncio.run(main())
