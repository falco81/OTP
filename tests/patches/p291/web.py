# 1.0.291: the move wizard with this node's otp-db-agent - "make it for me" on the agent's
# server, what happens to the agent said, the HA refusal for layout B; the docs.
#   python3 web.py OUT
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/assets/admin.js', [
# the refusal, layout B's words
(
"""  if (d.cluster) {
    modal('Move to another database', function (body) {
      body.appendChild(el('p', 'note warn', 'This node is one of a cluster' + (d.ha_mode ? ' (' + d.ha_mode + ')' : '') + ': its database is the cluster’s, and moving it from here would break the cluster.'));
      body.appendChild(el('p', 'note', 'To move it: make this node one alone first (Settings → High availability → Switch it off), move it here, and build the cluster again from it.'));
    }, [{words: 'Close', close: true}], true);
    return;
  }""",
"""  if (d.cluster) {
    modal('Move to another database', function (body) {
      if (d.agent && d.agent.layout_b) {
        /* each node's database on a server of its own (1.0.291) */
        body.appendChild(el('p', 'note warn', 'This node is one of a cluster (replicated - each node’s database on a server of its own, looked after by its agent, the two replicating): its database is the cluster’s. Moving it - to another engine, another server or back onto this machine - would break the replication and leave the other node on its own.'));
        var how = el('ol', 'ha-steps');
        how.appendChild(el('li', '', 'Switch the replication off: Settings → High availability → Switch it off…, then as root otp --ha-standalone --yes on both nodes.'));
        how.appendChild(el('li', '', 'Then move the database here: Settings → The database → Move to another database.'));
        how.appendChild(el('li', '', 'Then build the cluster again: Settings → High availability → Making it two.'));
        body.appendChild(how);
        return;
      }
      body.appendChild(el('p', 'note warn', 'This node is one of a cluster' + (d.ha_mode ? ' (' + d.ha_mode + ')' : '') + ': its database is the cluster’s, and moving it from here would break the cluster.'));
      body.appendChild(el('p', 'note', 'To move it: make this node one alone first (Settings → High availability → Switch it off), move it here, and build the cluster again from it.'));
    }, [{words: 'Close', close: true}], true);
    return;
  }"""),
# step 2: made by the agent
(
"""      if (DBW.engine !== 'sqlite' && t.in_use === false && (!t.reached || !t.writable)) {
        /* Not there yet: made here, with an administrator used once. */""",
"""      if (DBW.engine !== 'sqlite' && t.in_use === false && (!t.reached || !t.writable) && t.agent_server) {
        /* The server of this node's database agent (1.0.291): made there by the agent. */
        var ag = (d.agent || {});
        var sa = el('div', 'wiz-setup dbw-agent-make');
        sa.appendChild(el('h4', '', 'Make it for me'));
        var sn = el('p', 'note');
        sn.appendChild(document.createTextNode('The server of this node’s database agent ('));
        sn.appendChild(noI18n(el('span', 'mono', (ag.db_host || ag.host || '') + ':' + (ag.db_port || ''))));
        sn.appendChild(document.createTextNode('): '));
        sn.appendChild(el('span', '', 'the agent makes the database and the account there and lets this node in - no administrator’s password typed anywhere.'));
        sa.appendChild(sn);
        var mk = cmdButton('Make the database and the account for me', 'db', 'primary');
        mk.id = 'dbw-agent-make';
        mk.onclick = function () {
          busy(mk, true);
          api('db', {action: 'setup', settings: dbwSettings(), by_agent: true}).then(function (r) {
            if (r.password) { DBW.addr.password = r.password; DBW.made = r.password; }
            DBW.agentMade = r.made || [];
            toast('made by its agent', 'good');
            run();
          }).catch(function (e) { busy(mk, false); oops(e); });
        };
        sa.appendChild(mk);
        sa.appendChild(el('p', 'small muted', 'Encryption is that server’s own: after the move, Database → TLS turns it on there (verify-full, its certificate from otp’s authority put in by its agent).'));
        say.appendChild(sa);
      } else if (DBW.engine !== 'sqlite' && t.in_use === false && (!t.reached || !t.writable)) {
        /* Not there yet: made here, with an administrator used once. */"""),
(
"""      if (DBW.made) {
        var m = el('div', 'note good');""",
"""      if (DBW.agentMade && DBW.agentMade.length) {
        var am = el('div', 'note good dbw-agent-made');
        am.appendChild(el('div', '', 'What its agent did:'));
        var aul = el('ul', 'small');
        DBW.agentMade.forEach(function (x) { aul.appendChild(noI18n(el('li', 'mono', String(x)))); });
        am.appendChild(aul);
        say.appendChild(am);
      }
      if (DBW.made) {
        var m = el('div', 'note good');"""),
# step 3: what happens to the agent
(
"""    var useLi = el('li', '', '');
    ol.appendChild(useLi);
    page.appendChild(ol);""",
"""    var useLi = el('li', '', '');
    ol.appendChild(useLi);
    /* This node's database agent (1.0.291): onto its server, or off it. */
    if (d.agent && t.agent_server && !d.agent.here) {
      ol.appendChild(el('li', 'dbw-agent-onto', 'onto the server of this node’s database agent: otp looks after it from the restart on. Then Database → TLS: verify-full, its certificate from otp’s authority put in by the agent'));
    } else if (d.agent && d.agent.here && !t.agent_server) {
      ol.appendChild(el('li', 'warn dbw-agent-off', 'the database leaves the server of this node’s database agent: once the config file is switched, the agent is let go and told this node leaves it - otp asks nothing of it any more and its server leaves this page. To have it looked after again: connect its agent again (a new join code), then move back'));
    }
    page.appendChild(ol);"""),
# step 4: the agent let go, said
(
"""        line(true, u.message || 'the daemon starts again on it');""",
"""        line(true, u.message || 'the daemon starts again on it');
        if (u.agent) line(true, u.agent);"""),
])
print('1.0.291 pages done')

edit('docs/external-database.md', [
(
"""The move wizard's *make it for me*
on the agent's server, this machine's database shown as a database server (`db_local_card`),
and the database servers' rows in the header's meter come in a later release.""",
"""Moving onto the agent's server and off it
(1.0.291, *Moving* below). This machine's database shown as a database server
(`db_local_card`) and the database servers' rows in the header's meter come in a later
release."""),
(
"""## Leaving
""",
"""## Moving

**A node has one database agent, and it is the agent of the server its database is on.**

| From → to | What to do | `db_admin` afterwards |
|---|---|---|
| this machine / SQLite → an agent's server | connect its agent (*Connect a database server…*), then *Move the database onto it…* | `agent:` that agent |
| agent A's server → agent B's server | connect agent B first - it takes A's place (A is told this node leaves it); then move | `agent:` B |
| an agent's server → this machine, SQLite, or a server no agent looks after | move | `local` - the agent let go by the move |
| a node of a cluster | refused: take the cluster apart first | unchanged |

- **Make it for me**: on the agent's server, step *Reaching it* of the wizard offers *Make the
  database and the account for me* - the agent makes the database, the account (its password
  made up when none is typed, shown once), lets this node in (`pg_hba.conf`, or `'user'@'node'`
  on MariaDB) and opens its firewall. PostgreSQL started again by its agent when it must listen
  on its network addresses first (never while this node's own database runs on it). Elsewhere
  an administrator of that server is asked, as before.
- **The encryption is the server's own**: `db_tls` / `db_tls_ca` of the server in use are not
  carried to another server (another engine, address or port) - turned on there afterwards,
  *Database → TLS*.
- **What described the old server is left behind**: the moved database does not get the rows
  `dbtls:server:NODE`, `dbagent:node:NODE`, `load:db:NODE`; the new server's are written as they
  come. The database left behind is not touched.
- **Off the agent's server**: once `config.json` is switched the agent is let go
  (`agent.json` → `agent.json.forgotten`, as `--db-agent-forget`) and told this node leaves
  it; the wizard's last step says so. Moving back means connecting it again (a new code).
- **High availability**: refused on a node of a cluster; with each node's database on a server
  of its own the refusal says so, with the way out (switch the replication off,
  `otp --ha-standalone --yes` on both nodes, move, build the cluster again). Connecting another
  agent in place of the one the cluster's database is on is refused too.
- Without an agent the wizard is as it always was.

## Leaving
"""),
])
print('1.0.291 docs done')
