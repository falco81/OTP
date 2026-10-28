import asyncio, sys, json
sys.argv=['t','none']; exec(open('/tmp/claude-0/up/t_up.py').read().split("if sys.argv[1]=='upload'")[0])
from playwright.async_api import async_playwright
JS="""(function(){var out={};function walk(n){if(n.nodeType===3){var t=n.textContent.trim();if(/[A-Za-z]{3}/.test(t)&&!(n.parentElement&&n.parentElement.closest('[data-no-i18n],.mono,code,pre'))){out[t]=1}}else if(n.nodeType===1&&!/^(SCRIPT|STYLE)$/.test(n.tagName)){if(n.title&&/[A-Za-z]{3}/.test(n.title))out[n.title]=1;if(n.placeholder&&/[A-Za-z]{3}/.test(n.placeholder))out[n.placeholder]=1;for(var c=n.firstChild;c;c=c.nextSibling)walk(c)}}walk(document.querySelector(arguments_sel)||document.body);return Object.keys(out)})()"""
seen=set()
async def grab(pg, sel):
    got=await pg.evaluate(JS.replace('arguments_sel', json.dumps(sel)))
    for t in got: seen.add(t)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1000})).new_page()
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2500)
        await pg.goto('https://127.0.0.1/admin/#settings/backup'); await pg.wait_for_timeout(3000)
        await grab(pg, '#pane-backup')
        await pg.click('#rb-add-host button'); await pg.wait_for_timeout(500); await grab(pg,'#modal')
        for k in range(6):
            await pg.locator('#modal-foot button').first.click(); await pg.wait_for_timeout(300)
            await pg.click('#rb-add-host button'); await pg.wait_for_timeout(400)
            await pg.locator('.rb-kind-tile').nth(k).click(); await pg.wait_for_timeout(600); await grab(pg,'#modal')
        await pg.locator('#modal-foot button').first.click(); await pg.wait_for_timeout(300)
        cards=pg.locator('.rb-card')
        for k in range(await cards.count()):
            await cards.nth(k).locator('.rb-acts button').nth(1).click(); await pg.wait_for_timeout(700); await grab(pg,'#modal')
            await pg.locator('#modal-foot button').first.click(); await pg.wait_for_timeout(300)
        await cards.nth(1).locator('.rb-acts button').nth(2).click(); await pg.wait_for_timeout(2500); await grab(pg,'#modal')
        await pg.locator('#modal-foot button').first.click(); await pg.wait_for_timeout(300)
        await cards.nth(1).locator('.rb-acts button').nth(0).click(); await pg.wait_for_timeout(2500); await grab(pg,'#modal')
        res=await pg.evaluate("(function(a){return a.filter(function(t){return i18nText(t)==null})})(%s)" % json.dumps(sorted(seen)))
        json.dump(res, open('/tmp/claude-0/fwt/untr.json','w'), ensure_ascii=False, indent=0)
        print(len(seen), len(res))
        await b.close()
asyncio.run(main())
