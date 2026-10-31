const L=require('./login.js');
(async()=>{
 const {b,page,reqs}=await L.go();
 await page.evaluate(()=>{location.hash='#settings/fw'}); await page.waitForTimeout(5000);
 await page.locator('#pane-fw textarea').first().focus();
 await page.evaluate(()=>{ window.__in=document.activeElement; window.__d0=FW.draft; });
 const s=Date.now(); await page.waitForTimeout(6500);
 await page.keyboard.type('10.99.0.0/16');
 const r=await page.evaluate(()=>{ const keys=Object.keys(FW.draft.access||{}); return {typed: window.__in.value, kept: window.__in.isConnected, sameDraft: window.__d0===FW.draft,
   newDraftFrom: keys.map(k=>k+'='+JSON.stringify((FW.draft.access[k]||{}).from)).join(' '), oldDraftFrom: keys.map(k=>k+'='+JSON.stringify((window.__d0.access[k]||{}).from)).join(' '), changedFlag: FW.draft.access_changed, pending: !!PENDING.fw}; });
 console.log('firewall polls', reqs.filter(r=>r.t>=s && r.api==='firewall').length, JSON.stringify(r,null,1));
 await b.close();
})();
