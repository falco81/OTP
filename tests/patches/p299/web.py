# 1.0.299 web: the upgrade band - every page follows an upgrade while the things that serve it
# restart, and loads the new version by itself, once.   python3 web.py OUTDIR
import sys
W = sys.argv[1].rstrip('/') + '/web/'
D = W + 'assets/'


def edit(f, pairs, base=D):
    s = open(base + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(base + f, 'w').write(s)


edit('admin/index.php', [
("""<div id="offline" class="offline" hidden></div>
<div id="phpsafety" """,
 """<div id="upband" class="upband" hidden aria-live="polite"></div>
<div id="offline" class="offline" hidden></div>
<div id="phpsafety" """),
], base=W)

edit('core.js', [
("""    var err = new Error(late ? 'the server did not answer in ' + limit + ' s'
                             : 'the server could not be reached');
    err.unreachable = true;
    throw err;""",
 """    var err = new Error(late ? 'the server did not answer in ' + limit + ' s'
                             : 'the server could not be reached');
    err.unreachable = true;
    /* nginx and PHP restarting in an upgrade the page knows of (1.0.299): expected. */
    if (typeof upgradeExpected === 'function' && upgradeExpected()) err.upgrading = true;
    throw err;"""),
("""        if (r.status === 502 || r.status === 503 || r.status === 504) {
          var down = new Error('the server is not answering just now - try again in a moment');
          down.unreachable = true;     /* nginx with nothing behind it - a restart */
          throw down;
        }""",
 """        if (r.status === 502 || r.status === 503 || r.status === 504) {
          var down = new Error('the server is not answering just now - try again in a moment');
          down.unreachable = true;     /* nginx with nothing behind it - a restart */
          if (typeof upgradeExpected === 'function' && upgradeExpected()) down.upgrading = true;
          throw down;
        }"""),
("""      if (r.status === 503 && data && data.busy) {""",
 """      if (r.status === 503 && data && data.upgrading && typeof data.upgrading === 'object') {
        /* The daemon away while this node is upgraded (1.0.299): how far it is, from the file
           the pages read themselves - expected, never a red toast. */
        if (typeof upgradeHeard === 'function') upgradeHeard(data.upgrading, 'api');
        var up = new Error(data.error || 'otp is being upgraded - back in a moment');
        up.status = 503;
        up.unreachable = true;
        up.upgrading = data.upgrading.state === 'running';
        up.data = data;
        throw up;
      }
      if (r.status === 503 && data && data.busy) {"""),
("""function oops(e) {
  if (e && e.stopped) return;           /* somebody stopped it: not a fault */""",
 """function oops(e) {
  if (e && e.stopped) return;           /* somebody stopped it: not a fault */
  /* An upgrade restarting what answers these pages (1.0.299): the band says so, once. */
  if (e && (e.upgrading || (e.unreachable && typeof upgradeExpected === 'function' && upgradeExpected()))) return;"""),
])

BAND = r"""
/* ---- the upgrade band (1.0.299) -------------------------------------------
   How far an upgrade is, on every page, under the header - while the very things that serve these
   pages restart: the daemon and its API, nginx and PHP. Two sources: the cluster's plan, in every
   status whichever node answers (behind the VIP address, the other node while this one is done),
   and this node's own file (.upgrade.json, root's, read by PHP from the disk) - in the status
   while the daemon answers, in its 503 while it does not, from ?api=upgrade-state while PHP
   answers alone. While one is known the page asks every 2 s, says "restarting" rather than
   "down", and when the version it is upgraded to answers it loads that version's pages itself,
   once - never back to an older one behind a VIP address that moved. */
var UPG = {plan: null, u: null, away: 0, phpAway: false, sawRunning: false, target: '',
           reloading: false, offer: '', timer: null};
function upgHidden(id) { try { return !!id && localStorage.getItem('otp.upg.hide') === id; } catch (e) { return false; } }
function upgHide(id) { try { localStorage.setItem('otp.upg.hide', id); } catch (e) { } }
function upgradeRunning() {
  return !!((UPG.plan && UPG.plan.state === 'running') || (UPG.u && UPG.u.state === 'running'));
}
function upgradeExpected() {
  return upgradeRunning() || UPG.reloading;
}
/* This node's file, from a 503 of the relay or from ?api=upgrade-state: the API is away. */
function upgradeHeard(u, from) {
  if (!u || typeof u !== 'object' || !u.version) return;
  if (typeof UP_STATE === 'undefined') { setTimeout(function () { upgradeHeard(u, from); }, 0); return; }
  UPG.u = u;
  if (from !== 'status') {
    if (!UPG.away) UPG.away = Date.now();
    UPG.phpAway = false;
  }
  upgradeNote();
}
/* Which to show (1.0.299): the plan of the cluster - unless it has ended and this node's file
   says another upgrade (one by hand on the command line after it) runs or ended after it. */
function upgPick() {
  var p = UPG.plan, u = UPG.u;
  if (p && u && p.state !== 'running' && (u.state === 'running' || (u.id && p.id && u.id !== p.id && Number(u.at || 0) > Number(p.ended || 0)))) p = null;
  if (p && u && u.id && p.id && u.id !== p.id && p.state === 'running') u = null;
  return {p: p, u: u};
}
function upgradeNote() {
  var pk = upgPick(), p = pk.p, u = pk.u;
  if (upgradeRunning()) UPG.sawRunning = true;
  UPG.target = (p && p.version) || (u && u.version) || UPG.target;
  drawUpband();
  upgLoop();
}
/* Every status: the plan and the file as they are now - the API answers. */
function upgradeFromStatus(s) {
  if (!s) return;
  /* The page's first status is painted before the rest of this script has run: after it. */
  if (typeof UP_STATE === 'undefined' || typeof VERSION_LOADED === 'undefined') { setTimeout(function () { upgradeFromStatus(s); }, 0); return; }
  UPG.away = 0;
  UPG.phpAway = false;
  UPG.plan = s.upgrading && s.upgrading.version ? s.upgrading : null;
  UPG.u = s.upgrade_file && s.upgrade_file.version ? s.upgrade_file : null;
  upgradeNote();
  /* The version it was upgraded to answers here now: that version's pages, loaded once. */
  var to = UPG.target, pk = upgPick();
  var ended = (pk.p && pk.p.state === 'done') || (pk.u && pk.u.state === 'done');
  if (to && s.version === to && VERSION_LOADED && VERSION_LOADED !== to && (UPG.sawRunning || ended)) upgradeReload(to);
}
/* A tick that found nothing answering: away, if an upgrade is expected - true then. */
function upgradeAway(e) {
  if (!(e && e.upgrading) && !upgradeExpected()) return false;
  if (!UPG.away) UPG.away = Date.now();
  upgPill();
  drawUpband();
  upgLoop();
  return true;
}
function upgPill() {
  var pill = $('state-pill');
  if (!pill || !UPG.away) return;
  pill.className = 'pill warn';
  pill.lastChild.textContent = 'in maintenance';
}
function upgradeReload(to) {
  var done = '';
  try { done = sessionStorage.getItem('otp.upg.reload') || ''; } catch (e) { }
  /* A popup only when something is being typed into it: one that tells something closes with the page. */
  var pop = $('modal') && !$('modal').hidden ? $('modal') : null;
  var typing = !!pop && Array.prototype.some.call(pop.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]),textarea'),
    function (x) { return x.value !== x.defaultValue || document.activeElement === x; });
  var unsaved = Object.keys(DIRTY || {}).length || (typeof PENDING === 'object' && Object.keys(PENDING || {}).length) || typing;
  if (done === to || unsaved) {
    UPG.why = done === to ? 'once' : (Object.keys(DIRTY || {}).length ? 'unsaved' : 'a popup open');
    UPG.offer = to; drawUpband(); return;
  }
  try { sessionStorage.setItem('otp.upg.reload', to); } catch (e) { }
  UPG.reloading = true;
  drawUpband();
  setTimeout(function () { location.reload(); }, 700);
}
function upgLoop() {
  var want = upgradeRunning() || UPG.reloading || (UPG.away && Date.now() - UPG.away < 30 * 60000);
  if (!want) { clearTimeout(UPG.timer); UPG.timer = null; return; }
  if (UPG.timer) return;
  UPG.timer = setTimeout(function () {
    UPG.timer = null;
    if (document.hidden || UPG.reloading) { upgLoop(); return; }
    api('status', undefined, 6).then(function (s) {
      $('offline').hidden = true;
      paintHeader(s);
    }).catch(function (e) {
      if (e && e.busy) return;
      if (!UPG.away) UPG.away = Date.now();
      if (e && e.data && e.data.upgrading) return;           /* heard already, from PHP */
      return fetch('?api=upgrade-state', {credentials: 'same-origin', cache: 'no-store'}).then(function (r) {
        return r.json();
      }).then(function (d) {
        UPG.phpAway = false;
        if (d && d.upgrading) upgradeHeard(d.upgrading, 'state');
      }).catch(function () { UPG.phpAway = true; });
    }).then(function () {
      if (UPG.away) { $('offline').hidden = true; upgPill(); }
      drawUpband();
      upgLoop();
    });
  }, 2000);
}
function upgSince(t) {
  var s = Math.max(0, Math.round(Date.now() / 1000 - Number(t || 0)));
  return s < 60 ? s + ' s' : Math.floor(s / 60) + ' min ' + (s % 60) + ' s';
}
/* How far, 0-100: the plan by its nodes (the one this file is of by the file's steps), or the file. */
function upgPercent(p, u) {
  if (p) {
    var steps = p.steps || [];
    if (!steps.length) return 0;
    var sum = steps.reduce(function (m, st) {
      if (st.state === 'installing' && u && u.id === p.id && u.node === st.name && u.parts)
        return m + Math.round(20 + 62 * Math.min(1, Math.max(0, u.part - 1) / u.parts));
      return m + upPercent(st, p);
    }, 0);
    return Math.round(sum / steps.length);
  }
  if (!u) return 0;
  if (u.state !== 'running') return 100;
  return u.parts ? Math.round(100 * Math.min(1, Math.max(0, u.part - 1) / u.parts)) : 3;
}
function drawUpband() {
  var host = $('upband');
  if (!host) return;
  var pk = upgPick(), p = pk.p, u = pk.u;
  if (!p && !u) { host.hidden = true; clear(host); return; }
  var state = p ? p.state : u.state;
  if (p && u && p.state !== 'running' && u.state === 'running') state = 'running';
  var failed = state === 'failed';
  var ver = (p && p.version) || u.version;
  var id = (p && p.id) || (u && (u.id || (u.version + '-' + u.started))) || '';
  if (state === 'done' && !UPG.offer && !UPG.reloading) { host.hidden = true; clear(host); return; }
  if (failed && upgHidden(id)) { host.hidden = true; clear(host); return; }
  var down = !!((p && p.downgrade) || (u && u.downgrade));
  clear(host);
  host.hidden = false;
  host.className = 'upband' + (failed ? ' bad' : (state === 'done' ? ' good' : ''));
  var head = el('div', 'upband-head');
  head.appendChild(el('b', '', failed ? (down ? 'Going back to otp ' + ver + ' failed' : 'The upgrade to otp ' + ver + ' failed')
    : (state === 'done' ? 'otp ' + ver + ' is in place' : (down ? 'otp is being taken back to ' + ver : 'otp is being upgraded to ' + ver))));
  var sub = el('span', 'upband-sub');
  var from = (p && p.from) || (u && u.from);
  var by = (p && p.by) || (u && u.by);
  var began = (p && p.at) || (u && u.started);
  if (from && from !== ver) sub.appendChild(el('span', '', 'from ' + from));
  if (by) sub.appendChild(el('span', '', 'asked by ' + by));
  if (began && state === 'running') sub.appendChild(el('span', '', upgSince(began) + ' so far'));
  head.appendChild(sub);
  if (failed) {
    var x = iconButton('close', 'Hide it');
    x.className += ' upband-x';
    x.onclick = function () { upgHide(id); host.hidden = true; };
    head.appendChild(x);
  }
  host.appendChild(head);
  var pc = upgPercent(p, u);
  host.appendChild(upBar(pc, failed ? 'bad' : (state === 'done' ? 'good' : ''), null, true));
  var how = el('div', 'upband-how');
  how.appendChild(noI18n(el('span', '', num(pc) + ' %')));
  var turn = p ? (p.steps || []).filter(function (st) { return st.state !== 'done'; })[0] : null;
  var mine = u && (!p || (turn && u.node === turn.name && (!u.id || u.id === p.id)));
  if (p && (p.steps || []).length > 1) {
    (p.steps || []).forEach(function (st) {
      var one = el('span', 'upband-node');
      one.appendChild(noI18n(el('b', '', st.name)));
      var w = UP_STATE[st.state] || UP_STATE.waiting;
      one.appendChild(el('span', 'tag ' + w[1], w[0]));
      how.appendChild(one);
    });
  }
  if (state === 'running') {
    var words = mine ? u.words : (turn && turn.part_words) || '';
    if (!words && turn) words = (UP_STATE[turn.state] || UP_STATE.waiting)[0];
    if (words) how.appendChild(el('span', '', words));
    if (mine && u.parts) how.appendChild(el('span', '', 'step ' + Math.min(u.part, u.parts) + ' of ' + u.parts));
  }
  host.appendChild(how);
  var line = el('div', 'upband-line');
  if (failed) {
    var bad = p ? (p.steps || []).filter(function (st) { return st.state === 'failed'; })[0] : null;
    var said = (bad && bad.said) || (u && u.said) || '';
    if (said) line.appendChild(el('div', '', said));
    var more = el('div', '');
    more.appendChild(document.createTextNode('What install.sh said is in Settings → Upgrades. '));
    var a = el('a', 'fgo', 'Open Upgrades');
    a.href = '#settings/upgrade';
    more.appendChild(a);
    line.appendChild(more);
  } else if (UPG.reloading) {
    line.appendChild(el('span', '', 'Loading the pages of the new version…'));
  } else if (UPG.offer) {
    line.appendChild(document.createTextNode('This page is still the one of ' + VERSION_LOADED + '. '));
    var again = el('a', 'fgo', 'Load it again');
    again.onclick = function () { location.reload(); };
    line.appendChild(again);
  } else if (UPG.away) {
    var secs = Math.max(1, Math.round((Date.now() - UPG.away) / 1000));
    line.appendChild(el('span', '', UPG.phpAway
      ? 'nginx and PHP are restarting - not answering for ' + secs + ' s, asked again every two seconds; the page comes back by itself.'
      : 'The API of these pages is restarting with the new version - not answering for ' + secs + ' s, asked again every two seconds.'));
  } else {
    line.appendChild(el('span', '', p && (p.steps || []).length > 1
      ? 'The nodes are upgraded one at a time, each in maintenance while it is - the VPN and these pages go to the other one meanwhile. This page follows it and loads the new version by itself.'
      : 'otp.service and these pages restart once - for a minute nobody can sign in to the VPN. This page follows it and loads the new version by itself.'));
  }
  host.appendChild(line);
  if (typeof explainWhatWasDrawn === 'function') explainWhatWasDrawn(host);
}

var REDRAW_OWED = false;"""

edit('admin.js', [
("""
var REDRAW_OWED = false;""", BAND),
("""  $('tabn-requests').textContent = rej ? num(rej) : '';
  $('tabn-requests').classList.toggle('hot', rej > 0);
}""",
 """  $('tabn-requests').textContent = rej ? num(rej) : '';
  $('tabn-requests').classList.toggle('hot', rej > 0);
  upgradeFromStatus(s);          /* the upgrade band (1.0.299) */
}"""),
("""    /* Busy, not down (1.0.265): the next tick asks again; what is drawn stays. */
    if (e && e.busy) return;
    var o = $('offline');""",
 """    /* Busy, not down (1.0.265): the next tick asks again; what is drawn stays. */
    if (e && e.busy) return;
    /* Restarting in an upgrade (1.0.299): the band says so - not the red "not answering". */
    if (upgradeAway(e)) return;
    var o = $('offline');"""),
])

edit('otp.css', [
("""  .offline.warnish{background:var(--warn-bg, rgba(210,153,34,.12));""",
 """  /* The upgrade band (1.0.299): under the header, while an upgrade runs - blue; failed - red. */
  .upband{background:var(--info-bg);border:1px solid rgba(88,166,255,.45);color:var(--tx);
    border-radius:12px;padding:12px 16px;margin-bottom:16px;font-size:13.5px}
  body.framed > .wrap > .upband{flex:none}
  .upband.bad{background:var(--crit-bg);border-color:rgba(248,81,73,.45)}
  .upband.good{background:var(--ok-bg);border-color:rgba(63,185,80,.45)}
  .upband-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px}
  .upband-head > b{color:var(--info);font-weight:650}
  .upband.bad .upband-head > b{color:var(--crit)}
  .upband.good .upband-head > b{color:var(--ok)}
  .upband-sub{color:var(--tx-dim);font-size:12.5px}
  .upband-sub > span + span::before{content:" · "}
  .upband-x{margin-left:auto}
  .upband .going{margin-top:8px}
  .upband-how{display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;margin-top:6px;
    color:var(--tx-dim);font-size:12.5px;font-variant-numeric:tabular-nums}
  .upband-node{display:inline-flex;align-items:center;gap:6px}
  .upband-line{margin-top:6px;font-size:13px}
  .upband-line a{margin-left:2px}
  .upband-in{background:var(--info-bg);border:1px solid rgba(88,166,255,.45);border-radius:12px;
    padding:12px 16px;margin:0 0 14px;font-size:13.5px}
  .upband-in .up-bar{height:6px;border-radius:99px;background:var(--panel2);overflow:hidden;margin:8px 0 6px}
  .upband-in .up-bar span{display:block;height:100%;background:var(--info);transition:width .4s ease}
  .upband-in .small{margin-top:4px}
  .offline.warnish{background:var(--warn-bg, rgba(210,153,34,.12));"""),
])
print('ok')
