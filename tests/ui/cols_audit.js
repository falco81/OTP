const { chromium } = require('playwright'); const fs = require('fs');
const PW = fs.readFileSync('/home/claude/run/adminpw', 'utf8').trim();
const TABS = ['overview', 'tokens', 'requests', 'test', 'enrolment', 'events'];
const PANES = process.argv[2] ? process.argv[2].split(',') : ['radius','guard','clients','realms','dir','tokens','codes','texts','portal','import','mail','mailq','people','hisec','web','acme','fw','sshd','sshkeys','network','proxy','time','ha','power','logs','db','backup','carry','alerts','monitor','isemon','siem','osup','upgrade','about'];
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1700, height: 1000 } });
  const pg = await ctx.newPage(); pg.setDefaultTimeout(5000); const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto('https://127.0.0.1/admin/'); await pg.waitForTimeout(800);
  await pg.fill('#in-name', 'admin'); await pg.fill('#in-pass', PW); await pg.keyboard.press('Enter'); await pg.waitForTimeout(2500);
  await pg.evaluate(() => colsReset()); await pg.evaluate(() => colsSwitch(true)); await pg.waitForTimeout(800);
  const where = [...TABS.map(t => '#' + t), ...PANES.map(p => '#settings/' + p)];
  const out = [];
  for (const h of where) {
    await pg.goto('https://127.0.0.1/admin/' + h); await pg.waitForTimeout(3500);
    const tabs = await pg.evaluate(() => {
      document.querySelectorAll('[data-audit-i]').forEach(e => e.removeAttribute('data-audit-i'));
      const vis = e => !!(e.offsetParent || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
      const why = t => {
        if (t.dataset.noCols) return 'data-no-cols';
        if (t.closest('.tip, .no-cols, .helpbox')) return 'inside ' + (t.closest('.tip, .no-cols, .helpbox').className);
        if (!t.tHead) return 'no thead';
        if (t.tHead.rows.length !== 1) return 'thead rows ' + t.tHead.rows.length;
        const c = t.tHead.rows[0].cells; if (c.length < 2) return 'one column';
        for (const x of c) if (x.colSpan > 1) return 'colspan in head';
        return '';
      };
      return [...document.querySelectorAll('table')].filter(vis).map((t, i) => {
        t.dataset.auditI = i;
        const ar = t.closest('[id]');
        const hd = t.tHead ? [...t.tHead.rows[0].cells].map(c => (c.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 6).join(' | ') : (t.rows[0] ? [...t.rows[0].cells].map(c => c.textContent.trim().slice(0, 15)).join(' | ') : '');
        const rows = t.tBodies[0] ? t.tBodies[0].rows.length : 0;
        return { i, id: ar ? ar.id : '', able: t.classList.contains('cols-able'), why: why(t), hd: hd.slice(0, 110), rows,
          grips: t.querySelectorAll('thead .col-grip').length, drag: t.tHead ? [...t.tHead.rows[0].cells].filter(c => c.draggable).length : 0 };
      });
    });
    for (const t of tabs) {
      const r = Object.assign({ at: h }, t);
      if (t.able) {
        // right button on a heading
        try {
        const th = await pg.$(`table[data-audit-i="${t.i}"] thead th:not(.col-hidden)`);
        await th.evaluate(e => e.scrollIntoView({ block: 'center' })); await pg.waitForTimeout(200);
        const bb = await th.boundingBox();
        if (bb) { await pg.mouse.click(bb.x + 10, bb.y + bb.height / 2, { button: 'right' }); await pg.waitForTimeout(250);
          r.menuHead = await pg.evaluate(() => !!document.querySelector('.cols-menu')); await pg.keyboard.press('Escape'); }
        // right button on a body cell
        const td = await pg.$(`table[data-audit-i="${t.i}"] tbody tr:not(.empty-row) td:not(.col-hidden)`);
        if (td) { const tb = await td.boundingBox(); if (tb) { await pg.mouse.click(tb.x + 5, tb.y + tb.height / 2, { button: 'right' }); await pg.waitForTimeout(250);
          r.menuRow = await pg.evaluate(() => !!document.querySelector('.cols-menu')); await pg.keyboard.press('Escape'); } }
        // drag the first heading after the second
        const thl = pg.locator(`table[data-audit-i="${t.i}"] thead th:not(.col-hidden)`);
        const ths = [thl.nth(0), thl.nth(1)];
        if ((await thl.count()) >= 2 && t.drag >= 2) {
          const before = await pg.evaluate(i => [...document.querySelector(`table[data-audit-i="${i}"]`).tHead.rows[0].cells].map(c => c.dataset.ck).join(','), t.i);
          try { await ths[0].dragTo(ths[1], { targetPosition: { x: (await ths[1].boundingBox()).width - 4, y: 8 } }); } catch (e) { r.dragErr = String(e).slice(0, 80); }
          await pg.waitForTimeout(400);
          const after = await pg.evaluate(i => { const t = document.querySelector(`table[data-audit-i="${i}"]`); return t ? [...t.tHead.rows[0].cells].map(c => c.dataset.ck).join(',') : 'gone'; }, t.i);
          r.dragged = before !== after;
          await pg.evaluate(() => { Object.keys(COLS).forEach(k => delete COLS[k]); colsApplyAll(); });
        }
        } catch (e) { r.err = String(e).split('\n')[0].slice(0, 100); }
      }
      out.push(r);
    }
  }
  await pg.evaluate(() => colsReset()); await pg.evaluate(() => colsSwitch(false));
  fs.writeFileSync('/tmp/claude-0/ui/cols_audit.json', JSON.stringify(out, null, 1));
  for (const r of out) console.log([r.at, r.id, r.able ? 'ABLE' : 'NOT(' + r.why + ')', 'rows=' + r.rows, r.able ? `grips=${r.grips} drag=${r.drag} mHead=${r.menuHead} mRow=${r.menuRow} dragged=${r.dragged}${r.dragErr ? ' ' + r.dragErr : ''}${r.err ? ' ERR ' + r.err : ''}` : '', r.hd].join('  '));
  console.log('page errors', errs.length, errs.slice(0, 5).join(' ;; '));
  await b.close();
})();
