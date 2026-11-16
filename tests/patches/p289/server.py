# 1.0.289: the database on a server of its own, looked after by otp-db-agent (isemon's external-db kit,
# 2nd edition, acme 1.0.115) - layout A: one otp node (or a shared pair) and its database server.
#   python3 server.py PARTS BUILD_SH
# Without the node's own file (STATE_DIR/db-agent/agent.json) every path below is the one it was:
# each branch is `if db_agent_here():` (or db_agent_on()) at the top of a function, the old code
# untouched under it.
import os, shutil, sys
P = sys.argv[1].rstrip('/') + '/'
HERE = os.path.dirname(os.path.abspath(__file__))


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


# ---- the node's side: one part of its own (routes need 90_api's route()) -------------------
shutil.copy(os.path.join(HERE, '90d_dbagent.py'), P + '90d_dbagent.py')
if len(sys.argv) > 2:
    b = open(sys.argv[2]).read()
    if 'parts/90d_dbagent.py' not in b:
        assert b.count('parts/90z_clock_api.py ') == 1
        b = b.replace('parts/90z_clock_api.py ', 'parts/90z_clock_api.py parts/90d_dbagent.py ')
        open(sys.argv[2], 'w').write(b)

# ---- the daemon: the watching thread, only with an agent ------------------------------------
edit('80_daemon.py', [(
"""        threading.Thread(target=dbtls_watch, args=(self,), name='dbtls-watch', daemon=True).start()
""",
"""        threading.Thread(target=dbtls_watch, args=(self,), name='dbtls-watch', daemon=True).start()
        # The database on a server of its own (1.0.289): its agent watched - nothing without one.
        _db_agent_start(self)
"""),
# the server's own settings: the machine told by the agent, the restart through it
(
"""    facts = {'local': local, 'ram_gb': None, 'cpus': None, 'disk': None, 'avail': None,
             'ram': None, 'virtual': None, 'rotational': None,
             'source': 'this machine' if local else ''}
    if local:
""",
"""    facts = {'local': local, 'ram_gb': None, 'cpus': None, 'disk': None, 'avail': None,
             'ram': None, 'virtual': None, 'rotational': None,
             'source': 'this machine' if local else ''}
    if not local and db_agent_here(c):
        # A server of its own, told by its agent (1.0.289).
        try:
            f = db_agent_call('status', timeout=20).get('facts') or {}
            facts.update(ram=f.get('ram'), avail=f.get('avail'), cpus=f.get('cpus'),
                         virtual=f.get('virtual'), source='the database server (otp-db-agent)')
            if facts['ram']:
                facts['ram_gb'] = round(facts['ram'] / 1073741824.0, 1)
        except ValueError:
            pass
    if local:
"""),
(
"""    if db.engine != 'postgres':
        return {'may': False, 'unit': ''}
    host = str(CONFIG.get('db_host') or '').lower()
    if host not in ('', 'localhost', '127.0.0.1', '::1', socket.gethostname().lower()):
        return {'may': False, 'unit': 'postgresql',""",
"""    if db.engine != 'postgres':
        return {'may': False, 'unit': ''}
    if db_agent_here():
        return {'may': True, 'unit': 'otp-db-agent', 'why': ''}       # through it (1.0.289)
    host = str(CONFIG.get('db_host') or '').lower()
    if host not in ('', 'localhost', '127.0.0.1', '::1', socket.gethostname().lower()):
        return {'may': False, 'unit': 'postgresql',"""),
(
"""    db = store.db
    ready = tune_restart_ready(store)
    if db.engine != 'postgres' or not ready['unit']:
        raise ValueError('no database server is running as a service on this machine')""",
"""    db = store.db
    if db_agent_here() and db.engine == 'postgres' and not in_cluster(store):
        # On a server of its own: its agent starts it again and waits for it (1.0.289). In a
        # cluster the path below (the other node answering meanwhile) - its restart through
        # pg_restart_local, which asks the agent too.
        waiting = tune_pending(db)
        if not waiting:
            raise ValueError('nothing waits for a restart')
        said = db_agent_restart().get('said') or 'started again'
        store.add_event('settings', '%s restarted the database server through its agent for '
                        'the settings waiting for it: %s' % (by, ', '.join(waiting)), 'warn', who=by)
        left = tune_pending(db)
        return {'unit': 'otp-db-agent', 'waiting': waiting, 'still': left,
                'message': '%s%s' % (said, '; still waiting: ' + ', '.join(left) if left else
                                     ': every setting is in effect')}
    ready = tune_restart_ready(store)
    if db.engine != 'postgres' or not ready['unit']:
        raise ValueError('no database server is running as a service on this machine')"""),
])

# ---- the root helper's PostgreSQL parts: the agent's way when the database is on its server --
edit('87_ha.py', [
(
"""def pg_local_running(port=5432):
    try:""",
"""def pg_local_running(port=5432):
    if db_agent_here():
        return db_agent_running()       # on a server of its own (1.0.289)
    try:"""),
(
"""    \"\"\"PostgreSQL `major` on this machine, installed, initialised and running.\"\"\"
    if shutil.which('dnf'):""",
"""    \"\"\"PostgreSQL `major` on this machine, installed, initialised and running.\"\"\"
    if db_agent_here():
        # The agent first (1.0.289): away, it was said that PostgreSQL was not installed.
        try:
            db_agent_call('status', timeout=20)
        except ValueError as e:
            raise ValueError('%s - start it on the database server %s (systemctl start '
                             'otp-db-agent), then run this again' % (e, db_agent_db_host()))
        raise ValueError('PostgreSQL does not answer on the database server %s (its agent does): '
                         'install it there (install.sh --db-server postgres) and start it'
                         % db_agent_db_host())
    if shutil.which('dnf'):"""),
(
"""def pg_restart_local(port=5432):
    unit = tune_restart_unit()""",
"""def pg_restart_local(port=5432):
    if db_agent_here():
        db_agent_restart()              # through the agent of its server (1.0.289)
        return
    unit = tune_restart_unit()"""),
(
"""    restarted for it.\"\"\"
    pg_names_otps(port, name, user)""",
"""    restarted for it.\"\"\"
    if db_agent_here():
        # The same on a server of its own, by its agent (1.0.289).
        return db_agent_prepare(peer, name, user, password, say,
                                extra=[own_address] if own_address else ())
    pg_names_otps(port, name, user)"""),
(
"""def pg_publication(port, name):
""",
"""def pg_publication(port, name):
    if db_agent_here():
        db_agent_publication(name)      # FOR ALL TABLES needs a superuser: the agent's (1.0.289)
        return
"""),
])

edit('88w_web.py', [(
"""    got = {}
    if ask_log and WEB_DIR.is_dir():
        ask = WEB_DIR / PGLOG_ASK""",
"""    got = {}
    if ask_log and db_agent_here():
        got = db_agent_pglog()          # the log is on the database server (1.0.289)
    elif ask_log and WEB_DIR.is_dir():
        ask = WEB_DIR / PGLOG_ASK""")])

edit('87t_hatls.py', [
(
"""    for n in (CONFIG.get('ha_address'), node_address(), socket.gethostname(), socket.getfqdn(),
              peer_host):""",
"""    for n in (CONFIG.get('ha_address'), node_address(), socket.gethostname(), socket.getfqdn(),
              peer_host) + ((db_agent_db_host(),) if db_agent_here() else ()):"""),
(
"""    PgtlsBusy at once instead of waiting - tried again at its next pass.\"\"\"
""",
"""    PgtlsBusy at once instead of waiting - tried again at its next pass.\"\"\"
    if db_agent_here():
        # The database on a server of its own (1.0.289): its agent does it, the answer written
        # to the same file - every reader of it as it was.
        return db_agent_pgtls_send(data)
"""),
(
"""    s = socket.create_connection(('127.0.0.1', int(CONFIG.get('db_port') or 5432)), timeout=5)
    try:
        s.sendall(struct.pack('!II', 8, 80877103))           # SSLRequest""",
"""    s = socket.create_connection((db_agent_db_host() if db_agent_here() else '127.0.0.1',
                                  int(CONFIG.get('db_port') or 5432)), timeout=5)
    try:
        s.sendall(struct.pack('!II', 8, 80877103))           # SSLRequest"""),
(
"""    cas += [x for x in ca['cas'] if fnum(x.get('end')) > now][:3]
    store.set_meta('hatls:ca', json.dumps({'cas': cas}))
""",
"""    cas += [x for x in ca['cas'] if fnum(x.get('end')) > now][:3]
    store.set_meta('hatls:ca', json.dumps({'cas': cas}))
    # The agent told the cluster's authorities again (1.0.289): it knows by them which cluster
    # the database server's certificate is.
    DBAGENT_STATE['trust_due'] = True
"""),
])

edit('87d_dbtls.py', [
(
"""    if c.get('db_engine') == 'postgres' and local:
        return 'replicated' if c.get('ha_mode') == 'replicated' else 'local'
    return 'remote'
""",
"""    if c.get('db_engine') == 'postgres' and local:
        return 'replicated' if c.get('ha_mode') == 'replicated' else 'local'
    if conf is None and c.get('db_engine') == 'postgres' and db_agent_here(c):
        # On a server of its own, looked after by its agent (1.0.289): as one on this machine.
        return 'replicated' if c.get('ha_mode') == 'replicated' else 'local'
    return 'remote'
"""),
(
"""    own_ca = bool(hatls_trust(hatls_ca(store))) if CONFIG.get('db_engine') == 'postgres' else False
    return {'kind': dbtls_kind(), 'engine': CONFIG.get('db_engine'), 'nodes': nodes,""",
"""    own_ca = bool(hatls_trust(hatls_ca(store))) if CONFIG.get('db_engine') == 'postgres' else False
    more = {}
    if db_agent_on():
        # the database servers of their own beside the nodes (1.0.289)
        more = {'db_admin': db_admin(), 'dbservers': db_agent_servers(store)}
    return dict(more, **{'kind': dbtls_kind(), 'engine': CONFIG.get('db_engine'), 'nodes': nodes,"""),
(
"""            'hisec': hisec_enforced('db:tls', store)}


@node_ask_kind('dbtls_probe')""",
"""            'hisec': hisec_enforced('db:tls', store)})


@node_ask_kind('dbtls_probe')"""),
])

edit('90_api.py', [(
"""    nodes = [dict(n, web=web_unmapped(n['web'], me)) if isinstance(n, dict) and 'web' in n else n
             for n in ha_nodes(h.store)]
    return {'node': node_name(), 'address': node_address(), 'nodes': nodes,""",
"""    nodes = [dict(n, web=web_unmapped(n['web'], me)) if isinstance(n, dict) and 'web' in n else n
             for n in ha_nodes(h.store)]
    if db_agent_on():
        # The database servers of their own beside the nodes (1.0.289).
        return dict(_ha_view(h, me, nodes), db_admin=db_admin(), dbservers=db_agent_servers(h.store))
    return _ha_view(h, me, nodes)


def _ha_view(h, me, nodes):
    return {'node': node_name(), 'address': node_address(), 'nodes': nodes,""")])

# ---- the network job: the new address let in by the agent before anything changes ----------
edit('87n_net.py', [(
"""            _job_put(store, job, 'the node\\'s name %s kept in config.json, whatever the host '
                     'name' % me, 8)
""",
"""            _job_put(store, job, 'the node\\'s name %s kept in config.json, whatever the host '
                     'name' % me, 8)
        # 1b. The database on a server of its own (1.0.289): the new address let into it and
        # through its firewall by its agent before anything changes - and the other node told,
        # whose agent lets it in too. Without an agent nothing of it runs.
        if w.get('ip_changed') and w.get('new_ip') and db_agent_here():
            said = db_agent_node_moved(store, w.get('old_ip') or '', w['new_ip'])
            _job_put(store, job, 'the database server lets %s in (otp-db-agent): %s' % (
                w['new_ip'], '; '.join(said) or 'it did already'), 9)
""")])

# ---- MariaDB asked for TLS never goes on in the clear --------------------------------------
edit('20_db.py', [(
"""                except Exception as e:
                    raise DbError('MariaDB at %s could not be reached: %s' % (self.where(), e))
""",
"""                except Exception as e:
                    raise DbError('MariaDB at %s could not be reached: %s' % (self.where(), e))
                want_tls = str((CONFIG.get('db_tls') if self.tls is None else self.tls) or '')
                if want_tls in ('require', 'verify-ca', 'verify-full'):
                    # PyMySQL goes on unencrypted when the server does not offer TLS - asked
                    # for it, never (1.0.289): a MariaDB without TLS yet ran in the clear while
                    # config.json said verify-full.
                    import ssl as _ssl
                    if not isinstance(getattr(self.conn, '_sock', None), _ssl.SSLSocket):
                        try:
                            self.conn.close()
                        except Exception:               # noqa: BLE001
                            pass
                        self.conn = None
                        raise DbError('MariaDB at %s could not be reached: the connection asks '
                                      'for TLS (%s) and the server does not offer it - turn TLS '
                                      'on there, or the encryption off (db_tls)'
                                      % (self.where(), want_tls))
""")])

# ---- alerts, metrics, the status, the command line ---------------------------------------
edit('88z_alerts.py', [(
"""    # The security check (off by default).
    if CONFIG.get('alerts_hisec'):""",
"""    # The database servers looked after by agents (1.0.289): none without an agent.
    try:
        for p in _db_agent_alerts(store, lang):
            add(p['key'], p['level'], p.get('node') or '', p['title'], p['words'], p.get('pane') or 'db')
    except Exception as e:                              # noqa: BLE001
        log_sparing('alerts-dbagent', 'the alerts of the database agent: %s' % e, 'warn', every=600)
    # The security check (off by default).
    if CONFIG.get('alerts_hisec'):""")])

edit('90p_metrics.py', [(
"""    m.put('otp_high_security', 'gauge', 'Whether high security is on.',""",
"""    try:
        for name, words, kind, rows in _db_agent_metrics(store):     # only with an agent (1.0.289)
            m.put(name, kind, words, rows)
    except Exception as e:                              # noqa: BLE001
        log_sparing('metrics-dbagent', 'Prometheus, the database agent: %s' % e, 'warn', every=600)
    m.put('otp_high_security', 'gauge', 'Whether high security is on.',""")])

edit('95_cli.py', [
(
"""                        'joining throws away (1.0.59: --yes alone no longer means that)')
    return p
""",
"""                        'joining throws away (1.0.59: --yes alone no longer means that)')
    _db_agent_cli_args(p)           # the database on a server of its own (1.0.289)
    return p
"""),
(
"""    _LOG_TO_STDERR = False
    if args.rename_from_opt:""",
"""    _LOG_TO_STDERR = False
    got = _db_agent_cli(args)       # --db-agent-* (1.0.289); None when none was asked
    if got is not None:
        return got
    if args.rename_from_opt:"""),
(
"""        print(pal.ok_line('the database: %s (%s)' % (store.db.where(), store.db.version())))
""",
"""        print(pal.ok_line('the database: %s (%s)' % (store.db.where(), store.db.version())))
        try:
            for line in _db_agent_status_lines(store, pal):     # only with an agent (1.0.289)
                print(line)
        except Exception as e:                          # noqa: BLE001
            print(pal.warn_line('the database agent: %s' % e))
"""),
])
print('1.0.289 server parts done')
