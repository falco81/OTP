import asyncio, json
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1400,'height':1100})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        await pg.goto('https://127.0.0.1/admin/#settings/db'); await pg.wait_for_timeout(1500)
        says={"kind":"copy","version":"1.0.63","bytes":123456,"tables":11,"admins":1,"counts":{"accounts":2,"tokens":322,"radius_log":356984,"otp_log":295953},
              "machine":{"config_file":"/etc/otp/config.json","host":"otp2.example.cz","node":"nodea2","in_use":{"db_engine":"postgres","db_host":"127.0.0.1","db_port":5432,"db_name":"optmove","ha_mode":"replicated","ha_slot":2,"ha_peer":"10.0.0.5"},
                         "config":{"db_engine":"postgres","db_password":"(set - not kept in the copy)","node_name":"nodea2"}}}
        await pg.evaluate("askBeforeRestoring(%s, 'otp-x.json.gz', function(){return Promise.resolve({})})" % json.dumps(says))
        await pg.wait_for_timeout(600)
        await pg.click('#modal details summary'); await pg.wait_for_timeout(300)
        await pg.locator('#modal').screenshot(path='/home/claude/shots/restore-info.png')
        print('errors', errs)
        await b.close()
asyncio.run(main())
