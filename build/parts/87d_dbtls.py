

# ---- the daemon's own connection to its database: encrypted and checked (1.0.170) -------
# Settings → The database → Encryption to the database server, as a wizard, on
# the running installation - every node, nothing stopped:
#   replicated - each node's own PostgreSQL has the cluster's certificate once
#                the link between the databases is encrypted (High availability):
#                it names localhost and 127.0.0.1, so each node only moves its
#                own connection over to verify-full with the cluster's authority;
#   local      - PostgreSQL on this machine, no cluster: it is given a
#                certificate from otp's own authority (renewed by itself 45 days
#                before it ends), then the connection moves over;
#   remote     - a database server elsewhere (and the one of a shared cluster):
#                its administrator gave it a certificate; its authority is given
#                here (or the system's is used) and every node moves over.
# Each move is made on the live database: the new connection is tried apart
# first, then config.json is written and the daemon's connections are made
# again with it - and put back at once to what they were if the first
# statement on the new one does not go. Switched off the same way.
DBTLS_CA = STATE_DIR / 'db-ca.pem'
DBTLS_EVERY = 300
DBTLS_RENEW_DAYS = 45
DBTLS_LOCK = threading.Lock()
DBTLS_WORK = {'at': 0.0}


def dbtls_kind(conf=None):
    c = CONFIG if conf is None else conf
    if c.get('db_engine') not in ('postgres', 'mariadb'):
        return 'sqlite'
    host = str(c.get('db_host') or '').strip()
    if not host or host.startswith('/'):
        return 'socket'                 # a Unix socket: nothing crosses a network
    local = host.strip('[]') in ('127.0.0.1', 'localhost', '::1')
    if c.get('db_engine') == 'postgres' and local:
        return 'replicated' if c.get('ha_mode') == 'replicated' else 'local'
    return 'remote'


def _dbtls_ssl(db):
    """What the server says of this very connection: (ssl, version, cipher)."""
    if db.engine == 'postgres':
        row = db.row('SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid()')
        if not row:
            return False, '', ''
        return bool(row.get('ssl')), str(row.get('version') or ''), str(row.get('cipher') or '')
    if db.engine == 'mariadb':
        got = {r.get('Variable_name') or r.get('variable_name'): r.get('Value') or r.get('value')
               for r in db.rows("SHOW SESSION STATUS LIKE 'Ssl_%'")}
        cipher = str(got.get('Ssl_cipher') or '')
        return bool(cipher), str(got.get('Ssl_version') or ''), cipher
    return False, '', ''


def dbtls_probe(mode, ca):
    """A connection of its own with these settings: whether it opens, and
    whether it is encrypted."""
    c = {k: CONFIG.get(k) for k in DB_KEYS}
    c.update(db_tls=mode, db_tls_ca=ca, db_timeout_s=8)
    began = time.time()
    try:
        db = db_open(c)
    except Exception as e:                              # noqa: BLE001
        return {'ok': False, 'said': scrub_secret(str(e).split('\n')[0])[:300], 'mode': mode,
                'ms': int((time.time() - began) * 1000)}
    try:
        db.value('SELECT 1')
        ssl_on, ver, cipher = _dbtls_ssl(db)
    except Exception as e:                              # noqa: BLE001
        return {'ok': False, 'said': scrub_secret(str(e).split('\n')[0])[:300], 'mode': mode,
                'ms': int((time.time() - began) * 1000)}
    finally:
        db.close()
    out = {'ok': True, 'ssl': ssl_on, 'version': ver, 'cipher': cipher, 'mode': mode,
           'ms': int((time.time() - began) * 1000)}
    if mode and not ssl_on:
        out.update(ok=False, said='it opened, but not encrypted - the server does not speak TLS')
    return out


def _dbtls_dbs(daemon):
    """Every connection of this daemon to its database."""
    out = [daemon.store.db]
    r = getattr(daemon, '_reader', None)
    if r is not None and getattr(r, 'db', None) is not None and r.db is not daemon.store.db:
        out.append(r.db)
    return out


def dbtls_switch(daemon, mode, ca, by):
    """This node's connection moved over to (mode, ca) - on the live database,
    put back as it was if the new one does not go."""
    with DBTLS_LOCK:
        if mode and dbtls_kind() in ('sqlite', 'socket'):
            raise ValueError('the database is %s - nothing goes over a network to encrypt'
                             % ('a file on this machine' if dbtls_kind() == 'sqlite' else
                                'reached over a Unix socket'))
        p = dbtls_probe(mode, ca)
        if not p['ok']:
            raise ValueError('a connection with %s did not go: %s' % (mode or 'no TLS', p['said']))
        old = (str(CONFIG.get('db_tls') or ''), str(CONFIG.get('db_tls_ca') or ''))
        if old == (mode, ca):
            return dict(p, changed=False)

        def use(m, c):
            write_file_settings({'db_tls': m, 'db_tls_ca': c})
            CONFIG['db_tls'], CONFIG['db_tls_ca'] = m, c
            for d in _dbtls_dbs(daemon):
                d.tls, d.tls_ca = m, c
                d.close()
        use(mode, ca)
        try:
            daemon.store.db.value('SELECT 1')
            ssl_on, ver, cipher = _dbtls_ssl(daemon.store.db)
            if mode and not ssl_on:
                raise ValueError('the new connection is not encrypted')
        except Exception as e:                          # noqa: BLE001
            use(*old)
            try:
                daemon.store.db.value('SELECT 1')
            except Exception:                           # noqa: BLE001
                pass
            raise ValueError('the daemon\'s connection did not go with it, so it is as it was: %s'
                             % scrub_secret(str(e).split('\n')[0])[:300])
        daemon.store.add_event('settings', '%s: the connection of %s to its database %s' % (
            by, node_name(), ('is encrypted (%s, %s)' % (mode, ver or 'TLS')) if mode else
            'is no longer encrypted'), 'warn' if not mode else 'info', who=by)
        dbtls_publish(daemon, force=True)
        return dict(p, changed=True, version=ver, cipher=cipher)


def _dbtls_server_cert(store, by):
    """This machine's PostgreSQL given a certificate from otp's authority
    (kind local): for localhost, 127.0.0.1 and its names; ssl switched on with
    a reload, no restart."""
    with HATLS_LOCK:
        ca = hatls_ca(store)
        if not ca['cas'] or float(ca['cas'][0].get('end') or 0) - time.time() < \
                HATLS_CA_ROLL_DAYS * 86400:
            hatls_ca_make(store, by)
    names = hatls_names()
    key, crt = hatls_issue(store, names)
    st = {}
    _hatls_ask(st, {'do': 'server', 'cert': crt, 'key': key, 'trust': hatls_trust(hatls_ca(store))})
    end = time.time() + 120
    while time.time() < end:
        got = _hatls_answer(st)
        if got is not None:
            if not got.get('ok'):
                raise ValueError(got.get('said') or 'the root helper said no')
            store.set_meta('dbtls:server:' + node_name(), json.dumps(
                {'cert_end': got.get('cert_end') or _cert_end(crt), 'at': time.time(), 'by': by,
                 'names': names}))
            return got
        time.sleep(0.5)
    raise ValueError('the root helper of this node did not answer in 2 minutes - is '
                     'otp-web.path running?  systemctl status otp-web.path')


def dbtls_apply(daemon, args):
    """What every node does when the wizard is told to switch it on, or off."""
    store = daemon.store
    by = str(args.get('by') or '?')
    want = str(args.get('mode') or '')
    if want not in ('', 'require', 'verify-ca', 'verify-full'):
        raise ValueError('the mode is require, verify-ca or verify-full')
    kind = dbtls_kind()
    said = []
    ca = ''
    if want:
        if kind == 'replicated':
            st = hatls_state(store)
            if st.get('step') != 'done':
                raise ValueError('this node\'s PostgreSQL has no certificate from the cluster yet - '
                                 'encrypt the link between the databases first (High availability)')
            ca = str(HA_CA_FILE)
        elif kind == 'local':
            if args.get('server') or not (_meta_json(store, 'dbtls:server:' + node_name()) or {}):
                got = _dbtls_server_cert(store, by)
                said.append(got.get('said') or 'PostgreSQL answers over TLS')
            ca = str(HA_CA_FILE)
        elif kind == 'remote':
            pem = str(args.get('ca_pem') or '').strip()
            if pem:
                if '-----BEGIN CERTIFICATE-----' not in pem:
                    raise ValueError('the authority is a PEM certificate')
                tmp = str(DBTLS_CA) + '.new'
                fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o640)
                with os.fdopen(fd, 'w') as f:
                    f.write(pem + '\n')
                os.replace(tmp, str(DBTLS_CA))
                ca = str(DBTLS_CA)
            elif args.get('keep_ca') and CONFIG.get('db_tls_ca'):
                ca = str(CONFIG.get('db_tls_ca'))
    got = dbtls_switch(daemon, want, ca, by)
    if got.get('changed') is False:
        said.append('it was so already')
    return dict(got, said='; '.join(said), kind=kind)


def dbtls_publish(daemon, force=False):
    """This node's connection as the server says it is, for the page."""
    now = time.time()
    if not force and now - DBTLS_WORK['at'] < DBTLS_EVERY:
        return
    DBTLS_WORK['at'] = now
    store = daemon.store
    row = {'at': now, 'kind': dbtls_kind(), 'mode': str(CONFIG.get('db_tls') or ''),
           'ca': str(CONFIG.get('db_tls_ca') or ''), 'engine': CONFIG.get('db_engine'),
           'host': str(CONFIG.get('db_host') or '')}
    try:
        row['ssl'], row['version'], row['cipher'] = _dbtls_ssl(store.db)
    except Exception as e:                              # noqa: BLE001
        row['said'] = str(e)[:200]
    srv = _meta_json(store, 'dbtls:server:' + node_name()) or {}
    if row['kind'] == 'local' and srv:
        row['cert_end'] = srv.get('cert_end')
    elif row['kind'] == 'replicated':
        row['cert_end'] = hatls_state(store).get('cert_end')
    store.set_meta('dbtls:node:' + node_name(), json.dumps(row))


def dbtls_tick(daemon):
    """Every few minutes: the row for the page; the own certificate (kind
    local) renewed 45 days before it ends - the connection keeps going."""
    dbtls_publish(daemon)
    if dbtls_kind() != 'local' or not CONFIG.get('db_tls'):
        return
    srv = _meta_json(daemon.store, 'dbtls:server:' + node_name()) or {}
    if srv and float(srv.get('cert_end') or 0) - time.time() < DBTLS_RENEW_DAYS * 86400 and \
            time.time() - float(srv.get('tried') or 0) > 6 * 3600:
        srv['tried'] = time.time()
        daemon.store.set_meta('dbtls:server:' + node_name(), json.dumps(srv))
        try:
            _dbtls_server_cert(daemon.store, 'otp (renewed)')
            daemon.store.add_event('settings', 'the certificate of %s\'s PostgreSQL was renewed'
                                   % node_name())
        except ValueError as e:
            daemon.store.add_event('settings', 'the certificate of %s\'s PostgreSQL could not be '
                                   'renewed: %s' % (node_name(), e), 'bad')


def dbtls_view(store):
    nodes = []
    for n in sorted(set(host_nodes(store)) | {node_name()}):
        row = _meta_json(store, 'dbtls:node:' + n) or {}
        nodes.append(dict(row, name=n, me=n == node_name()))
    hat = hatls_view(store) if CONFIG.get('ha_mode') == 'replicated' else None
    return {'kind': dbtls_kind(), 'engine': CONFIG.get('db_engine'), 'nodes': nodes,
            'mode': str(CONFIG.get('db_tls') or ''), 'ha_mode': CONFIG.get('ha_mode') or '',
            'link_done': bool(hat) and all(x.get('step') == 'done' for x in hat['nodes']) and
            len(hat['nodes']) >= 2, 'ca_given': DBTLS_CA.exists()}


@node_ask_kind('dbtls_probe')
def _ask_dbtls_probe(daemon, args):
    mode = str(args.get('mode') or '')
    kind = dbtls_kind()
    ca = str(args.get('ca') or '')
    if kind in ('replicated', 'local'):
        ca = str(HA_CA_FILE) if HA_CA_FILE.exists() else ''
    elif args.get('ca_pem'):
        tmp = tempfile.NamedTemporaryFile('w', suffix='.pem', dir=str(STATE_DIR), delete=False)
        tmp.write(str(args['ca_pem']) + '\n')
        tmp.close()
        ca = tmp.name
    try:
        return dict(dbtls_probe(mode, ca), kind=kind)
    finally:
        if args.get('ca_pem') and kind == 'remote':
            try:
                os.unlink(ca)
            except OSError:
                pass


@node_ask_kind('dbtls_apply')
def _ask_dbtls_apply(daemon, args):
    return dbtls_apply(daemon, args)
