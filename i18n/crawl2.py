import sys, asyncio, json
from playwright.async_api import async_playwright
SEEN = set()
INIT = """
window.OTP_LANG_PACK = {code: 'cs', strings: {'zz never zz': 'x'}, patterns: [], rich: {}};
window.__seen = {}; window.__rich = {};
document.addEventListener('DOMContentLoaded', function () {
  var orig = window.i18nText;
  if (orig) window.i18nText = function (s, depth) { if (!depth) window.__seen[s] = 1; return orig(s, depth); };
  if (window.I18N && I18N.rich) { var rg = I18N.rich.get.bind(I18N.rich); I18N.rich.get = function (k) { window.__rich[k] = 1; return rg(k); }; }
});
"""
async def grab(pg):
    try:
        got = await pg.evaluate("Object.keys(window.__seen||{}).concat(Object.keys(window.__rich||{}).map(function(k){return 'RICH:'+k}))")
        SEEN.update(got)
    except Exception as e: print('grab fail', e)
async def run(pg, steps):
    for c in steps:
        try:
            if c.startswith('js:'): await pg.evaluate(c[3:])
            elif c.startswith('fill:'):
                sel,val=c[5:].split('=',1); await pg.fill(sel,val)
            elif c.startswith('wait:'): await pg.wait_for_timeout(int(c[5:]))
            else: await pg.click(c, timeout=4000)
            await pg.wait_for_timeout(900)
            await grab(pg)
        except Exception as e: print('step fail', c, str(e)[:120])
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(ignore_https_errors=True, viewport={'width':1500,'height':950})
        await ctx.add_init_script(INIT)
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: print('pageerror', e)); pg.on('console', lambda m: m.type=='error' and print('console', m.text))
        base='https://127.0.0.1'
        # admin door
        await pg.goto(base+'/admin/'); await pg.wait_for_timeout(800); await grab(pg)
        await run(pg, ['fill:#in-name=admin','fill:#in-pass=wrong','#in-go','wait:800'])
        await run(pg, ['fill:#in-name=admin','fill:#in-pass=Admin-Pass-123','#in-go','wait:2500'])
        steps = ['#me-btn','js:closeModal()','button[data-tab=tokens]','#tk-table tbody tr >> nth=0','text=Show the QR code and key','text=Show it','wait:800','js:closeModal()','#tk-add','js:closeModal()',
          'js:tokenPeek("nobody@corpnet.cz")','wait:800','js:closeModal()',
          'button[data-tab=requests]','#rq-table tbody tr >> nth=0','js:closeModal()','#rq-forget','js:closeModal()','button[data-tab=codes]','#cd-table tbody tr >> nth=0','wait:500','js:closeModal()','#cd-forget','js:closeModal()','button[data-tab=test]',
          'fill:#rt-user=falco','fill:#rt-pass=000000','#rt-go','wait:1500','js:document.getElementById("rt-how").value="direct";document.getElementById("rt-how").onchange()','#rt-go','wait:1500',
          'button[data-tab=events]','#log-read','button[data-tab=settings]']
        for pane in ['radius','clients','realms','dir','tokens','portal','import','isemon','people','db','carry','about']:
            steps.append('button[data-pane=%s]' % pane)
            if pane=='clients': steps += ['#cl-table tbody tr >> nth=0','js:closeModal()','#cl-add','js:closeModal()']
            if pane=='realms': steps += ['#rl-table tbody tr >> nth=0','.groupbrowser .btn >> nth=0','wait:1500','js:closeModal()','#rl-add','js:closeModal()']
            if pane=='dir': steps += ['#ad-table tbody tr >> nth=0','js:closeModal()','#ad-add','js:closeModal()','text=Check it >> nth=1','wait:1500','js:closeModal()','text=Check it >> nth=0','wait:2500','js:closeModal()']
            if pane=='people': steps += ['#us-add','js:closeModal()','#ag-find','wait:1500','#ag-try','js:closeModal()']
            if pane=='db': steps += ['#db-engine-test','wait:800','#db-engine-move','js:closeModal()','#db-engine-use','js:closeModal()','#db-prune','js:closeModal()','#db-check','wait:800','js:closeModal()','#db-optimize','js:closeModal()','#db-engine-setup','js:closeModal()']
        steps += ['js:document.querySelector("#ctl-find").value="port";document.querySelector("#ctl-find").dispatchEvent(new Event("input"))',
                  'button[data-tab=overview]','wait:1500']
        await run(pg, steps)
        # hover every element with a help panel to collect its words
        await pg.evaluate("""document.querySelectorAll('[data-explains]').forEach(function(n){ if(n._explainHtml){ var d=document.createElement('div'); d.innerHTML=n._explainHtml; document.body.appendChild(d);} })""")
        await pg.wait_for_timeout(800); await grab(pg)
        # portal
        pg2 = await ctx.new_page()
        await pg2.goto(base+'/'); await pg2.wait_for_timeout(800); await grab(pg2)
        await run(pg2, ['fill:#in-name=outsider@corpnet.cz','fill:#in-pass=outsider-password-1','#in-go','wait:1500',
                        'fill:#in-name=falco@corpnet.cz','fill:#in-pass=falco-password-1','#in-go','wait:2500',
                        'js:document.querySelector("input[type=password]").value="falco-password-1"','js:document.querySelector("input.mono").value="000000"','text=Make a new token','wait:1500'])
        await b.close()
    json.dump(sorted(SEEN), open('seen.json','w'), ensure_ascii=False, indent=0)
    print(len(SEEN))
asyncio.run(main())
