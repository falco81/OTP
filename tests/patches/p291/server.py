# 1.0.291: moving the database onto the server of this node's otp-db-agent and off it - the
# move wizard's "make it for me" done by the agent, the agent let go once the database has left
# its server, the old server's rows and its TLS not carried to another one, the HA refusal said
# for layout B. Without an agent nothing changes.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


# ---- the agent's part ------------------------------------------------------------------------
edit('90d_dbagent.py', [
(
"""def db_agent_dbmake(c):
    \"\"\"The database and its account made on the agent's server, let in from this node.\"\"\"
    # This node by the address its database server sees it from (1.0.289: a node with several
    # addresses was let in by the one it reaches the outside with).
    me = db_agent_my_address(c.get('db_host'))
    peers = [x for x in (me, '127.0.0.1') if x]
    got = db_agent_call('dbmake', {'name': c['db_name'], 'user': c['db_user'],
                                   'password': c['db_password'], 'peers': peers}, timeout=120)
    said = list(got.get('said') or [])
""",
"""def db_agent_dbmake(c):
    \"\"\"The database and its account made on the agent's server, let in from this node.\"\"\"
    # This node by the address its database server sees it from (1.0.289: a node with several
    # addresses was let in by the one it reaches the outside with).
    me = db_agent_my_address(c.get('db_host'))
    peers = [x for x in (me, '127.0.0.1') if x]
    got = db_agent_call('dbmake', {'name': c['db_name'], 'user': c['db_user'],
                                   'password': c['db_password'], 'peers': peers}, timeout=120)
    said = [x for x in (got.get('said') or []) if 'has to start again' not in str(x)]
    # PostgreSQL listening on its network addresses only from a restart on (1.0.291): started
    # again by its agent - unless this node's own database runs on it now, which is not
    # stopped under it from here (the server's administrator restarts it, or the card does).
    if got.get('pg_restart_needed'):
        if db_agent_here():
            said.append('PostgreSQL there has to start again for listen_addresses: this node\\'s '
                        'database runs on it now - Settings -> The database -> Database server '
                        '-> Restart the database…')
        else:
            try:
                db_agent_restart()
                said.append('PostgreSQL started again by its agent (listen_addresses)')
            except ValueError as e:
                said.append('PostgreSQL there has to start again for listen_addresses, and its '
                            'agent could not: %s' % e)
"""),
(
"""def db_agent_is_target(c):""",
"""def db_other_server(c):
    \"\"\"Whether `c` names another database server than the one in use (its engine, address or
    port) - not merely another database on it (1.0.291).\"\"\"
    eng = str(c.get('db_engine') or '')
    if eng != str(CONFIG.get('db_engine') or 'sqlite'):
        return True
    if eng == 'sqlite':
        return False

    def norm(h):
        h = str(h or '').strip().strip('[]').lower()
        return '127.0.0.1' if h in ('', 'localhost', '127.0.0.1', '::1') else h
    dflt = 5432 if eng == 'postgres' else 3306
    try:
        return norm(c.get('db_host')) != norm(CONFIG.get('db_host')) or \\
            int(c.get('db_port') or dflt) != int(CONFIG.get('db_port') or dflt)
    except (TypeError, ValueError):
        return True


def db_move_agent_info():
    \"\"\"This node's database agent, for the move wizard (1.0.291): the server it makes a
    database on (make it for me), and whether this node's database is there now - or None.\"\"\"
    a = db_agent()
    if not a:
        return None
    eng = a.get('engine') or 'postgres'
    try:
        port = int(a.get('pg_port' if eng == 'postgres' else 'my_port') or 0)
    except (TypeError, ValueError):
        port = 0
    try:
        here = bool(db_agent_here())
    except Exception:                                   # noqa: BLE001
        here = False
    return {'host': a.get('host'), 'port': a.get('port'), 'engine': eng,
            'db_host': a.get('db_host') or a.get('host'),
            'db_port': port or (5432 if eng == 'postgres' else 3306), 'here': here,
            'layout_b': bool(here and CONFIG.get('ha_mode') == 'replicated')}


# The rows that say something of the database SERVER in use, not of otp (1.0.291): not true of
# another server, so not carried onto one - the new server's are written as they come.
DB_SERVER_ROWS = ('dbtls:server:', 'dbagent:node:', 'load:db:')


def db_agent_is_target(c):"""),
])

# ---- the TLS of the server in use not carried to another one (with an agent) ------------------
edit('80_daemon.py', [
(
"""    if c.get('db_engine') not in ('sqlite', 'mariadb', 'postgres'):
        raise ValueError('the engine is sqlite, mariadb or postgres')
    for k in ('db_name', 'db_user'):""",
"""    if c.get('db_engine') not in ('sqlite', 'mariadb', 'postgres'):
        raise ValueError('the engine is sqlite, mariadb or postgres')
    # Nor the encryption of the server in use (1.0.291, with a database agent): verify-full and
    # the authority of the server in use are that server's - carried to another one, a MariaDB
    # without TLS yet was asked for it, a PostgreSQL checked against an authority that never
    # signed its certificate. Off unless asked; Database -> TLS turns it on there afterwards.
    # Without an agent as it always was.
    if c.get('db_engine') != 'sqlite' and (given or {}).get('db_tls') is None and \\
            'db_agent_on' in globals() and db_agent_on() and db_other_server(c):
        c['db_tls'] = ''
        if (given or {}).get('db_tls_ca') is None:
            c['db_tls_ca'] = ''
    for k in ('db_name', 'db_user'):"""),
(
"""            load_tables(far, copy, say=along)
            dbguard_resign(SimpleStore(far))       # the rows carried signed there (1.0.231)""",
"""            load_tables(far, copy, say=along)
            # What the rows say of the database server in use is not true of another one
            # (1.0.291, with a database agent): its certificate from otp's authority, what its
            # agent said, the meter's reading. The new server's are written as they come.
            if 'db_agent_on' in globals() and db_agent_on() and db_other_server(c):
                for k in DB_SERVER_ROWS:
                    try:
                        far.run('DELETE FROM meta WHERE k = ?', (k + node_name(),))
                    except Exception as e:              # noqa: BLE001
                        log('the rows of the old database server could not be left out: %s' % e,
                            'warn')
            dbguard_resign(SimpleStore(far))       # the rows carried signed there (1.0.231)"""),
])

# ---- the page's requests -----------------------------------------------------------------------
LAYOUT_B_WHY = (
    "'this node is one of a cluster (replicated - each node\\'s database on a server of its own, '\n"
    "                            'looked after by its agent, the two replicating): its database is the '\n"
    "                            'cluster\\'s. Moving it - to another engine, another server or back onto '\n"
    "                            'this machine - would break the replication and leave the other node on '\n"
    "                            'its own. Switch the replication off first (Settings → High availability), '\n"
    "                            'then otp --ha-standalone --yes on both nodes; move it; build the cluster '\n"
    "                            'again.'")
edit('90_api.py', [
(
"""            'cluster': in_cluster(h.store), 'ha_mode': CONFIG.get('ha_mode') or '',
            # Its own key (1.0.249)""",
"""            'cluster': in_cluster(h.store), 'ha_mode': CONFIG.get('ha_mode') or '',
            # This node's database agent, for the move wizard (1.0.291) - only with one.
            **({'agent': db_move_agent_info()} if db_agent_on() else {}),
            # Its own key (1.0.249)"""),
(
"""    if in_cluster(h.store) and act in ('move', 'use', 'empty'):
        raise ApiError(409, 'this node is one of a cluster: its database is not moved from here '
                            '(switch the replication off first - Settings → High availability)')""",
"""    if in_cluster(h.store) and act in ('move', 'use', 'empty', 'setup') and \\
            CONFIG.get('ha_mode') == 'replicated' and db_agent_here():
        # Each node's database on a server of its own (1.0.291): said so, with the way out.
        raise ApiError(409, """ + LAYOUT_B_WHY + """)
    if in_cluster(h.store) and act in ('move', 'use', 'empty'):
        raise ApiError(409, 'this node is one of a cluster: its database is not moved from here '
                            '(switch the replication off first - Settings → High availability)')"""),
(
"""            if act == 'try':
                got = db_try(c)
                got['in_use'] = db_same_place(h.store, c)
                return got""",
"""            if act == 'try':
                got = db_try(c)
                got['in_use'] = db_same_place(h.store, c)
                if db_agent_on():
                    # The server of this node's database agent (1.0.291): made there by the
                    # agent - no administrator typed in.
                    got['agent_server'] = db_agent_is_target(c)
                return got"""),
(
"""                first = db_try(c) if c.get('db_password') else {'reached': False}
                fresh = ''
                if first.get('reached') and first.get('writable'):
                    made = ['the database and the account are there already, and it gets in']
                else:""",
"""                first = db_try(c) if c.get('db_password') else {'reached': False}
                fresh = ''
                if first.get('reached') and first.get('writable'):
                    made = ['the database and the account are there already, and it gets in']
                elif b.get('by_agent'):
                    # Made for me on the server of this node's database agent (1.0.291): the
                    # database, the account with its password (made up when none is given),
                    # this node let in (pg_hba.conf, or 'user'@'node'), the firewall.
                    if not db_agent_on() or not db_agent_is_target(c):
                        raise ApiError(400, 'only the server of this node\\'s database agent is '
                                            'made by otp itself: give an administrator of that '
                                            'server instead')
                    if not c.get('db_password'):
                        fresh = c['db_password'] = db_password_made()
                    try:
                        made = db_agent_dbmake(c)
                    except ValueError as e:
                        raise ApiError(400, 'its agent did not make it: %s' % e)
                    made = made or ['made by its agent']
                else:"""),
(
"""                write_file_settings({k: c[k] for k in DB_KEYS})
                h.store.add_event('settings', '%s switched the database to %s at %s; the '
                                  'daemon starts again on it' % (s['name'], words, db_where(c)),
                                  'warn', who=s['name'])""",
"""                was_here = db_agent_here()
                write_file_settings({k: c[k] for k in DB_KEYS})
                h.store.add_event('settings', '%s switched the database to %s at %s; the '
                                  'daemon starts again on it' % (s['name'], words, db_where(c)),
                                  'warn', who=s['name'])
                # Moved off the server of this node's database agent (1.0.291): the agent is
                # no longer this node's - let go after the switch, never before (until
                # config.json names the new database, the agent is as it was).
                agent_said = ''
                if db_agent_on():
                    try:
                        agent_said = db_agent_after_move(h.store, was_here, c, s['name'])
                    except Exception as e:              # noqa: BLE001
                        log('the database agent could not be let go after the move: %s - otp '
                            '--db-agent-forget --yes' % e, 'warn')"""),
(
"""                return {'message': 'the daemon starts again on %s in a moment' % words,
                        'restarting': True}""",
"""                return dict({'message': 'the daemon starts again on %s in a moment' % words,
                             'restarting': True}, **({'agent': agent_said} if agent_said else {}))"""),
])
print('1.0.291 parts done')
