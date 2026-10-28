import asyncio, json
from playwright.async_api import async_playwright
PW=open('/home/claude/run/adminpw').read().strip()
JS = r"""(root) => {
  const out = new Set();
  const walk = (n) => {
    if (n.nodeType === 1) {
      if (n.hasAttribute('data-no-i18n') || ['SCRIPT','STYLE','PRE','CODE'].includes(n.tagName)) return;
      ['title','placeholder'].forEach(a => { const v = n.getAttribute(a); if (v) out.add(v.trim()); });
      n.childNodes.forEach(walk);
    } else if (n.nodeType === 3) { const t = n.textContent.trim(); if (t) out.add(t); }
  };
  document.querySelectorAll(root).forEach(walk);
  return [...out].filter(t => /[a-z]{3}/i.test(t) && !/[ěščřžýáíéůúňťď]/i.test(t));
}"""
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(ignore_https_errors=True, viewport={'width':1600,'height':1000})
        pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('https://127.0.0.1/admin/'); await pg.wait_for_timeout(600)
        await pg.fill('#in-name','admin'); await pg.fill('#in-pass',PW); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(2000)
        got=set()
        await pg.goto('https://127.0.0.1/admin/#settings/fw'); await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.fw-other').open=true")
        got |= set(await pg.evaluate(JS, '#pane-fw, #ctl-nav'))
        await pg.click('text=Add a rule') if await pg.locator('text=Add a rule').count() else await pg.click('.fw-h .btn')
        await pg.wait_for_timeout(500); got |= set(await pg.evaluate(JS, '#modal')); await pg.evaluate('closeModal()')
        await pg.evaluate("document.querySelector('#fw-master input').click()"); await pg.wait_for_timeout(500)
        got |= set(await pg.evaluate(JS, '#modal')); await pg.evaluate('closeModal()')
        await pg.goto('https://127.0.0.1/admin/#settings/ha'); await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelectorAll('.lb-guide').forEach(d=>d.open=true)"); await pg.wait_for_timeout(300)
        got |= set(await pg.evaluate(JS, '#pane-ha'))
        await pg.click('#ha-history'); await pg.wait_for_timeout(1200); got |= set(await pg.evaluate(JS, '#modal')); await pg.evaluate('closeModal()')
        await pg.evaluate("haErrors()"); await pg.wait_for_timeout(9000); got |= set(await pg.evaluate(JS, '#modal'))
        await pg.evaluate("document.querySelectorAll('#modal .seg button')[1].click()"); await pg.wait_for_timeout(300); got |= set(await pg.evaluate(JS, '#modal'))
        print(json.dumps(sorted(got), ensure_ascii=False, indent=0)); print('errors', errs)
        await b.close()
asyncio.run(main())
