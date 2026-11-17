# 1.0.298 web: an administrator's second step - an answer that comes after another way was chosen
# is not drawn into it.   python3 web.py OUTDIR
import sys
D = sys.argv[1].rstrip('/') + '/web/assets/'


def edit(f, pairs):
    s = open(D + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(D + f, 'w').write(s)


edit('core.js', [
("""    api('mfa', {action: 'enrol_start', kind: 'app'}).then(function (r) {
      d.started = null;             /* the code sent before is not the one asked for now (1.0.255) */""",
 """    api('mfa', {action: 'enrol_start', kind: 'app'}).then(function (r) {
      /* Another way chosen meanwhile (1.0.298): its view got this one's code box. */
      if (!body.contains(pic)) return;
      d.started = null;             /* the code sent before is not the one asked for now (1.0.255) */"""),
("""    }).catch(function (e) { clear(pic); pic.appendChild(el('p', 'said bad', String(e.message || e))); });
    return;""",
 """    }).catch(function (e) { if (!body.contains(pic)) return; clear(pic); pic.appendChild(el('p', 'said bad', String(e.message || e))); });
    return;"""),
("""    api('mfa', {action: 'enrol_start', kind: kind, dest: dest.value}).then(function (r) {
      mfaSentSay(sent, r.sent_to, r.send && r.send.sent > 1 ? {sent: r.send.sent} : null);""",
 """    api('mfa', {action: 'enrol_start', kind: kind, dest: dest.value}).then(function (r) {
      if (!body.contains(drow)) return;
      mfaSentSay(sent, r.sent_to, r.send && r.send.sent > 1 ? {sent: r.send.sent} : null);"""),
])
print('ok')
