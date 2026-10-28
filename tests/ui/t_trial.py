import asyncio, sys, json
sys.argv=['x','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
fw=call('firewall',None); rules=(fw.get('conf') or {}).get('rules') or []
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True,viewport={'width':1400,'height':800})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(800)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.click('#in-go'); await pg.wait_for_timeout(2000)
        call('firewall',{'action':'rule_add','rule':{'family':4,'proto':'tcp','port':'2299','source':'192.0.2.97','action':'drop','note':'banner test'}})
        await pg.wait_for_timeout(12000)
        await pg.screenshot(path='/home/claude/shots/trial.png')
        print('banner:', (await pg.inner_text('#trials'))[:300].replace('\n',' | '))
        await pg.locator('#trials button.primary').first.click(); await pg.wait_for_timeout(4000)
        print('hidden after keep:', await pg.evaluate("document.getElementById('trials').hidden"))
        print('errs', errs)
        await b.close()
asyncio.run(main())
fw=call('firewall',None)
for x in (fw.get('conf') or {}).get('rules') or []:
    if x.get('note')=='banner test': call('firewall',{'action':'rule_drop','id':x['id']})
print(call('trial',{'kind':'fw','action':'keep'}))
