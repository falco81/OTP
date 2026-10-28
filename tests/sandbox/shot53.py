import asyncio, sys, subprocess
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1000})).new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/backup'); await pg.wait_for_timeout(2500)
        await pg.click('#rb-add-host button'); await pg.wait_for_timeout(500)
        await pg.locator('.rb-kind-tile').nth(3).click(); await pg.wait_for_timeout(700)
        inp=pg.locator('#modal input[type=text]')
        await inp.nth(0).fill('ssh key box'); await inp.nth(1).fill('127.0.0.1'); await inp.nth(2).fill('2222'); await inp.nth(3).fill('uikey/otp'); await inp.nth(4).fill('rbtest')
        await pg.locator('#modal button:has-text("Make a key here"), #modal button:has-text("Vytvořit klíč")').first.click(); await pg.wait_for_timeout(2500)
        pub=await pg.locator('#modal .rb-keybox pre').first.inner_text()
        print('pub', pub[:40])
        open('/home/rbtest/.ssh/authorized_keys','a').write(pub.strip()+'\n')
        await pg.locator('#modal-foot button').nth(1).click(); await pg.wait_for_timeout(3000)
        print('try1', (await pg.locator('#rb-try-out').inner_text())[:200].replace('\n',' | '))
        await pg.locator('#rb-try-out button').first.click(); await pg.wait_for_timeout(5000)
        print('try2', (await pg.locator('#rb-try-out').inner_text())[:300].replace('\n',' | '))
        await pg.screenshot(path='/home/claude/shots/s109-sftp-try.png')
        await pg.locator('#modal-foot button').nth(2).click(); await pg.wait_for_timeout(2000)
        # back up now
        await pg.click('#rb-now'); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/home/claude/shots/s109-running.png')
        for i in range(90):
            await pg.wait_for_timeout(2000)
            if await pg.locator('#rb-going').is_hidden(): break
        await pg.wait_for_timeout(2500)
        await pg.screenshot(path='/home/claude/shots/s109-after.png')
        print('hero', (await pg.locator('.rb-hero b').first.inner_text()))
        print('errors', errs); await b.close()
asyncio.run(main())
