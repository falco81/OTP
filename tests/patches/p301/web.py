# 1.0.301 web: SELinux on a pane of its own, the card as the kit draws it.   python3 web.py OUTDIR
import sys
W = sys.argv[1].rstrip('/') + '/web/'


def edit(f, pairs):
    s = open(W + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(W + f, 'w').write(s)


edit('admin/index.php', [
("""    <button type="button" class="fulladmin-only" data-pane="hisec" data-icon="shield" title="Every way of doing something less safely switched off - and what stands against it now.">High security</button>
""",
 """    <button type="button" class="fulladmin-only" data-pane="hisec" data-icon="shield" title="Every way of doing something less safely switched off - and what stands against it now.">High security</button>
    <button type="button" class="fulladmin-only" data-pane="selinux" data-icon="shield" title="What SELinux refuses on each node, what otp needs of it, what is put right here - and the steps to enforcing.">SELinux</button>
"""),
("""    <div id="hs-host"></div>
    <div id="se-host"></div>
    <div class="card full"><h2>Settings</h2><div id="sect-hisec"></div></div>
  </div>""",
 """    <div id="hs-host"></div>
    <div class="card full"><h2>Settings</h2><div id="sect-hisec"></div></div>
  </div>
  <div class="ctl-pane" id="pane-selinux" hidden>
    <div class="ctl-head"><h2 class="ctl-title">SELinux</h2>
      <p class="ctl-lede">What SELinux refuses on each node when it is enforcing, and what otp needs of it: its own
        module (otp_server), the labels of its files, the booleans that let the pages ask the daemon and SSH ask
        for the code, the ports of sshd and PostgreSQL. Looked at every half hour; what is put right and the
        steps - made ready and permissive, enforcing, permissive again - are done by each node's root only when
        asked here or with <span class="mono">sudo otp --selinux</span>.</p></div>
    <div id="se-host"></div>
  </div>"""),
])

edit('assets/admin.js', [
("""  if (name === 'hisec') loadHisec();
""",
 """  if (name === 'hisec') loadHisec();
  if (name === 'selinux') loadSelinux(); else sePoll(false);      /* a pane of its own (1.0.301) */
"""),
("""  api('hisec').then(function (d) { drawHisec(d); }).catch(oops);
  loadSelinux();
}""",
 """  api('hisec').then(function (d) { drawHisec(d); }).catch(oops);
}"""),
("""    if (TAB !== 'settings' || PANE !== 'hisec') { sePoll(false); return; }""",
 """    if (TAB !== 'settings' || PANE !== 'selinux') { sePoll(false); return; }"""),
("""  var c = el('div', 'card full se-card');
  var h = el('h2', '', 'SELinux');
  var tl = el('span', 'right');""",
 """  var c = el('div', 'card full se-card');
  var h = el('h2', '', 'SELinux');
  /* A light for each node (1.0.301): its mode and whether something stands against it; turning
     while a node has a step to do. */
  var chip = el('span', 'se-chip');
  (SE.d.nodes || []).forEach(function (n) {
    var s = n.state || {}, m = s.mode || '';
    var k = n.error ? 'bad' : !m ? 'dim' : (m === 'Enforcing' ? ((s.problems || []).length ? 'warn' : 'ok')
      : m === 'Permissive' ? 'warn' : 'dim');
    var dt = el('span', 'dot ' + k);
    dt.title = n.name + ': ' + seModeWords(m);
    chip.appendChild(dt);
  });
  var turning = (SE.d.nodes || []).some(function (n) { return !!n.pending; });
  var rf = el('span', 'se-chip-r' + (turning ? ' on' : ''), '↻');
  rf.title = turning ? 'a node is doing what was asked' : 'looked at every half hour';
  chip.appendChild(rf);
  h.appendChild(chip);
  var tl = el('span', 'right');"""),
("""  c.appendChild(el('p', 'note', 'What SELinux refuses to the web server, keepalived, sshd and the rest when it is enforcing - and what otp needs of it on each node. Nothing changes here unless asked: disabled stays disabled. In a cluster, one node at a time - the other answers meanwhile. On the server: otp --selinux-check.'));""",
 """  c.appendChild(el('p', 'note', 'What SELinux refuses to the web server, keepalived, sshd, PostgreSQL and the rest when it is enforcing - and what otp needs of it on each node. Nothing changes here unless asked: disabled stays disabled. In a cluster, one node at a time - the other answers meanwhile. On the server: sudo otp --selinux-check.'));
  if ((SE.d.nodes || []).length > 1)
    c.appendChild(el('p', 'note small', 'SELinux is each machine\\'s own: every node has its own mode, module, refusals and fixes. What is asked on a node\\'s card is asked of that node, and done by its root only - never on the other node.'));"""),
("""  var fs = s.findings || [], rules = s.local_rules || [];
  if (!fs.length && !rules.length) return;
  var sel = SE_SEL[n.name] = SE_SEL[n.name] || {};
  fs.forEach(function (f) { if (seFixable(f) && !(f.id in sel)) sel[f.id] = true; });
  var wrap = el('div', 'se-find');
  if (fs.length) {
    var hd = el('div', 'se-find-h');
    hd.appendChild(el('b', '', 'What SELinux refuses'));
    hd.appendChild(el('span', 'small muted', (s.denials || {}).since ? 'since otp\\'s needs were put in' : 'since the machine started'));
    wrap.appendChild(hd);
  }""",
 """  var fs = s.findings || [], rules = s.local_rules || [];
  var sel = SE_SEL[n.name] = SE_SEL[n.name] || {};
  fs.forEach(function (f) { if (seFixable(f) && !(f.id in sel)) sel[f.id] = true; });
  var wrap = el('div', 'se-find');
  var since = (s.denials || {}).since;
  var hd = el('div', 'se-find-h');
  hd.appendChild(el('b', '', 'What SELinux refuses'));
  hd.appendChild(el('span', 'small muted', since ? 'since otp\\'s needs were put in' : 'since the machine started'));
  wrap.appendChild(hd);
  /* Nothing refused (1.0.301): said so, plainly, as the kit draws it. */
  if (!fs.length) {
    var none = el('div', 'se-none');
    none.appendChild(el('span', 'se-none-ico', '✓'));
    var nt = el('div', '');
    nt.appendChild(el('b', '', 'SELinux refused nothing on this node'));
    nt.appendChild(el('div', 'small', since ? 'Nothing since otp\\'s needs were put in.' : 'Nothing since the machine started.'));
    none.appendChild(nt);
    wrap.appendChild(none);
  }"""),
])

edit('assets/otp.css', [
("""/* What SELinux refuses, sorted (1.0.300) */""",
 """/* The SELinux pane (1.0.301): a light a node beside the title; nothing refused, said in green */
.se-card > h2{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.se-card > h2 .right{margin-left:auto}
.se-chip{display:inline-flex;align-items:center;gap:5px;padding:3px 8px;border:1px solid var(--line);border-radius:999px;background:var(--panel2);font-weight:400}
.se-chip .dot{width:8px;height:8px}
.se-chip-r{font-size:12px;color:var(--tx-dim);line-height:1}
.se-chip-r.on{color:var(--info);display:inline-block;animation:turn 1.2s linear infinite}
.se-none{display:flex;align-items:center;gap:12px;padding:12px 14px;border:1px solid rgba(63,185,80,.5);border-radius:10px;background:var(--ok-bg);font-size:13px}
.se-none-ico{flex:0 0 auto;width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:rgba(63,185,80,.18);color:var(--ok);font-weight:700}
/* What SELinux refuses, sorted (1.0.300) */"""),
])
print('ok')
