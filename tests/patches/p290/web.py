# 1.0.290: high availability with each node's database on a server of its own (layout B) - the
# out folder: the steps on High availability -> Making it two, the docs.   python3 web.py OUT
import os, sys
O = sys.argv[1].rstrip('/') + '/'
HERE = os.path.dirname(os.path.abspath(__file__))


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/assets/admin.js', [
(
"""/* Making it two with each node's database on a server of its own (layout B) comes with a later
   release: nothing drawn for it yet. */
function dbaHaMake(d) {
  var box = $('ha-dbs-make');
  if (box) box.remove();
}
""",
"""/* Making it two with each node's database on a server of its own (layout B, 1.0.290): the
   commands, filled in from what is typed. Only for a node whose database is PostgreSQL on its
   agent's server, not yet one of a cluster. */
function dbaHaMake(d) {
  var at = $('ha-make-body');
  var box = $('ha-dbs-make');
  var on = !!(d && String(d.db_admin || '').indexOf('agent:') === 0 && d.engine === 'postgres' &&
              d.db_here && !d.mode);
  if (!on || !at) { if (box) box.remove(); return; }
  if (box) return;                                    /* typed into: kept as it is */
  box = el('div', 'dbs-make');
  box.id = 'ha-dbs-make';
  var ic = el('span', 'ha-lead-ico'); ic.innerHTML = iconMarkup('db', 22);
  var lead = el('div', 'ha-lead');
  lead.appendChild(noI18n(ic));
  var lw = el('div', '');
  lw.appendChild(el('b', '', 'Each node’s database on a server of its own'));
  lw.appendChild(el('p', 'note', 'This node’s database is looked after by otp-db-agent. Replicated, each node has its own database server: this node on its own, the second node on another - the two servers replicate both ways, set up and encrypted by otp through their agents. --ha-peer is then the other database server, --ha-peer-node the other otp node.'));
  lead.appendChild(lw);
  box.appendChild(lead);
  var g = el('div', 'formgrid');
  var db2 = textBox('', '192.0.2.22', 'mono'); db2.id = 'ha-dbs-peer';
  var n2 = textBox('', '192.0.2.12', 'mono'); n2.id = 'ha-dbs-node';
  var me = textBox(d.node || 'otp1', 'otp1', 'mono'); me.id = 'ha-dbs-name';
  var nm2 = textBox('otp2', 'otp2', 'mono'); nm2.id = 'ha-dbs-name2';
  g.appendChild(formField('The other database server', db2, 'Its address: where the second node’s database runs, with its own agent.'));
  g.appendChild(formField('The other otp node', n2, 'The second otp server’s own address - let into this node’s database server too.'));
  g.appendChild(formField('This node’s name', me));
  g.appendChild(formField('The second node’s name', nm2));
  box.appendChild(g);
  var said = el('div', 'dbs-make-cmds');
  box.appendChild(said);
  function draw() {
    clear(said);
    var p = db2.value.trim() || 'DB2', q = n2.value.trim() || 'OTP2', a = me.value.trim() || 'otp1', b = nm2.value.trim() || 'otp2';
    [[db2, p], [n2, q]].forEach(function (x) { x[0].classList.toggle('bad', !!x[0].value.trim() && !haIp(x[0].value.trim())); });
    var ol = el('ol', 'ha-steps dbs-steps');
    var l1 = el('li', '');
    l1.appendChild(el('b', '', 'On this node, as root'));
    l1.appendChild(dbaCmd('otp --ha-setup --ha-peer ' + p + ' --ha-peer-node ' + q + ' --node-name ' + a));
    l1.appendChild(el('div', 'small muted', 'Its agent prepares this node’s database server (wal_level, listening, pg_hba.conf for the other server and the other node), restarts it, publishes the tables and opens its firewall; the bundle for the second node is written to /root.'));
    ol.appendChild(l1);
    var l2 = el('li', '');
    l2.appendChild(el('b', '', 'On the other database server, as root'));
    l2.appendChild(dbaCmd('./install.sh --db-server postgres --otp-node ' + q + ' --otp-node ' + (d.address || 'OTP1')));
    ol.appendChild(l2);
    var l3 = el('li', '');
    l3.appendChild(el('b', '', 'On the second node, as root: its agent, then the join'));
    l3.appendChild(dbaCmd('otp --db-agent-join -\\notp --ha-join /root/otp-join-' + a + '.json --node-name ' + b));
    l3.appendChild(el('div', 'small muted', 'otp --db-agent-join - reads the join code from its standard input: paste it there, it is never put on a command line.'));
    l3.appendChild(el('div', 'small muted', 'Every row is copied from this node’s server to the other one, both directions of replication set up.'));
    ol.appendChild(l3);
    var l4 = el('li', '');
    l4.appendChild(el('b', '', 'Then on either node: the link between the two servers encrypted'));
    l4.appendChild(dbaCmd('otp --ha-tls-repair'));
    l4.appendChild(el('div', 'small muted', 'Each node issues its database server’s certificate and its agent puts it in: verify-full, hostssl for the other server and the other node. High availability → Repair does the same.'));
    ol.appendChild(l4);
    said.appendChild(ol);
  }
  [db2, n2, me, nm2].forEach(function (x) { x.addEventListener('input', draw); });
  draw();
  at.insertBefore(box, at.firstChild);
}
"""),
])
with open(O + 'web/assets/otp.css', 'a') as f:
    f.write("""
/* Making it two with each node's database on a server of its own (1.0.290) */
.dbs-make .ha-lead{display:flex;gap:12px;align-items:flex-start;margin-bottom:10px}
.dbs-make .ha-lead-ico{color:var(--violet);flex:none;margin-top:2px}
.dbs-make .ha-lead p{margin:4px 0 0}
.dbs-make .formgrid{margin-bottom:8px}
""")
print('1.0.290 pages done')

# ---- the docs ------------------------------------------------------------------------------------
edit('docs/external-database.md', [
(
"""This release covers **layout A**: one otp node, or two that share one database, and its
database server. High availability with each node's database on a server of its own (layout B,
`--ha-peer-node`) comes in a later release. So do the move wizard's *make it for me* on the
agent's server, this machine's database shown as a database server (`db_local_card`), and the
database servers' rows in the header's meter.""",
"""**Layout A**: one otp node, or two that share one database, and its database server.
**Layout B** (1.0.290): high availability with each node's database on a server of its own,
the two servers replicating (see *High availability* below). The move wizard's *make it for me*
on the agent's server, this machine's database shown as a database server (`db_local_card`),
and the database servers' rows in the header's meter come in a later release."""),
(
"""## Leaving
""",
"""## High availability (layout B)

PostgreSQL 16 or later only. otp1 uses db1, otp2 uses db2, and db1 and db2 replicate both ways
(logical replication, as two nodes with a PostgreSQL each). The VIP address, keepalived, the
leader, the split handling and the clocks stay the **otp nodes'** own. The link between the
two database servers is encrypted with certificates from otp's authority, put in by their agents.

```
                    VRRP VIP 192.0.2.10 (keepalived - the nodes' own)
             ┌────────────────────────────────────────────────────┐
        ┌────┴────┐  heartbeat, leader, split handling, clocks ┌───┴─────┐
        │ otp1    │◄──────────────────────────────────────────►│ otp2    │
        │ .11     │       (--ha-peer-node: the other otp node) │ .12     │
        └──┬───┬──┘                                            └──┬───┬──┘
  agent 9443│   │5432 TLS verify-full              agent 9443 │   │5432 TLS verify-full
           ▼   ▼                                                ▼   ▼
        ┌─────────┐   logical replication, both ways      ┌─────────┐
        │ db1 .21 │◄─────────────────────────────────────►│ db2 .22 │
        │ PG 16 + │   hostssl, verify-full                │ PG 16 + │
        │ agent   │   (--ha-peer: the other DATABASE)     │ agent   │
        └─────────┘                                       └─────────┘
```

1. On each database server: `./install.sh --db-server postgres --otp-node OTP1 --otp-node OTP2`.
2. otp1: `otp --db-agent-join -` (db1's code), then its database moved onto db1.
3. otp1: `otp --ha-setup --ha-peer DB2 --ha-peer-node OTP2 --node-name otp1`. **`--ha-peer` is
   the other database server, `--ha-peer-node` the other otp node.** db1's agent prepares db1
   (wal_level, listening, pg_hba.conf for db2, otp2 and otp1), restarts it, publishes the tables
   and opens its firewall. `ha_address` is db1; `agent.json` keeps `peer_node` (otp2) and
   `node_address` (otp1's own address toward otp2). The bundle carries `peer.node`.
4. otp2: `otp --db-agent-join -` (db2's code), then `otp --ha-join BUNDLE --node-name otp2`: db2
   is prepared by its agent, every row is copied from db1, both subscriptions are made,
   config.json gets `db_host` = db2, and db2's agent is told the cluster's authorities.
5. On either node: `otp --ha-tls-repair` (or *High availability → Repair*): each node issues its
   server's certificate, its agent puts it in - verify-full, hostssl.

*High availability → Making it two* shows these commands filled in, on a node whose database is
on its agent's server.

What is the nodes' own takes the other **otp node** (`peer_node`), never the other database
server: the clocks' peers, the addresses the firewall always lets in, keepalived's other node
and its own address (`node_address`), the split's look at the other machine. The other database
server's clock is said as *the database server of otp2* and never corrects the heartbeats.

Rebuild (`otp --ha-resync`), pause and resume, renewals and the authority's roll work as with a
PostgreSQL on each node; the root parts go through the agents. A node's own address changed on
*Settings → Network*: its agent lets the new address into its server before anything changes,
and the other node's agent does once the replicated row comes over.

Without `--ha-peer-node` and without an agent, `--ha-setup` is what it always was: `--ha-peer`
is the other node. `--ha-peer-node` on a node whose database is not on its agent's server is
refused. MariaDB does not replicate; the shared layout (`--ha-shared`) is unchanged - that
server stays its administrator's.

## Leaving
"""),
(
"""- `install.sh --uninstall` on a node keeps the join""",
"""- In layout B the agent is not forgotten while the replication runs through it: `--db-agent-forget`,
  `--db-agent-leave` and the card refuse it - take the cluster apart first
  (`otp --ha-standalone`).
- `install.sh --uninstall` on a node keeps the join"""),
])
print('1.0.290 docs done')
