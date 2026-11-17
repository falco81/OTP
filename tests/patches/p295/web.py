# 1.0.295 web: the database card of a node with no agent of its own (in a cluster whose other node
# has one); the HA pane's database servers without replication.   python3 web.py OUTDIR
import sys
D = sys.argv[1].rstrip('/') + '/web/assets/'


def edit(f, pairs):
    s = open(D + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(D + f, 'w').write(s)


edit('admin.js', [
("""  var full = typeof ME === 'object' && ME && ME.role === 'fulladmin';
  if (!dbaOn(d)) {
    /* A server elsewhere, its administrator's: otp only connects to it. */""",
 """  var full = typeof ME === 'object' && ME && ME.role === 'fulladmin';
  /* This node's own agent (1.0.295): the other node's server's row alone drew the card of an
     agent of this node's - Move, Restart, Renew and Forget for an agent it does not have. */
  if (String(d.db_admin || '').indexOf('agent:') !== 0) {
    /* A server elsewhere, its administrator's: otp only connects to it. */"""),
("""    host.appendChild(dbaHero('plain', 'db', t0,
      'otp only connects to it: its certificate, its settings and their restart are its administrator’s. With otp-db-agent on that server otp looks after it as it would one on this machine - and the meter in the header shows it.'));
    var row = el('div', 'btnrow');""",
 """    host.appendChild(dbaHero('plain', 'db', t0,
      'otp only connects to it: its certificate, its settings and their restart are its administrator’s. With otp-db-agent on that server otp looks after it as it would one on this machine - and the meter in the header shows it.'));
    if ((d.servers || []).length) {
      var og = el('div', 'dbs-grid');
      d.servers.forEach(function (s) { og.appendChild(dbaTile(s, d)); });
      host.appendChild(og);
    }
    var row = el('div', 'btnrow');"""),
("""      rep.appendChild(arrow);
      var ok = false, words = 'not set up', behind;
      if (s.me) {""",
 """      /* No replication (1.0.295): standalone, or both nodes on one server - not a red "not set
         up", there is none to set up. */
      var norep = d.mode !== 'replicated';
      if (!norep) rep.appendChild(arrow);
      var ok = false, words = 'not set up', behind;
      if (norep) {
        rep.appendChild(el('span', 'muted', '– no replication'));
        tr.appendChild(rep);
      } else if (s.me) {"""),
("""      rep.appendChild(document.createTextNode(' '));
      rep.appendChild(el('span', 'tag ' + (ok ? 'ok' : (words === 'paused' || words === 'waiting' ? 'warn' : 'crit')), words));
      tr.appendChild(rep);""",
 """      if (!norep) {
        rep.appendChild(document.createTextNode(' '));
        rep.appendChild(el('span', 'tag ' + (ok ? 'ok' : (words === 'paused' || words === 'waiting' ? 'warn' : 'crit')), words));
        tr.appendChild(rep);
      }"""),
])
print('ok')
