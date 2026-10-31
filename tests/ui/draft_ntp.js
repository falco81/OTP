const L=require('./login.js');
(async()=>{
 const {b,page,reqs}=await L.go();
 await page.evaluate(()=>{location.hash='#settings/time'}); await page.waitForTimeout(4000);
 const loc=page.locator('#ntp-form input[type=checkbox]').first();
 await loc.focus();
 await page.evaluate(()=>{ window.__f=document.getElementById('ntp-form'); window.__in=document.activeElement; window.__d0=NTP.draft; });
 console.log('focused', await page.evaluate(()=>document.activeElement.type+' '+document.activeElement.checked+' manage='+NTP.draft.manage));
 const s=Date.now(); await page.waitForTimeout(10500);
 await page.keyboard.press('Space');
 await page.waitForTimeout(300);
 const r=await page.evaluate(()=>({checkedNow: window.__in.checked, sameDraft: window.__d0===NTP.draft, formKept: window.__f.isConnected, inputConnected: window.__in.isConnected, draftManage: NTP.draft.manage, oldDraftManage: window.__d0.manage, serverManage: NTP.d.conf.manage, pending: !!PENDING.ntp}));
 console.log('ntp polls', reqs.filter(r=>r.t>=s && r.api==='ntp').length, JSON.stringify(r));
 await b.close();
})();
