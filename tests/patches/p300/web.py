# 1.0.300 web: Settings → High security → SELinux - what is refused, sorted by what puts it right,
# put right by id; otp's own local rules, each taken away.   python3 web.py OUTDIR
import sys
D = sys.argv[1].rstrip('/') + '/web/assets/'


def edit(f, pairs):
    s = open(D + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(D + f, 'w').write(s)


FIND = r"""
/* What SELinux refuses, sorted by what puts it right (1.0.300): each kind with what root would do;
   the fixable ones ticked, put in by their ids only - that node's root helper works out every fix
   again from its own audit log. otp's own local rules (otp_local), each taken away on its own. */
var SE_SEL = {};
var SE_KINDS = [
  ['fixed', 'Put right just now', 'Put right here - a refusal of it from after that comes back.'],
  ['boolean', 'A boolean', 'A switch of the policy allows it - setsebool switches it on.'],
  ['label', 'A label', 'The file is not labelled as the policy says it should be - restorecon puts it right.'],
  ['port', 'A port', 'A service otp works with on a port of no type of its own - semanage gives it the type.'],
  ['rule', 'A rule of otp\'s', 'Nothing of the policy allows it: exactly this, and nothing more, goes into otp\'s own local module (otp_local).'],
  ['nobutton', 'Not for a button', 'otp\'s, but what it would take is too much to allow from here - each says why; the report is for whoever looks after otp\'s module.'],
  ['other', 'Not otp\'s', 'Other programs of this machine - shown, never put right here.']];
function seFixable(f) { return ['boolean', 'label', 'port', 'rule'].indexOf(f.kind) >= 0 && !!f.fix; }
function seKindWord(k) { return {boolean: 'boolean', label: 'label', port: 'port', rule: 'rule'}[k] || k; }
function seFindings(box, n, s) {
  var fs = s.findings || [], rules = s.local_rules || [];
  if (!fs.length && !rules.length) return;
  var sel = SE_SEL[n.name] = SE_SEL[n.name] || {};
  fs.forEach(function (f) { if (seFixable(f) && !(f.id in sel)) sel[f.id] = true; });
  var wrap = el('div', 'se-find');
  if (fs.length) {
    var hd = el('div', 'se-find-h');
    hd.appendChild(el('b', '', 'What SELinux refuses'));
    hd.appendChild(el('span', 'small muted', (s.denials || {}).since ? 'since otp\'s needs were put in' : 'since the machine started'));
    wrap.appendChild(hd);
  }
  var btn = null, boxes = {};
  var picked = function () { return fs.filter(function (f) { return seFixable(f) && sel[f.id]; }); };
  var refresh = function () {
    if (!btn) return;
    var k = picked().length;
    setButtonIcon(btn, 'shield', 'Put in what is selected (' + k + ')');
    btn.disabled = !k || !!n.pending;
  };
  SE_KINDS.forEach(function (k) {
    var list = fs.filter(function (f) { return f.kind === k[0]; });
    if (!list.length) return;
    var g = el('div', 'se-kind se-k-' + k[0]);
    var gh = el('div', 'se-kind-h');
    var can = ADMIN && list.some(seFixable);
    var all = null;
    if (can) {
      all = el('input');
      all.type = 'checkbox';
      all.setAttribute('aria-label', 'Select all of them');
      all.checked = list.every(function (f) { return sel[f.id]; });
      all.onchange = function () {
        list.forEach(function (f) { sel[f.id] = all.checked; if (boxes[f.id]) boxes[f.id].checked = all.checked; });
        refresh();
      };
      gh.appendChild(all);
    } else {
      gh.appendChild(el('span', 'dot ' + ({fixed: 'ok', nobutton: 'bad', other: 'dim'}[k[0]] || 'warn')));
    }
    gh.appendChild(el('b', '', k[1]));
    gh.appendChild(noI18n(el('span', 'count', num(list.length))));
    gh.appendChild(el('span', 'small muted se-kind-says', k[2]));
    g.appendChild(gh);
    list.forEach(function (f) {
      var row = el('div', 'se-f');
      if (can && seFixable(f)) {
        var cb = el('input');
        cb.type = 'checkbox';
        cb.checked = !!sel[f.id];
        cb.setAttribute('aria-label', 'Put this right');
        cb.onchange = function () {
          sel[f.id] = cb.checked;
          if (all) all.checked = list.every(function (x) { return sel[x.id]; });
          refresh();
        };
        boxes[f.id] = cb;
        row.appendChild(cb);
      } else {
        row.appendChild(el('span', 'se-f-ico ' + k[0], {fixed: '✓', nobutton: '⊗', other: '⊘'}[k[0]] || '•'));
      }
      var main = el('div', 'se-f-main');
      var l1 = el('div', 'se-f-l1');
      l1.appendChild(noI18n(el('b', '', f.program || '?')));
      l1.appendChild(noI18n(el('span', 'mono small' + (k[0] === 'fixed' ? ' se-gone' : ''), f.source + ' → ' + f.target + ' ' + f['class'] + ' { ' + (f.perms || []).join(' ') + ' }')));
      main.appendChild(l1);
      var l2 = el('div', 'small muted se-f-l2');
      var where = f.path || (f.port ? 'port ' + f.port : '');
      if (where) l2.appendChild(noI18n(el('span', 'mono', where)));
      l2.appendChild(el('span', '', f.count === 1 ? 'once, last ' + ago(f.last) : num(f.count) + ' times, last ' + ago(f.last)));
      if (f.permissive) l2.appendChild(el('span', '', '(permissive: let through, written down)'));
      main.appendChild(l2);
      if (f.fix && k[0] !== 'fixed') {
        var cmd = el('div', 'se-f-cmd');
        cmd.appendChild(document.createTextNode('→ '));
        cmd.appendChild(noI18n(el('code', '', f.fix.cmd)));
        main.appendChild(cmd);
      }
      if (f.why) main.appendChild(noI18n(el('div', 'small se-f-why ' + k[0], f.why)));
      row.appendChild(main);
      row.appendChild(noI18n(el('span', 'se-f-n', num(f.count) + '×')));
      g.appendChild(row);
    });
    wrap.appendChild(g);
  });
  if (ADMIN && fs.some(seFixable)) {
    var bar = el('div', 'se-fixbar');
    btn = cmdButton('Put in what is selected', 'shield', 'primary');
    btn.onclick = function () { seFixAsk(n, picked()); };
    bar.appendChild(btn);
    bar.appendChild(el('span', 'small muted', 'Under enforcing too - nothing has to be switched off for it. What was put right is looked at again at once.'));
    wrap.appendChild(bar);
    refresh();
  }
  if (rules.length) {
    var rl = el('div', 'se-rules');
    var rh = el('div', 'se-kind-h');
    rh.appendChild(el('b', '', 'otp\'s local rules'));
    rh.appendChild(noI18n(el('span', 'count', num(rules.length))));
    rh.appendChild(el('span', 'small muted', s.local_module === false ? 'otp_local - NOT in the policy now' : 'otp_local, in the policy'));
    rl.appendChild(rh);
    rules.forEach(function (x) {
      var row = el('div', 'se-rule');
      var t = el('div', 'se-f-main');
      t.appendChild(noI18n(el('code', 'se-rule-t', x.rule)));
      var said = el('div', 'small muted');
      said.appendChild(noI18n(el('span', '', (x.why || '') + ' ')));
      said.appendChild(el('span', '', '- put in ' + (x.at ? new Date(x.at * 1000).toLocaleString() : '?') + ' by ' + (x.by || '?')));
      t.appendChild(said);
      row.appendChild(t);
      if (ADMIN) {
        var take = cmdButton('Take it away', 'close', 'small');
        take.disabled = !!n.pending;
        take.onclick = function () {
          confirmThen('Take the rule away on ' + n.name + '?', 'SELinux refuses it again from now on: <code>' + htmlText(x.rule) + '</code>' +
            (rules.length === 1 ? '<br>The last one: otp\'s local module goes out of the policy.' : ''), 'Take it away', function () {
            api('selinux', {node: n.name, action: 'rule_drop', rule: x.id}).then(function (r) {
              toast(r.message, 'good'); setTimeout(loadSelinux, 800);
            }).catch(oops);
          }, true);
        };
        row.appendChild(take);
      }
      rl.appendChild(row);
    });
    wrap.appendChild(rl);
  }
  box.appendChild(wrap);
}
function seFixAsk(n, pick) {
  if (!pick.length) return;
  var li = pick.map(function (f) {
    return '<li><b>' + htmlText(seKindWord(f.kind)) + '</b> <code>' + htmlText(f.fix.cmd) + '</code><br><span class="small">' +
      htmlText((f.program || '?') + ': ' + f.source + ' → ' + f.target + ' ' + f['class'] + ' { ' + (f.perms || []).join(' ') + ' }') + '</span></li>';
  }).join('');
  confirmThen('Put in what is selected on ' + n.name + '?',
    htmlText('Root does exactly this - nothing else - and looks again at once:') + '<ul class="se-confirm">' + li + '</ul>' +
    (pick.some(function (f) { return f.kind === 'rule'; }) ? htmlText('The rules go into otp\'s own local module otp_local - each can be taken away again on this card. ') : '') +
    htmlText('Every step is written in Events. It works under enforcing too.'),
    'Put it in', function () {
      api('selinux', {node: n.name, action: 'fix', ids: pick.map(function (f) { return f.id; })}).then(function (r) {
        toast(r.message, 'good');
        setTimeout(loadSelinux, 800);
      }).catch(oops);
    }, false);
}
"""

edit('admin.js', [
("""function seNode(n) {
  var s = n.state || {};""", FIND.lstrip('\n') + """function seNode(n) {
  var s = n.state || {};"""),
("""    if ((d.groups || []).length) {
      var det = el('details', 'se-avc');""",
 """    if (s.findings) seFindings(box, n, s);
    else if ((d.groups || []).length) {
      var det = el('details', 'se-avc');"""),
("""    if (d.total && known) {""",
 """    if (d.total && known && !s.findings) {"""),
("""    if (m === 'Permissive' && !s.ready) verdict.appendChild(el('span', 'small', 'Let it run a day or two as it is used - sign-ins, the pages, a failover, an upgrade - then look again.'));""",
 """    /* How many the card puts right, how many it does not (1.0.300). */
    var ct = s.counts || {};
    var canFix = (ct.boolean || 0) + (ct.label || 0) + (ct.port || 0) + (ct.rule || 0);
    if (canFix) verdict.appendChild(el('span', 'small', num(canFix) + ' thing(s) SELinux refused can be put right here - "Put in what is selected" above.'));
    if (ct.nobutton) verdict.appendChild(el('span', 'small', num(ct.nobutton) + ' thing(s) are not for a button - each says why; the report is for whoever looks after otp\\'s module.'));
    if (m === 'Permissive' && !s.ready) verdict.appendChild(el('span', 'small', 'Let it run a day or two as it is used - sign-ins, the pages, a failover, an upgrade - then look again.'));"""),
])

edit('otp.css', [
(""".se-verdict{display:flex;""",
 """/* What SELinux refuses, sorted (1.0.300) */
.se-find{display:flex;flex-direction:column;gap:10px;min-width:0}
.se-find-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;font-size:14px}
.se-kind{border:1px solid var(--line);border-left-width:3px;border-radius:10px;background:var(--panel);overflow:hidden;min-width:0}
.se-k-fixed{border-left-color:var(--ok)} .se-k-boolean,.se-k-label,.se-k-port{border-left-color:var(--info)}
.se-k-rule{border-left-color:var(--warn)} .se-k-nobutton{border-left-color:var(--crit)} .se-k-other{border-left-color:var(--line)}
.se-kind-h{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:8px 12px;border-bottom:1px solid var(--line);font-size:13px}
.se-kind-h .count{font-size:11.5px;padding:1px 7px;border-radius:999px;background:var(--panel2);color:var(--tx-dim)}
.se-kind-says{flex:1 1 220px;min-width:0}
.se-f,.se-rule{display:flex;gap:10px;align-items:flex-start;padding:8px 12px;border-bottom:1px solid var(--line);font-size:13px}
.se-f:last-child,.se-rule:last-child{border-bottom:0}
.se-f input[type=checkbox],.se-kind-h input[type=checkbox]{margin-top:3px;flex:0 0 auto}
.se-f-main{display:flex;flex-direction:column;gap:3px;min-width:0;flex:1 1 auto}
.se-f-l1{display:flex;gap:8px;flex-wrap:wrap;align-items:baseline}
.se-f-l1 .mono,.se-f-l2 .mono,.se-rule-t,.se-f-cmd code{overflow-wrap:anywhere}
.se-f-l2{display:flex;gap:8px;flex-wrap:wrap}
.se-f-cmd code{font-size:12px;padding:1px 6px;border-radius:6px;border:1px solid var(--line);background:var(--panel2);color:var(--info)}
.se-f-why.nobutton{color:var(--crit)} .se-f-why.fixed{color:var(--ok)}
.se-f-ico{flex:0 0 auto;width:15px;text-align:center;color:var(--tx-dim)} .se-f-ico.fixed{color:var(--ok)} .se-f-ico.nobutton{color:var(--crit)}
.se-f-n{flex:0 0 auto;color:var(--tx-dim);font-size:12px;font-variant-numeric:tabular-nums}
.se-gone{text-decoration:line-through;color:var(--tx-dim)}
.se-fixbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.se-rules{border:1px solid var(--line);border-radius:10px;background:var(--panel);overflow:hidden}
.se-rule-t{font-size:12px}
ul.se-confirm{margin:8px 0 10px;padding-left:18px} ul.se-confirm li{margin:4px 0;overflow-wrap:anywhere}
.se-verdict{display:flex;"""),
])
print('ok')
