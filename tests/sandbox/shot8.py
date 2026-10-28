import asyncio, time
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True)
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        hung=[]
        async def hang(route):
            hung.append(route)          # never answered: a connection that died with the VIP move
        await pg.route('**/admin/?api=status*', hang)
        t=time.time()
        r=await pg.evaluate("api('status', undefined, 3).then(function(){return 'answered'}, function(e){return 'refused: '+e.message+' unreachable='+e.unreachable})")
        print(r, '%.1fs'%(time.time()-t))
        await pg.unroute('**/admin/?api=status*')
        r=await pg.evaluate("api('status').then(function(d){return 'next one answered: '+(d.version||'?')}, function(e){return 'refused '+e.message})")
        print(r); print('errors', errs)
        await b.close()
asyncio.run(main())
