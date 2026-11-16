# 1.0.289: the database on a server of its own (otp-db-agent) - the out folder: the agent's files,
# install.sh's --db-server / --db-agent, the pages.   python3 web.py OUT
import os, shutil, sys
O = sys.argv[1].rstrip('/') + '/'
HERE = os.path.dirname(os.path.abspath(__file__))


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


for f, mode in (('otp_db_agent.py', 0o755), ('otp_pg_ops.py', 0o644), ('otp-db-agent.service', 0o644),
                ('db-server.sh', 0o644)):
    shutil.copy(os.path.join(HERE, 'deploy', f), O + 'deploy/' + f)
    os.chmod(O + 'deploy/' + f, mode)

# ---- install.sh ------------------------------------------------------------------------------
edit('install.sh', [
(
"""FACT_NGINX_ADD=""
""",
"""FACT_NGINX_ADD=""
# A database server of its own for otp, and its agent (1.0.289, deploy/db-server.sh): nothing of
# it runs without --db-server or --db-agent.
DB_SERVER=""
DB_AGENT=""
DB_AGENT_NEW_CODE=""
DB_AGENT_PORT="9443"
DB_AGENT_PORT_GIVEN=""
OTP_NODES=""
DBS_NAME="otp"
DBS_USER="otp"
DBS_PASSWORD=""
DBS_PASSWORD_FILE=""
DBS_PASSWORD_ARGV=""
DBS_ENGINE=""
DBS_PORT=""
"""),
(
"""  --dry-run                 print what would happen and change nothing
  --yes                     never ask; take the defaults
  --help                    this
EOF""",
"""  --dry-run                 print what would happen and change nothing
  --yes                     never ask; take the defaults
  --help                    this

  A database server of its own for otp (docs/external-database.md) - run on THAT
  server, never on the otp node; nothing of otp itself is installed:
  --db-server ENGINE        postgres: PostgreSQL 16 (EL: postgresql:16 module or PGDG;
                            Debian/Ubuntu: PGDG), initialised, started, listening, wal_level
                            logical, the database and the account for otp;
                            mariadb: the distribution's MariaDB, secured, the same
                            ...and otp-db-agent, the firewall for the otp nodes, a join code
  --db-agent                otp-db-agent alone, for a database server installed already
                            (run again: upgraded, its nodes stay joined)
  --db-agent-port N         the agent's port (9443)
  --new-code                a join code printed even though the agent was installed already
                            (only a new install prints one by itself - an upgrade does not)
  --otp-node ADDRESS        an otp node using this server (again for each one): let into
                            pg_hba.conf / the accounts and the firewall
  --db-name NAME --db-user NAME   otp's database and account (otp, otp)
  --db-password-file FILE   the account's password, the first line of FILE (made up and shown
                            once without it; --db-password PASS works too, but every account
                            on the machine sees a command line)
  --db-server/--db-agent --uninstall   the agent taken away; the database stays
EOF"""),
(
"""        --dry-run)         DRY_RUN="yes"; shift;;
""",
"""        --dry-run)         DRY_RUN="yes"; shift;;
        --db-server)       DB_SERVER="${2:-}"; shift 2;;
        --db-agent)        DB_AGENT="yes"; shift;;
        --new-code)        DB_AGENT_NEW_CODE="yes"; shift;;
        --db-agent-port)   DB_AGENT_PORT="${2:-}"; DB_AGENT_PORT_GIVEN="yes"; shift 2;;
        --otp-node)        OTP_NODES="${OTP_NODES:+$OTP_NODES }${2:-}"; shift 2;;
        --db-name)         DBS_NAME="${2:-}"; shift 2;;
        --db-user)         DBS_USER="${2:-}"; shift 2;;
        --db-password)     DBS_PASSWORD="${2:-}"; DBS_PASSWORD_ARGV="yes"; shift 2;;
        --db-password-file) DBS_PASSWORD_FILE="${2:-}"; shift 2;;
        --db-engine)       DBS_ENGINE="${2:-}"; shift 2;;
"""),
(
"""[[ $EUID -eq 0 ]] || fail "run this as root: sudo ./install.sh"
""",
"""# The database server's own options (1.0.289): the password from a file, never asked on a
# command line; --new-code only there.
if [[ -n "$DBS_PASSWORD_FILE" ]]; then
    [[ -f "$DBS_PASSWORD_FILE" && -r "$DBS_PASSWORD_FILE" ]] || fail "--db-password-file: $DBS_PASSWORD_FILE cannot be read"
    IFS= read -r DBS_PASSWORD < "$DBS_PASSWORD_FILE" || true
    [[ -n "$DBS_PASSWORD" ]] || fail "--db-password-file: $DBS_PASSWORD_FILE has no password on its first line"
elif [[ -n "${DBS_PASSWORD_ARGV:-}" ]]; then
    warn "--db-password is on the command line, where every account on this machine sees it: --db-password-file FILE is better"
fi
if [[ -n "$DB_AGENT_NEW_CODE" && -z "$DB_SERVER" && -z "$DB_AGENT" ]]; then
    fail "--new-code is for the database server: install.sh --db-agent --new-code there (or python3 -I /usr/local/lib/otp-db-agent/otp_db_agent.py --new-code)"
fi
if [[ -z "$DB_SERVER" && -z "$DB_AGENT" ]] && [[ -n "$OTP_NODES$DBS_PASSWORD_FILE$DBS_PASSWORD_ARGV$DBS_ENGINE$DB_AGENT_PORT_GIVEN" ]]; then
    fail "--otp-node, --db-password(-file), --db-engine and --db-agent-port are for the database server: with --db-server or --db-agent"
fi

[[ $EUID -eq 0 ]] || fail "run this as root: sudo ./install.sh"
"""),
(
"""    *) PKG="";;
esac

# ---------------------------------------------------------------------------
# Taking it away
""",
"""    *) PKG="";;
esac

if [[ -n "$DB_SERVER" || -n "$DB_AGENT" ]]; then
    # A database server of its own and its agent (1.0.289): this, and nothing else of otp.
    # shellcheck source=deploy/db-server.sh
    . "$SOURCE_DIR/deploy/db-server.sh"
    db_server_main
    exit 0
fi

# ---------------------------------------------------------------------------
# Taking it away
"""),
(
"""    ASSUME_YES="" confirm "Go ahead?" n || { say "Nothing was changed."; exit 0; }
""",
"""    ASSUME_YES="" confirm "Go ahead?" n || { say "Nothing was changed."; exit 0; }
    # A database agent this node joined stays joined (1.0.289), as $STATE_DIR is kept: otp
    # installed again goes on with it. A node going away for good leaves it first with
    # otp --db-agent-leave --yes, or is taken away on the database server:
    # otp_db_agent.py --forget NODE.
    if [[ -f "$STATE_DIR/db-agent/agent.json" ]]; then
        say "This node stays joined to its database agent (kept in $STATE_DIR/db-agent). Going away"
        say "for good: otp --db-agent-leave --yes before this, or otp_db_agent.py --forget NODE"
        say "on the database server."
    fi
"""),
])
print('1.0.289 out folder done')

# ---- the pages ---------------------------------------------------------------------------------
JS = open(os.path.join(HERE, 'dba.js')).read()
CSS = open(os.path.join(HERE, 'dbs.css')).read()
edit('web/assets/admin.js', [
(
"""    drawTune(d);
    drawErasable(d.erasable || {});""",
"""    drawTune(d);
    dbaPane();                                          /* a server of its own (1.0.289) */
    drawErasable(d.erasable || {});"""),
(
"""    drawHaRep(d, !!live);
    drawHaLb(d);""",
"""    drawHaRep(d, !!live);
    dbaHa(d);                                           /* the database servers (1.0.289) */
    drawHaLb(d);"""),
(
"""  nodes.hidden = d.nodes.length < 2;
  drawFwBody(d);
  explainWhatWasDrawn($('pane-fw'));""",
"""  nodes.hidden = d.nodes.length < 2;
  dbaFw();                                              /* the database servers (1.0.289) */
  drawFwBody(d);
  explainWhatWasDrawn($('pane-fw'));"""),
# Database -> TLS: a row per database server, the pill on the heading
(
"""    row.appendChild(sd);
    list.appendChild(row);
  });
  box.appendChild(list);
  host.appendChild(box);
}
/* What to switch to: for a server elsewhere its authority and the mode; for a""",
"""    row.appendChild(sd);
    list.appendChild(row);
  });
  /* The database servers looked after by agents (1.0.289): their certificate is put in by
     their agents, as the root helper does on a node. */
  (d.dbservers || []).forEach(function (s) {
    var row = el('div', 'hal-node dbs-hal');
    var st = dbaState(s), f = s.facts || {};
    var nm = el('b', 'hal-name dbs-hal-n');
    nm.appendChild(dbaDot(st[0]));
    nm.appendChild(noI18n(el('span', '', dbaLabel(s, d.dbservers))));
    row.appendChild(nm);
    var steps = el('div', 'hal-steps');
    steps.appendChild(el('span', 'hal-step', 'database server'));
    steps.appendChild(el('span', 'hal-step ' + (f.ssl ? 'ok' : ''), f.ssl ? 'TLS on' : 'no TLS'));
    steps.appendChild(el('span', 'hal-step ' + (st[0] === 'ok' ? 'ok' : (st[0] === 'bad' ? 'bad' : '')), st[0] === 'ok' ? 'its agent answers' : st[1]));
    row.appendChild(steps);
    var sd = el('div', 'hal-said small ' + (st[0] === 'bad' ? 'bad' : 'muted'));
    if (st[2]) sd.appendChild(noI18n(el('span', '', st[2])));
    else {
      sd.appendChild(el('span', '', 'node'));
      sd.appendChild(noI18n(el('span', '', ' ' + s.node + ' · ' + (s.db_host || s.host || ''))));
    }
    row.appendChild(sd);
    list.appendChild(row);
  });
  box.appendChild(list);
  host.appendChild(box);
  if (d.dbservers) dbaPillInto(card.querySelector(':scope > h2'), d.dbservers, 'dbtls');
}
/* What to switch to: for a server elsewhere its authority and the mode; for a"""),
# the move wizard's first step: connect a database server first
(
"""    page.appendChild(grid);
    var n = dbwFoot(null, function () { dbwGo(DBW.engine === 'sqlite' ? 2 : 1); });""",
"""    page.appendChild(grid);
    /* A database server with otp-db-agent (1.0.289): connected first, then moved onto. */
    if (ME && ME.role === 'fulladmin' && typeof dbaWizard === 'function') {
      var ag = el('div', 'dbw-agent small muted');
      ag.appendChild(el('span', '', 'A database server otp should look after itself (its certificate, settings, restarts)? Connect its agent first:'));
      var agb = el('button', 'linkish', 'Connect a database server…');
      agb.type = 'button';
      agb.id = 'dbw-agent';
      agb.onclick = function () { dbaWizard(); };
      ag.appendChild(document.createTextNode(' '));
      ag.appendChild(agb);
      page.appendChild(ag);
    }
    var n = dbwFoot(null, function () { dbwGo(DBW.engine === 'sqlite' ? 2 : 1); });"""),
])
with open(O + 'web/assets/admin.js', 'a') as f:
    f.write('\n' + JS)
with open(O + 'web/assets/otp.css', 'a') as f:
    f.write('\n' + CSS)
print('1.0.289 pages done')
