# 1.0.280 page and root-helper side: python3 web.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('deploy/otp_web.py', [(
"""        if h not in hosts:
            hosts.append(h)
    return hosts or ['127.0.0.1']


def lbport_listening(""",
"""        if h not in hosts and _own_address(h):
            hosts.append(h)
    return hosts or ['127.0.0.1']


def _own_address(host):
    \"\"\"Whether an address is this node's own (1.0.280): the VIP's listen line, answered by the other
    node while it holds the VIP, is no answer of this node's nginx.\"\"\"
    import socket
    s = None
    try:
        s = socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, 0))
        return True
    except (OSError, ValueError):
        return False
    finally:
        if s is not None:
            s.close()


def lbport_listening("""), (
"""            elif not NO_SERVICES and not lbport_listening(int(cl['port']), 0):
                cert_look = int(cl['port'])""",
"""            elif not NO_SERVICES and not lbport_listening(int(cl['port']), 0, hosts=cert_listen_hosts(int(cl['port']))):
                cert_look = int(cl['port'])"""), (
"""                cert_gone = int(m.group(1)) if m else 0
            except (OSError, ValueError):
                cert_gone = 0""",
"""                cert_gone = int(m.group(1)) if m else 0
                # Where it listened, read before the file goes (1.0.280): looked at 127.0.0.1 alone, a
                # server on one address was never seen still asking.
                cert_gone_hosts = cert_listen_hosts(cert_gone) if cert_gone else None
            except (OSError, ValueError):
                cert_gone = 0"""), (
"""            if cert_gone and lbport_listening(cert_gone, 0):""",
"""            if cert_gone and lbport_listening(cert_gone, 0, hosts=cert_gone_hosts):"""), (
"""                while time.time() < end and lbport_listening(cert_gone, 0):""",
"""                while time.time() < end and lbport_listening(cert_gone, 0, hosts=cert_gone_hosts):""")])
edit('deploy/otp_web.py', [(
"""        cert_look = cert_gone = 0""",
"""        cert_look = cert_gone = 0
        cert_gone_hosts = None""")])
edit('web/assets/admin.js', [(
"""function drawSettings() {
  DRAWN_NODE = SETTINGS.node || '';""",
"""function drawSettings() {
  /* The height held for the pane before let go (1.0.280): a short pane after a long one kept a gap. */
  paneLetGo();
  DRAWN_NODE = SETTINGS.node || '';""")])
print('web 1.0.280 patched')

# SSH keys: root's only shown; a user's key made for every node or one, as root's was (1.0.280)
edit('web/assets/admin.js', [(
"""    if (me === 'root') host.appendChild(skKeptCard(d));
    else host.appendChild(skUserCard(d, me));""",
"""    /* Root's keys are only shown (1.0.280): put on and taken away by root on the node itself. */
    if (me === 'root') host.appendChild(skRootNote());
    else host.appendChild(skUserCard(d, me));"""), (
"""    var tools = el('span', 'right');
    var add = cmdButton('Add a key', 'upload', 'small');
    explain(add, 'A key you have already - its public line or .pub file, or the private key, of which only the public half is used - put onto the nodes you choose.');
    var again = iconButton('refresh', 'Read the keys again on every node');
    tools.appendChild(add); tools.appendChild(again);
    h.appendChild(tools);
    card.appendChild(h);
    add.onclick = skAdd;""",
"""    var tools = el('span', 'right');
    if (me !== 'root') {
      var add = cmdButton('Add a key', 'upload', 'small');
      explain(add, 'A key you have already - its public line or .pub file, or the private key, of which only the public half is used - put onto the nodes you choose.');
      add.onclick = skAdd;
      tools.appendChild(add);
    }
    var again = iconButton('refresh', 'Read the keys again on every node');
    tools.appendChild(again);
    h.appendChild(tools);
    card.appendChild(h);"""), (
"""        act.appendChild(ex);
        var rm = iconButton('trash', 'Take this key away');
        rm.onclick = function () { skDrop(row); };
        act.appendChild(rm);""",
"""        act.appendChild(ex);
        if (me !== 'root') {
          var rm = iconButton('trash', 'Take this key away');
          rm.onclick = function () { skDrop(row); };
          act.appendChild(rm);
        }"""), (
"""/* A key for a normal user (1.0.240): made here, its private half shown once - remembered nowhere. */
function skUserCard(d, user) {
  var card = el('div', 'card full');
  var h = el('h2', '', 'A key for');
  h.appendChild(noI18n(el('span', 'mono', ' ' + user)));
  card.appendChild(h);
  var where = ((d.nodes || []).filter(function (n) { return (n.users || []).some(function (u) { return u.name === user; }); })).map(function (n) { return n.name; });
  var P = rbPanel('Its <b>public</b> half goes into <code>~' + htmlText(user) + '/.ssh/authorized_keys</code> of ' + htmlText(where.join(', ') || 'the nodes') + ' - written as ' + htmlText(user) + ', so that the folder and the file are theirs. The <b>private</b> half is never kept here: it is shown to you once, to hand over.');
  var mk = cmdButton('Make a key', 'key', '');
  mk.disabled = !d.keygen || !where.length;
  mk.onclick = function () {
    var kind = 'ed25519';
    modal('Make a key for ' + user, function (body) {
      body.appendChild(el('p', 'note', 'A fresh pair is made here. Its private half is shown to you once, to download or copy, and kept nowhere; its public half goes onto ' + where.join(', ') + '.'));""",
"""/* Root's keys are only shown (1.0.280): no key is made, put on or taken away as root from the pages. */
function skRootNote() {
  var card = el('div', 'card full');
  card.appendChild(el('h2', '', 'Keys for root'));
  var p = el('p', 'note');
  p.innerHTML = 'Root\\'s keys are only shown here - none is made, put on or taken away from these pages. That is done by root on the node itself, in <code>/root/.ssh/authorized_keys</code>. A key for another user who may sign in on the nodes is made or added here: choose them under <b>Whose keys</b>.';
  card.appendChild(p);
  return card;
}
/* A key for a normal user (1.0.240): made here, its private half shown once - remembered nowhere. In a
   cluster the same key on every node where the user is, or a node's own (1.0.280, as root's was). */
function skUserCard(d, user) {
  var card = el('div', 'card full');
  var h = el('h2', '', 'A key for');
  h.appendChild(noI18n(el('span', 'mono', ' ' + user)));
  card.appendChild(h);
  var there = ((d.nodes || []).filter(function (n) { return (n.users || []).some(function (u) { return u.name === user; }); })).map(function (n) { return n.name; });
  SK.uscope = SK.uscope || {};
  var scope = SK.uscope[user] || 'all';
  if (scope !== 'all' && there.indexOf(scope) < 0) scope = SK.uscope[user] = 'all';
  if (there.length > 1) {
    var segb = el('div', 'seg');
    ['all'].concat(there).forEach(function (sc) {
      var b = el('button', sc === scope ? 'on' : '', sc === 'all' ? 'The same key on every node' : 'Only on');
      if (sc !== 'all') b.appendChild(noI18n(el('b', '', ' ' + sc)));
      b.type = 'button';
      b.onclick = function () { SK.uscope[user] = sc; drawSshKeys(); };
      segb.appendChild(b);
    });
    var ff = formField('The key for', segb);
    ff.style.marginBottom = '12px';
    card.appendChild(ff);
  }
  var where = scope === 'all' ? there : [scope];
  var on = scope === 'all' ? (there.length > 1 ? htmlText(there.join(', ')) + ' - the same key' : htmlText(there.join(', ') || 'the nodes')) : '<b>' + htmlText(scope) + '</b> only';
  var P = rbPanel('Its <b>public</b> half goes into <code>~' + htmlText(user) + '/.ssh/authorized_keys</code> of ' + on + ' - written as ' + htmlText(user) + ', so that the folder and the file are theirs. The <b>private</b> half is never kept here: it is shown to you once, to hand over. The key is then in the list below - exported or taken away there; a key of their own is added there too.');
  if (!d.keygen) {
    var miss = el('p', 'note');
    miss.style.color = 'var(--warn)';
    miss.textContent = 'ssh-keygen is not on this machine, so a key cannot be made or read here: dnf install openssh-clients.';
    P.box.insertBefore(miss, P.row);
  }
  var mk = cmdButton('Make a key', 'key', '');
  explain(mk, 'Make a fresh pair here - Ed25519, or RSA 4096 where something old needs RSA. Its private half is shown to you once; its public half goes into ' + user + '\\'s authorized_keys of ' + where.join(', ') + '.');
  mk.disabled = !d.keygen || !where.length;
  mk.onclick = function () {
    var kind = 'ed25519';
    modal('Make a key for ' + user, function (body) {
      body.appendChild(el('p', 'note', 'A fresh pair is made here. Its private half is shown to you once, to download or copy, and kept nowhere; its public half goes onto ' + where.join(', ') + '. A key there before stays until it is taken away in the list below.'));""")])
print('ssh keys page patched')
edit('web/admin/index.php', [(
"""      <p class="ctl-lede">The keys that may sign in to each node over SSH - as root (the lines of
        /root/.ssh/authorized_keys) or as any user who may sign in there (their own
        ~/.ssh/authorized_keys, written as they are), read from every node. A key made here is shown once,
        to be kept by you, and kept nowhere on the server; one of your own is put on by its public half - on
        every node or on one. Every change is written into Events.</p></div>""",
"""      <p class="ctl-lede">The keys that may sign in to each node over SSH - as root (the lines of
        /root/.ssh/authorized_keys, only shown here: put on and taken away by root on the node itself) or as
        any user who may sign in there (their own ~/.ssh/authorized_keys, written as they are), read from
        every node. A key made here for a user is shown once, to be kept by you, and kept nowhere on the
        server; one of your own is put on by its public half - on every node or on one. Every change is
        written into Events.</p></div>""")])
print('lede patched')
