
# ---------------------------------------------------------------------------
# Two servers, both answering: high availability, active/active (1.0.13)
# ---------------------------------------------------------------------------
# Both nodes open the same PostgreSQL and keep nothing that matters anywhere
# else, so that a load balancer may send any request - a RADIUS packet, a
# page, the second half of an enrolment - to either, round robin and without
# stickiness:
#
#   * every setting, client, realm, directory and token is in the database,
#     and a node that sees another node's change (`conf_serial`) reads it in
#     within five seconds;
#   * a sign-in is a row in the database, and so is what belongs to it (the
#     "Edit the columns" switch); a job's progress (a move, an erase) is in
#     the database too, so the bar keeps moving whichever node is asked;
#   * a code is used up with one conditional UPDATE, and a row of its own in
#     token_once that nothing ever writes over (1.0.101). With two
#     replicating databases (ha_mode "replicated") a node also looks in the
#     other node's database before it lets a code in - so the same code sent
#     to both nodes at the same moment is let in once, not once on each, and
#     a used recovery code does not come back when replication writes an
#     older copy of the token's row. Only while the other node's database
#     cannot be reached at all is a code checked against this node's rows
#     alone (said in the log);
#   * the nightly dump is claimed by one node, with one conditional UPDATE;
#   * the key that seals the tokens is the same file on both, carried to the
#     second node once in a bundle locked with a passphrase.
#
# Each node writes a heartbeat into the database every fifteen seconds; the
# pages show the nodes and how long since each was heard from.

HA_KIND = 'otp-ha-join'
HA_STORE = {'store': None}
HEARTBEAT_S = 15
# One subscription of this database by its name (1.0.170): pg_subscription is
# the whole server's catalog - a second database on the same PostgreSQL (or one
# left from before) has subscriptions of the same names, and they were taken
# for this one's: ALTER SUBSCRIPTION ... does not exist.
SUB_HERE_SQL = ('SELECT 1 FROM pg_subscription WHERE subdbid = (SELECT oid FROM pg_database '
                'WHERE datname = current_database()) AND subname = ?')


def node_name():
    return this_node_name()


def node_address():
    """The address this machine uses to reach the outside - what a peer would
    use to reach it."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('192.0.2.1', 9))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return ''


# Set while this node is rebuilt from the other (1.0.44): it answers nothing
# and writes nothing until every row has come over.
HA_REBUILDING = threading.Event()
HA_REBUILD_LOCK = 7_011_959     # pg advisory lock: one rebuild in the cluster (1.0.59)
HA_REBUILDER = [None]          # the thread that rebuilds; the only one that writes meanwhile


FW_NOW_SENT = {}


def fw_now_publish(store, asked=False):
    """This node's whole firewall into its row for the other node's pages
    (1.0.71): when root read it again, and every 10 minutes all the same -
    a row lost on the way (a rebuild, a restore) was never written again.
    The other node's page may ask for it to be read again: 'fw:ask:<node>'."""
    me = node_name()
    try:
        ask = float(store.get_meta('fw:ask:' + me) or 0)
    except (TypeError, ValueError):
        ask = 0
    if ask and ask > FW_NOW_SENT.get('asked', 0):
        FW_NOW_SENT['asked'] = ask
        fw_now_ask(wait=0)              # root reads it within a second or two
    got = fw_now_read()
    at = got.get('full_at')
    if not at:
        return
    if FW_NOW_SENT.get('at') == at and time.time() - FW_NOW_SENT.get('when', 0) < 600:
        return
    store.set_meta('fw:now:' + me, json.dumps({'full': got.get('full') or {}, 'full_at': at}))
    FW_NOW_SENT.update(at=at, when=time.time())


def heartbeat(store, daemon=None):
    if HA_REBUILDING.is_set():
        return {}                       # nothing written while the rows come over (1.0.44)
    beat = {'at': time.time(), 'version': __version__, 'address': node_address(),
            'host': socket.gethostname(), 'started': daemon.started if daemon else None,
            'radius': list(getattr(getattr(daemon, 'radius', None), 'bound', []) or []),
            'engine': store.db.engine,
            'maintenance': bool(maintenance_now(store).get('on')),
            # What its own settings are in effect (1.0.67), its config.json's
            # among them, for the other node's pages to show as they are.
            'own': {k: (CONFIG.get(k) if not isinstance(CONFIG.get(k), bytes) else '')
                    for k in NODE_KEYS},
            'own_file': sorted(k for k in NODE_KEYS if k in (FILE_KEYS or ()))}
    try:
        beat['software'] = software_info(store)  # for the other node's About (1.0.99)
    except Exception:                                   # noqa: BLE001
        pass
    try:
        beat['web'] = web_state(store)          # TLS and the VIP address (1.0.47)
        # The whole firewall goes in a row of its own, when it changed
        # (1.0.67) - not into a heartbeat written every 15 s.
        for k in ('full', 'full_at', 'full_backend'):
            (beat['web'].get('fw') or {}).pop(k, None)
        fw_now_publish(store)
    except Exception:                                   # noqa: BLE001
        pass
    beat['mid'] = machine_id()
    name_clash_check(store, beat)
    store.set_meta('node:' + node_name(), json.dumps(beat))
    return beat


# Two machines with one name (1.0.110): both wrote the same heartbeat row, so
# the other looked gone and the VIP address "on both". Each row now carries
# the machine it came from; a row from another machine, fresh, under this
# node's name is said loudly - in the log, on every page and in --ha-status.
NAME_CLASH = {}
NAME_CLASH_SEEN = []


def machine_id():
    """This installation: the machine's id, its host name and where its state
    is - a VM cloned with its machine-id still tells itself apart by its
    host name."""
    got = ''
    for f in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
        try:
            got = Path(f).read_text().strip()
        except OSError:
            continue
        if got:
            break
    return hashlib.sha256(('%s|%s|%s' % (got, socket.gethostname(), STATE_DIR)).encode()
                          ).hexdigest()[:24]


def name_clash_check(store, beat):
    try:
        was = json.loads(store.get_meta('node:' + node_name()) or '{}')
    except ValueError:
        was = {}
    now = time.time()
    other = was.get('mid')
    if other and other != beat['mid'] and now - float(was.get('at') or 0) < HEARTBEAT_S * 3:
        # Seen twice before it is said: once is this machine's own row from
        # before a new host name, overwritten by the beat after this one.
        NAME_CLASH_SEEN.append(now)
        del NAME_CLASH_SEEN[:-2]
        if len(NAME_CLASH_SEEN) < 2:
            return
        first = not NAME_CLASH
        NAME_CLASH.update(name=node_name(), address=was.get('address') or '?',
                          host=was.get('host') or '?', at=now)
        if first or now - NAME_CLASH.get('said', 0) > 600:
            NAME_CLASH['said'] = now
            log('two machines call themselves %s: this one (%s, %s) and %s (%s) - give '
                'one of them its own name: otp --set node_name=NAME on it, then systemctl '
                'restart otp (docs/renaming-and-readdressing.md)'
                % (node_name(), beat.get('address'), beat.get('host'), NAME_CLASH['address'],
                   NAME_CLASH['host']), 'error')
    elif now - (NAME_CLASH_SEEN or [0])[-1] > HEARTBEAT_S * 4:
        NAME_CLASH.clear()
        del NAME_CLASH_SEEN[:]


def name_clash_words():
    if not NAME_CLASH or NAME_CLASH.get('name') != node_name():
        return ''
    return ('two machines call themselves %s: this one and %s (%s) - each node needs a name '
            'of its own (otp --set node_name=NAME on one of them, then systemctl restart otp)'
            % (NAME_CLASH['name'], NAME_CLASH['address'], NAME_CLASH['host']))


def node_name_taken(store, want):
    """Another machine, answering now, already called want? (1.0.110)"""
    want = str(want or '').strip()
    if not want or want == node_name():
        return None
    mine = machine_id()
    for n in ha_nodes(store):
        if n['name'] == want and n.get('alive') and n.get('mid', '') != mine:
            return n
    return None


def ha_nodes(store):
    out = []
    try:
        rows = store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'node:%'")
    except Exception:                                   # noqa: BLE001
        rows = []
    now = time.time()
    for r in rows:
        try:
            beat = json.loads(r['v'] or '{}')
        except ValueError:
            continue
        name = r['k'][5:]
        age = now - float(beat.get('at') or 0)
        beat.update(name=name, age=age, me=name == node_name(),
                    alive=age < HEARTBEAT_S * 3)
        out.append(beat)
    out.sort(key=lambda b: (not b['me'], b['name']))
    return out


def ha_forget(store, name):
    if name == node_name():
        raise ValueError('this is the node answering: it would write itself back at once')
    store.db.run('DELETE FROM meta WHERE k = ?', ('node:' + name,))


def ha_lead(store):
    """Whether this node is the one of a replicated pair that does what one
    node does for both (1.0.147): the first by name of the nodes heard from,
    this one when it hears no other."""
    if CONFIG.get('ha_mode') != 'replicated':
        return True
    alive = sorted(n['name'] for n in ha_nodes(store) if n.get('alive') or n.get('me'))
    return not alive or alive[0] == node_name()


def claim_once(store, key, value):
    """True for exactly one node: the one whose conditional UPDATE changed the
    row. A key not there yet is made first; two nodes making it at the same
    moment cannot both insert it (it is the primary key).

    Two replicated databases are two tables, though: each node's INSERT went
    in, and replication then stopped on the other's for good; each UPDATE
    took the day too. A key of both nodes (not one of this node's own,
    'NAME:NODE') is claimed by one node alone since 1.0.147 - see ha_lead -
    so only that one ever writes its row."""
    if CONFIG.get('ha_mode') == 'replicated' and not key.endswith(':' + node_name()) and \
            not ha_lead(store):
        return False
    if store.get_meta(key) is None:
        try:
            store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (key, ''))
        except Exception:                               # noqa: BLE001
            pass
    return bool(store.db.run('UPDATE meta SET v = ? WHERE k = ? AND (v IS NULL OR v <> ?)',
                             (str(value), key, str(value))))


def sub_connection_set(store, sub, conninfo):
    """ALTER SUBSCRIPTION ... CONNECTION, its password kept out of PostgreSQL's
    log (1.0.136) and the text as it is - a ? in a password was taken for a
    parameter (1.0.139). Raises ValueError, the password scrubbed."""
    for quiet in ("SET log_statement = 'none'", "SET log_min_error_statement = 'panic'"):
        try:
            store.db.run(quiet)
        except Exception:                               # noqa: BLE001
            pass
    try:
        store.db.run(RawSql("ALTER SUBSCRIPTION %s CONNECTION '%s'"
                            % (sub, conninfo.replace("'", "''"))))
    except Exception as e:                              # noqa: BLE001
        raise ValueError('the subscription %s could not be changed: %s'
                         % (sub, scrub_secret(str(e).split('\n')[0][:300])))
    finally:
        for back in ('RESET log_statement', 'RESET log_min_error_statement'):
            try:
                store.db.run(back)
            except Exception:                           # noqa: BLE001
                pass


# ---- a job's progress, where both nodes can read it ------------------------------
def job_publish(job):
    store = HA_STORE.get('store')
    if not store or HA_REBUILDING.is_set():
        return
    try:
        store.set_meta('db_job:' + node_name(), json.dumps(dict(job, node=node_name(),
                                                                at=time.time()),
                                                           default=str))
    except Exception:                                   # noqa: BLE001
        pass


def job_read():
    """The job as the database has it - this node's, or the other's."""
    if DB_JOB.get('running') or DB_JOB.get('ended'):
        here = dict(DB_JOB, node=node_name())
    else:
        here = None
    store = HA_STORE.get('store')
    there = None
    if store:
        try:
            for r in store.db.rows("SELECT v FROM meta WHERE k LIKE 'db!_job:%' ESCAPE '!'"):
                one = json.loads(r['v'] or 'null')
                # Going on, by the word of a node that has not said so for
                # five minutes - or of this node, which is not running it:
                # it ended with the process that ran it (1.0.37).
                if one and one.get('running') and (
                        time.time() - float(one.get('at') or one.get('began') or 0) > 300 or
                        (one.get('node') == node_name() and not DB_JOB.get('running'))):
                    one = dict(one, running=False, ended=float(one.get('at') or 0),
                               error=one.get('error') or 'it stopped with the service that '
                               'ran it (restarted, or the database was changed)')
                if one and (not there or float(one.get('began') or 0) >
                            float(there.get('began') or 0)):
                    there = one
        except Exception:                               # noqa: BLE001
            there = None
    if here and (not there or float(here.get('began') or 0) >= float(there.get('began') or 0)):
        return here
    return there or dict(DB_JOB)


# ---- the bundle that carries a cluster to its second node --------------------------
def _bundle_key(passphrase, salt):
    return hashlib.scrypt(str(passphrase).encode('utf-8'), salt=salt, n=2 ** 15, r=8, p=1,
                          maxmem=64 * 1024 * 1024, dklen=32)


def bundle_lock(data, passphrase, kind=None):
    salt = secrets.token_bytes(16)
    key = _bundle_key(passphrase, salt)
    raw = json.dumps(data).encode('utf-8')
    nonce = secrets.token_bytes(16)
    hide = hmac.new(key, b'hide', hashlib.sha256).digest()
    sign = hmac.new(key, b'sign', hashlib.sha256).digest()
    body = bytes(a ^ b for a, b in zip(raw, _seal_stream(hide, nonce, len(raw))))
    # Format 2 (1.0.101): what kind of bundle it is is signed too, so a
    # backup of tokens cannot be handed in as a cluster's bundle, nor the
    # other way round.
    tag = hmac.new(sign, (kind or HA_KIND).encode('utf-8') + b'\n' + salt + nonce + body,
                   hashlib.sha256).digest()
    return {'kind': kind or HA_KIND, 'format': 2, 'made': time.time(), 'from': node_name(),
            'version': __version__,
            'locked': base64.b64encode(salt + nonce + body + tag).decode('ascii')}


def bundle_open(bundle, passphrase, kinds=None):
    if isinstance(bundle, str):
        try:
            bundle = json.loads(bundle)
        except ValueError:
            raise ValueError('that is not a bundle made by otp --ha-bundle: it is not JSON')
    if not isinstance(bundle, dict) or bundle.get('kind') not in (kinds or (HA_KIND, 'opt-ha-join')):
        raise ValueError('that is not a bundle made by otp --ha-bundle')
    try:
        raw = base64.b64decode(bundle.get('locked') or '')
    except (ValueError, TypeError):
        raise ValueError('the bundle is damaged')
    if len(raw) < 16 + 16 + 32:
        raise ValueError('the bundle is damaged')
    salt, nonce, body, tag = raw[:16], raw[16:32], raw[32:-32], raw[-32:]
    key = _bundle_key(passphrase, salt)
    sign = hmac.new(key, b'sign', hashlib.sha256).digest()
    signed = salt + nonce + body
    if int(bundle.get('format') or 1) >= 2:
        signed = str(bundle.get('kind')).encode('utf-8') + b'\n' + signed
    if not hmac.compare_digest(tag, hmac.new(sign, signed, hashlib.sha256).digest()):
        raise ValueError('the passphrase is not the one the bundle was locked with')
    hide = hmac.new(key, b'hide', hashlib.sha256).digest()
    data = json.loads(bytes(a ^ b for a, b in zip(body, _seal_stream(hide, nonce, len(body))))
                      .decode('utf-8'))
    data['_from'] = bundle.get('from')
    data['_made'] = bundle.get('made')
    return data


def ha_passphrase():
    words = 'abcdefghijkmnopqrstuvwxyz23456789'
    return '-'.join(''.join(secrets.choice(words) for _ in range(5)) for _ in range(5))


def ha_checks(store):
    """What has to be true before a second node can join, each with its
    answer: the database, its address as the other node will see it, the
    key."""
    db = store.db
    host = str(CONFIG.get('db_host') or '')
    local = host in ('', 'localhost', '127.0.0.1', '::1')
    mode = CONFIG.get('ha_mode') or ''
    out = [
        {'key': 'engine', 'ok': db.engine == 'postgres',
         'says': 'the database is PostgreSQL' if db.engine == 'postgres' else
         'the database is %s: a cluster needs PostgreSQL, which both nodes open - move to it '
         'first (Settings → The database)' % ENGINE_WORDS.get(db.engine, db.engine)},
        {'key': 'key', 'ok': bool(sealing_key()),
         'says': 'the key that seals the tokens is there' if sealing_key() else
         'the key that seals the tokens is missing'},
    ]
    if mode == 'replicated' and db.engine == 'postgres':
        # Made two already (1.0.43): each node has its own PostgreSQL here,
        # and the other node never opens it - nothing to warn of.
        out.append({'key': 'address', 'ok': True,
                    'says': 'this node is one of two already: each has its own PostgreSQL '
                            'and they replicate to each other'})
        return out
    out += [
        {'key': 'address', 'ok': not local or db.engine != 'postgres',
         'warn': local and db.engine == 'postgres',
         'says': ('PostgreSQL is reached at %s, which the other node can use as well' % host)
         if not local else ('PostgreSQL is on this machine (%s): the other node reaches it at '
                            'this machine\'s address - it has to listen there and let the other '
                            'node in (otp --ha-setup does both, as root)' % (host or 'localhost'))},
    ]
    return out


def ha_bundle_data(store, peer_db_host='', with_tls=None):
    """What the second node needs and nothing else: how to open the
    database, the key that opens the tokens, and the name of the cluster."""
    if store.db.engine != 'postgres':
        raise ValueError('a cluster needs PostgreSQL: move to it first (Settings → The database)')
    key = sealing_key()
    if not key:
        raise ValueError('the key that seals the tokens is missing')
    db = {k: CONFIG.get(k) for k in DB_KEYS}
    host = str(db.get('db_host') or '')
    if peer_db_host:
        db['db_host'] = peer_db_host
    elif host in ('', 'localhost', '127.0.0.1', '::1'):
        db['db_host'] = node_address()
    data = {'db': db, 'key': key.hex(), 'cluster': CONFIG.get('site_name') or 'otp',
            'peer': {'name': node_name(), 'address': node_address()}}
    if with_tls:
        data['tls'] = with_tls
    return data


def ha_join(data, name='', even_if_data=False, by=''):
    """This node into the cluster: the database's address into config.json and
    the key beside it. The daemon starts again on it afterwards."""
    db = data.get('db') or {}
    if db.get('db_engine') != 'postgres':
        raise ValueError('the bundle does not name a PostgreSQL')
    # Every value checked as the settings are (1.0.57) before it goes into
    # config.json: they reach command lines, option files and pg_hba.conf.
    try:
        db = {k: check_setting(k, v) for k, v in db.items() if k in DB_KEYS}
        if name:
            name = check_setting('node_name', name)
    except BadSetting as e:
        raise ValueError('the bundle or the name will not do: %s' % e)
    key_hex = str(data.get('key') or '')
    if not re.match(r'^[0-9a-f]{64}\Z', key_hex):
        raise ValueError('the bundle holds no key')
    got = db_try(db)
    if not got.get('reached'):
        raise ValueError('the database in the bundle cannot be reached from here: %s'
                         % (got.get('trouble') or 'no answer'))
    now = sealing_key()
    if now and now.hex() != key_hex and not even_if_data:
        # This node has a key of its own: whatever it sealed would be lost.
        store = HA_STORE.get('store')
        mine = 0
        if store and store.db.engine == 'sqlite':
            try:
                mine = int(store.db.value('SELECT COUNT(*) FROM tokens') or 0)
            except Exception:                           # noqa: BLE001
                mine = 0
        if mine:
            raise ValueError('this node holds %d token(s) of its own, sealed with another key; '
                             'joining replaces both its database and its key. Say so to go on '
                             '(--discard-local, or tick it on the page)' % mine)
    if now and now.hex() != key_hex:
        backup = sealing_key_path().with_name('secrets.key.before-join')
        write_replacing(backup, now.hex() + '\n', 0o600)
    write_replacing(sealing_key_path(), key_hex + '\n', 0o600)
    changes = {k: db.get(k) for k in DB_KEYS if k in db}
    if name:
        changes['node_name'] = name
    write_file_settings(changes)
    return {'where': db_where(db), 'rows': got.get('rows'), 'peer': data.get('peer') or {},
            'message': 'this node joins the cluster: it starts again on %s' % db_where(db)}


# ---- the PostgreSQL side, as root on the machine it runs on ------------------------
def pg_local_admin(sql, secret=False):
    """A statement run as the postgres account on this machine (root only).
    The SQL goes in on standard input, never on the command line, where
    every process on the machine could read it; `secret` marks one that
    carries a password, which is then kept out of PostgreSQL's own log."""
    for runner in (['runuser', '-u', 'postgres', '--'], ['su', '-s', '/bin/sh', 'postgres', '-c']):
        if not shutil.which(runner[0]):
            continue
        if runner[0] == 'su':
            args = runner + ['psql -XAtq -v ON_ERROR_STOP=1 -f -']
        else:
            args = runner + ['psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', '-f', '-']
        got = subprocess.run(args, capture_output=True, text=True, timeout=30,
                             input=pg_script(sql, secret))
        if got.returncode == 0:
            return got.stdout.strip()
        raise ValueError(scrub_secret((got.stderr or got.stdout).strip()[:300]) or 'psql failed')
    raise ValueError('neither runuser nor su is here')


PG_QUIET = "SET log_statement = 'none'; SET log_min_error_statement = 'panic';\n"


def pg_script(sql, secret=False):
    """The statement as psql reads it from its standard input - for one with
    a password in it, after switching the logging of statements off for the
    session, so the password lands in no log."""
    return (PG_QUIET if secret else '') + str(sql).rstrip().rstrip(';') + ';\n'


def shlex_quote(s):
    import shlex
    return shlex.quote(s)


def peer_address(text):
    """The other node's address - one address, never a range: ValueError
    otherwise."""
    said = str(text or '').strip()
    if not said:
        raise ValueError('the other node\'s address is needed')
    try:
        return ipaddress.ip_address(said)
    except ValueError:
        raise ValueError('%s is not an address (one address, not a range or a name)' % said)


def peer_net(text):
    """That address as the one-address network pg_hba.conf takes."""
    a = peer_address(text)
    return '%s/%d' % (a, 32 if a.version == 4 else 128)


def pg_open_to(peer, db_name, db_user):
    """PostgreSQL on this machine listening beyond localhost and letting the
    other node's address in for this one database and account. Returns what
    was done, in words."""
    # Both go into pg_hba.conf as root: a name with a space or a new line
    # in config.json wrote a line of its own there (1.0.139).
    for what, v in (('db_name', db_name), ('db_user', db_user)):
        if not DB_IDENT.fullmatch(str(v or '')):
            raise ValueError('%s is letters, digits and _ only, starting with a letter' % what)
    done = []
    listen = pg_local_admin('SHOW listen_addresses')
    if listen not in ('*', '0.0.0.0') and '*' not in listen.split(','):
        pg_local_admin("ALTER SYSTEM SET listen_addresses = '*'")
        done.append("listen_addresses = '*' (was %s) - takes effect at the next start" % listen)
    hba = pg_local_admin('SHOW hba_file')
    line = 'host    %s    %s    %s    scram-sha-256' % (db_name, db_user, peer_net(peer))
    try:
        text = Path(hba).read_text()
    except OSError as e:
        raise ValueError('%s could not be read: %s' % (hba, e))
    if line not in text:
        # In front of whatever is there: pg_hba.conf is read top down, and a
        # "reject" or an "ident" line further up would win otherwise.
        Path(hba).write_text('# otp high availability: the other node (%s)\n%s\n%s'
                             % (datetime.now().strftime('%Y-%m-%d'), line, text))
        done.append('%s: %s' % (hba, line))
    pg_local_admin('SELECT pg_reload_conf()')
    return done


# ---------------------------------------------------------------------------
# Replicated: a PostgreSQL on each node, each replicating to the other (1.0.14)
# ---------------------------------------------------------------------------
# Each node opens only its own PostgreSQL, on this machine, and goes on alone
# when the other is gone. The two replicate both ways with PostgreSQL's own
# logical replication: a publication of every table on each (inserts, updates
# and deletes - never TRUNCATE, so that a node being rebuilt cannot empty the
# other), and on each a subscription to the other with `origin = none`, so
# that what came from the other is not sent back to it. PostgreSQL 16 or
# later on both.
#
# Rows made on both at once never collide: the numbering of every table goes
# up in twos, odd on node 1 and even on node 2.
#
# A node that was away comes back by itself: what it missed waited in its
# replication slot on the other (up to max_slot_wal_keep_size). A node that
# was lost - or reinstalled - is rebuilt from the living one: its tables
# emptied, every row copied over by the subscription, and the other node's
# subscription to it made afresh.

HA_PUB = 'otp_pub'
# Before 1.0.37 the program was called opt, and its replication objects so:
# a publication and subscriptions are renamed at the upgrade, a slot keeps
# its name until it is next made (a rebuild) - so both are looked for.
HA_PUB_OLD = 'opt_pub'
HA_SLOT_KEEP = '16GB'


def ha_sub_name(slot):
    """The subscription that brings node `slot`'s rows in (and its slot on
    node `slot`)."""
    return 'otp_from_%d' % int(slot)


def ha_sub_names(slot):
    return ['otp_from_%d' % int(slot), 'opt_from_%d' % int(slot)]


def ha_sub_here(db, slot):
    """The subscription for node `slot` as it is called in `db`."""
    for name in ha_sub_names(slot):
        if db.value(SUB_HERE_SQL, (name,)):
            return name
    return ha_sub_name(slot)


def pg_admin(sql, port=5432, db='postgres', secret=False):
    """A statement as the postgres account on this machine (root only). As
    pg_local_admin: the SQL on standard input, a `secret` one unlogged."""
    for runner in (['runuser', '-u', 'postgres', '--'], ['sudo', '-u', 'postgres']):
        if shutil.which(runner[0]):
            got = subprocess.run(runner + ['psql', '-XAtq', '-p', str(int(port)), '-d', db,
                                           '-v', 'ON_ERROR_STOP=1', '-f', '-'],
                                 capture_output=True, text=True, timeout=120,
                                 input=pg_script(sql, secret))
            if got.returncode == 0:
                return got.stdout.strip()
            raise ValueError(scrub_secret((got.stderr or got.stdout).strip()[:400])
                             or 'psql failed')
    raise ValueError('neither runuser nor sudo is on this machine')


def pg_local_running(port=5432):
    try:
        return pg_admin('SELECT 1', port) == '1'
    except Exception:                                   # noqa: BLE001
        return False


def pg_install_local(major, say):
    """PostgreSQL `major` on this machine, installed, initialised and running."""
    if shutil.which('dnf'):
        say('installing PostgreSQL %s (dnf)' % major)
        subprocess.run(['dnf', '-y', 'module', 'reset', 'postgresql'], capture_output=True)
        subprocess.run(['dnf', '-y', 'module', 'enable', 'postgresql:%s' % major],
                       capture_output=True)
        got = subprocess.run(['dnf', '-y', 'install', 'postgresql-server', 'postgresql',
                              'postgresql-contrib'], capture_output=True, text=True)
        if got.returncode != 0:
            raise ValueError('dnf could not install PostgreSQL %s: %s'
                             % (major, (got.stderr or got.stdout).strip()[-300:]))
        if not Path('/var/lib/pgsql/data/PG_VERSION').exists():
            subprocess.run(['postgresql-setup', '--initdb'], capture_output=True)
        subprocess.run(['systemctl', 'enable', '--now', 'postgresql'], capture_output=True)
    elif shutil.which('apt-get'):
        say('installing PostgreSQL %s (apt)' % major)
        got = subprocess.run(['apt-get', 'install', '-y', 'postgresql-%s' % major,
                              'postgresql-client-%s' % major], capture_output=True, text=True)
        if got.returncode != 0:
            got = subprocess.run(['apt-get', 'install', '-y', 'postgresql'],
                                 capture_output=True, text=True)
        if got.returncode != 0:
            raise ValueError('apt could not install PostgreSQL: %s'
                             % (got.stderr or got.stdout).strip()[-300:])
    else:
        raise ValueError('install PostgreSQL %s on this machine first' % major)
    for _ in range(30):
        if pg_local_running():
            return
        time.sleep(1)
    raise ValueError('PostgreSQL was installed but does not answer')


def pg_restart_local(port=5432):
    unit = tune_restart_unit()
    if unit:
        subprocess.run(['systemctl', 'restart', unit], capture_output=True)
    elif shutil.which('pg_lsclusters'):
        for line in subprocess.run(['pg_lsclusters', '-h'], capture_output=True,
                                   text=True).stdout.splitlines():
            f = line.split()
            if len(f) >= 3 and f[2] == str(port):
                subprocess.run(['pg_ctlcluster', f[0], f[1], 'restart'], capture_output=True)
    else:
        raise ValueError('PostgreSQL could not be restarted: no service of it was found')
    for _ in range(60):
        if pg_local_running(port):
            return
        time.sleep(1)
    raise ValueError('PostgreSQL did not come back after its restart')


def pg_prepare_local(port, peer, name, user, password, say):
    """PostgreSQL on this machine ready to replicate with `peer`: logical
    WAL, listening on the network, the peer let in, the account able to
    replicate and to subscribe, the database there. True when it has to be
    restarted for it."""
    major = int(pg_admin('SHOW server_version_num', port)) // 10000
    if major < 16:
        raise ValueError('PostgreSQL %d is here; replicating both ways needs 16 or later '
                         '(dnf module enable postgresql:16, then upgrade it)' % major)
    restart = False
    for key, want in (('wal_level', 'logical'), ('listen_addresses', '*'),
                      ('max_slot_wal_keep_size', HA_SLOT_KEEP)):
        now = pg_admin('SHOW %s' % key, port)
        if key == 'max_slot_wal_keep_size' and now not in ('-1',) and now.upper() == want:
            continue
        if now != want:
            pg_admin("ALTER SYSTEM SET %s = '%s'" % (key, want), port)
            say('%s = %s (was %s)' % (key, want, now))
            if key != 'max_slot_wal_keep_size':
                restart = True
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}', user) or \
            not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}', name):
        raise ValueError('the database and its account are letters, digits and _')
    lit = "'%s'" % str(password).replace("'", "''")
    if pg_admin("SELECT 1 FROM pg_roles WHERE rolname = '%s'" % user, port) != '1':
        pg_admin('CREATE ROLE %s LOGIN PASSWORD %s' % (user, lit), port, secret=True)
        say('the account %s was made' % user)
    else:
        pg_admin('ALTER ROLE %s LOGIN PASSWORD %s' % (user, lit), port, secret=True)
    pg_admin('ALTER ROLE %s REPLICATION' % user, port)
    pg_admin('GRANT pg_create_subscription TO %s' % user, port)
    if pg_admin("SELECT 1 FROM pg_database WHERE datname = '%s'" % name, port) != '1':
        # UTF-8 whatever the cluster was made with: one made under LANG=C is
        # SQL_ASCII, and every name with an accent would come back unreadable.
        pg_admin("CREATE DATABASE %s OWNER %s ENCODING 'UTF8' TEMPLATE template0 "
                 "LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8'" % (name, user), port)
        say('the database %s was made' % name)
    pg_admin('GRANT CREATE ON DATABASE %s TO %s' % (name, user), port)
    hba = pg_admin('SHOW hba_file', port)
    text = Path(hba).read_text()
    added = []
    for who in sorted(set(([peer] if peer else []) + ['127.0.0.1'])):
        line = 'host    %s    %s    %s    scram-sha-256' % (name, user, peer_net(who))
        # Taken over TLS only already (1.0.104): no plain line put back in front.
        if line not in text and ('hostssl' + line[4:]) not in text:
            added.append(line)
    if added:
        # In front of whatever is there: pg_hba.conf is read top down, and a
        # "reject" or an "ident" line further up would win otherwise.
        Path(hba).write_text('# otp high availability (%s)\n%s\n%s'
                             % (datetime.now().strftime('%Y-%m-%d'), '\n'.join(added), text))
        say('%s: %s' % (hba, '; '.join(added)))
    pg_admin('SELECT pg_reload_conf()', port)
    return restart, major


def pg_publication(port, name):
    if pg_admin("SELECT 1 FROM pg_publication WHERE pubname = '%s'" % HA_PUB_OLD, port, name) == '1':
        pg_admin('ALTER PUBLICATION %s RENAME TO %s' % (HA_PUB_OLD, HA_PUB), port, name)
    if pg_admin("SELECT 1 FROM pg_publication WHERE pubname = '%s'" % HA_PUB, port, name) != '1':
        pg_admin("CREATE PUBLICATION %s FOR ALL TABLES WITH (publish = 'insert, update, delete')"
                 % HA_PUB, port, name)


def ha_conninfo(host, port, name, user, password):
    def q(v):
        return "'%s'" % str(v).replace('\\', '\\\\').replace("'", "\\'")
    tls = ''
    mode, ca = ha_link_tls()
    if mode:
        # The other node's link encrypted as the database's own is (1.0.33),
        # or as its own setting says (1.0.104).
        tls = ' sslmode=%s' % q(mode)
        if ca:
            tls += ' sslrootcert=%s' % q(ca)
    return 'host=%s port=%d dbname=%s user=%s password=%s connect_timeout=10%s' % (
        q(host), int(port), q(name), q(user), q(password), tls)


def ha_drop_sub(db, sub):
    """A subscription taken away without asking the other side for its slot
    (which may be gone with a lost node) - under its name now or before."""
    names = ha_sub_names(sub.rsplit('_', 1)[1]) if sub[:9] in ('otp_from_', 'opt_from_') \
        else [sub]
    for one in names:
        if db.value(SUB_HERE_SQL, (one,)):
            db.run('ALTER SUBSCRIPTION %s DISABLE' % one)
            db.run('ALTER SUBSCRIPTION %s SET (slot_name = NONE)' % one)
            db.run('DROP SUBSCRIPTION %s' % one)


def ha_drop_slot(db, slot_name):
    if slot_name[:9] in ('otp_from_', 'opt_from_'):
        gone = False
        for one in ha_sub_names(slot_name.rsplit('_', 1)[1]):
            gone = _ha_drop_slot(db, one) or gone
        return gone
    return _ha_drop_slot(db, slot_name)


def _ha_drop_slot(db, slot_name):
    # This database's only (1.0.170): the catalog is the server's, and a slot
    # of the same name may be another database's - in use by it.
    got = db.row('SELECT active, active_pid FROM pg_replication_slots WHERE slot_name = ? '
                 'AND database = current_database()', (slot_name,))
    if not got:
        return False
    if got.get('active') and got.get('active_pid'):
        db.value('SELECT pg_terminate_backend(?)', (int(got['active_pid']),))
        time.sleep(1)
    db.value('SELECT pg_drop_replication_slot(?)', (slot_name,))
    return True


def ha_sequences(db, slot):
    """Every table numbered in twos: odd on node 1, even on node 2."""
    slot = int(slot)
    for table in TABLES:
        if table in ('meta', 'settings'):
            continue                    # keyed by name, not numbered
        seq = db.value("SELECT pg_get_serial_sequence(?, 'id')", (table,))
        if not seq:
            continue
        top = int(db.value('SELECT COALESCE(MAX(id), 0) FROM %s' % table) or 0)
        start = top + 1
        while start % 2 != slot % 2:
            start += 1
        db.run('ALTER SEQUENCE %s INCREMENT BY 2' % seq)
        # The next nextval() is `start`.
        db.value('SELECT setval(?, ?, false)', (seq, start))


def ha_sequences_check(db, slot):
    """Every hour, and once at start (1.0.59): a table whose next number is
    not above every row in it - rows put back on the other node, a database
    restored from an older snapshot - would hand out a number the other
    node already has, and replication stops on it. Moved past them, on this
    node's side of odd and even."""
    fixed = []
    for table in TABLES:
        if table in ('meta', 'settings'):
            continue
        seq = db.value("SELECT pg_get_serial_sequence(?, 'id')", (table,))
        if not seq:
            continue
        st = db.row('SELECT last_value, is_called FROM %s' % seq)
        inc = int(db.value('SELECT increment_by FROM pg_sequences WHERE '
                           "schemaname || '.' || sequencename = ? OR sequencename = ?",
                           (seq, seq.split('.')[-1])) or 1)
        nxt = int(st['last_value']) + (inc if st['is_called'] else 0)
        top = int(db.value('SELECT COALESCE(MAX(id), 0) FROM %s' % table) or 0)
        if nxt > top and inc == 2 and nxt % 2 == int(slot) % 2:
            continue
        if inc == 2 and nxt % 2 == int(slot) % 2:
            # (1.0.61) Only behind the other node's rows - the usual thing where one
            # node takes more of the traffic, and harmless: moved past them
            # quietly, so no number of its own can ever meet a row put back.
            start = top + 1 + ((int(slot) - top - 1) % 2)
            db.value('SELECT setval(?, ?, false)', (seq, start))
            continue
        start = top + 1
        while start % 2 != int(slot) % 2:
            start += 1
        db.run('ALTER SEQUENCE %s INCREMENT BY 2' % seq)
        db.value('SELECT setval(?, ?, false)', (seq, max(start, nxt if nxt % 2 == int(slot) % 2
                                                      else start)))
        fixed.append(table)
    if fixed:
        log('the numbering of %s was behind the rows in it, or on the other node\'s side: '
            'moved on' % ', '.join(fixed), 'warn')
    return fixed


def ha_wait_copied(db, sub, say, seconds=3600):
    t0 = time.time()
    while time.time() - t0 < seconds:
        left = db.rows("SELECT c.relname AS t, r.srsubstate AS s FROM pg_subscription_rel r "
                       "JOIN pg_subscription s ON s.oid = r.srsubid "
                       "JOIN pg_class c ON c.oid = r.srrelid WHERE s.subname = ? "
                       "AND r.srsubstate <> 'r'", (sub,))
        if not left and db.value('SELECT COUNT(*) FROM pg_subscription_rel r JOIN '
                                 'pg_subscription s ON s.oid = r.srsubid WHERE s.subname = ?',
                                 (sub,)):
            return True
        say('copying: %s still to come' % ', '.join(sorted(x['t'] for x in left)[:6]))
        time.sleep(2)
    raise ValueError('the copy from the other node did not finish in %d s' % seconds)


def ha_subscribe(db, sub, conninfo, copy_data):
    """A subscription made on `db`. The statement carries the password of
    the account in its conninfo, so it is kept out of PostgreSQL's log for
    the session, and out of any error that comes back."""
    # Tried from here first (1.0.44): the SETs below need a superuser, which
    # the otp account is not, so a CREATE SUBSCRIPTION that fails - the
    # other node unreachable, a wrong password - would be written to
    # PostgreSQL's log with the password in it. What fails here is never
    # sent.
    try:
        import psycopg2
        probe = psycopg2.connect(conninfo + ' connect_timeout=10')
        probe.close()
    except ImportError:
        pass
    except Exception as e:                              # noqa: BLE001
        raise ValueError('the other node\'s database cannot be reached from here, so the '
                         'subscription %s was not made: %s'
                         % (sub, scrub_secret(str(e).split('\n')[0][:300])))
    for quiet in ("SET log_statement = 'none'", "SET log_min_error_statement = 'panic'"):
        try:
            db.run(quiet)
        except Exception:                               # noqa: BLE001
            pass                                        # not a superuser: logged as usual
    try:
        db.run(RawSql("CREATE SUBSCRIPTION %s CONNECTION '%s' PUBLICATION %s WITH (copy_data = %s, "
                      "origin = none)" % (sub, conninfo.replace("'", "''"), HA_PUB,
                                          'true' if copy_data else 'false')))
    except Exception as e:                              # noqa: BLE001
        raise ValueError('the subscription %s could not be made: %s'
                         % (sub, scrub_secret(str(e).split('\n')[0][:300])))
    finally:
        for back in ('RESET log_statement', 'RESET log_min_error_statement'):
            try:
                db.run(back)
            except Exception:                           # noqa: BLE001
                pass


HA_REBUILD_FAILED_WHY = ('a rebuild from the other node failed half way - its tables are '
                         'not whole: rebuild it again (Settings → High availability)')


def ha_rebuild(local, remote, *args):
    """Never two at once (1.0.59): both nodes rebuilding from each other
    emptied both. The same lock is taken in both databases - the other
    node's rebuild holds it in its own and in this one."""
    held = []
    try:
        for db in (local, remote):
            if not db.value('SELECT pg_try_advisory_lock(?)', (HA_REBUILD_LOCK,)):
                raise ValueError('a rebuild is running already (on this node or the other one)')
            held.append(db)
        return _ha_rebuild(local, remote, *args)
    finally:
        for db in held:
            try:
                db.value('SELECT pg_advisory_unlock(?)', (HA_REBUILD_LOCK,))
            except Exception:                           # noqa: BLE001
                pass


def _ha_rebuild(local, remote, my_slot, peer_slot, my_host, my_port, peer_host, peer_port,
                name, user, password, say):
    """This node rebuilt from the other: both subscriptions made afresh, this
    node's tables emptied and every row copied over. What this node held is
    replaced by what the other holds."""
    mine_on_peer = ha_sub_name(my_slot)       # on the peer: brings my rows to it
    theirs_here = ha_sub_name(peer_slot)      # here: brings the peer's rows to me
    say('the other node stops taking rows from this one')
    ha_drop_sub(remote, mine_on_peer)
    ha_drop_slot(local, mine_on_peer)
    say('this node stops taking rows from the other')
    ha_drop_sub(local, theirs_here)
    ha_drop_slot(remote, theirs_here)
    say('this node\'s tables emptied')
    local.make_tables()
    # Nothing written here while the rows come over (1.0.44): the heartbeat
    # and the job's own progress wrote rows the copy then met again, and it
    # stopped on a duplicate key for good.
    HA_REBUILDER[0] = threading.get_ident()    # before the flag (1.0.59)
    HA_REBUILDING.set()
    done = False
    try:
        local.run('TRUNCATE %s RESTART IDENTITY' % ', '.join(TABLES))
        say('every row copied from the other node')
        ha_subscribe(local, theirs_here, ha_conninfo(peer_host, peer_port, name, user, password),
                     copy_data=True)
        ha_wait_copied(local, theirs_here, say)
        ha_sequences(local, my_slot)
        # The other node's subscription - and with it the point it starts
        # from - made before this node writes anything again (1.0.57): what
        # was written in between never went over.
        say('the other node takes this one\'s rows from now on')
        ha_subscribe(remote, mine_on_peer, ha_conninfo(my_host, my_port, name, user, password),
                     copy_data=False)
        done = True
    finally:
        # Odd or even again whatever happened (1.0.57): RESTART IDENTITY
        # left them at 1 with the other node's numbering.
        try:
            ha_sequences(local, my_slot)
        except Exception as e:                          # noqa: BLE001
            log('the numbering could not be set again: %s' % e, 'warn')
        HA_REBUILDER[0] = None
        HA_REBUILDING.clear()
        # Failed after its tables were emptied (1.0.94): the node stays out of
        # service, not back answering every person "no such token" with
        # nothing replicating - until a rebuild goes through.
        store = HA_STORE.get('store')
        if store is not None:
            try:
                row = maintenance_row(store)
                if not done:
                    maintenance_set(store, True, HA_REBUILD_FAILED_WHY, 'the rebuild')
                elif row.get('on') and row.get('why') == HA_REBUILD_FAILED_WHY:
                    maintenance_set(store, False, '', 'the rebuild')
            except Exception as e:                      # noqa: BLE001
                log('maintenance after the rebuild could not be written: %s' % e, 'error')
    rows = sum(int(local.value('SELECT COUNT(*) FROM %s' % t) or 0) for t in TABLES)
    return {'rows': rows}


def ha_repl_state(store):
    """Both directions, as this node's PostgreSQL sees them."""
    db = store.db
    out = {'mode': CONFIG.get('ha_mode') or '', 'slot': CONFIG.get('ha_slot') or 0,
           'peer': CONFIG.get('ha_peer') or '', 'incoming': [], 'outgoing': []}
    if out['mode'] != 'replicated' or db.engine != 'postgres':
        return out
    try:
        for r in db.rows(
                'SELECT s.subname AS name, s.subenabled AS enabled, st.pid AS pid, '
                'EXTRACT(EPOCH FROM st.last_msg_receipt_time) AS last_msg, '
                'EXTRACT(EPOCH FROM st.latest_end_time) AS latest_end, '
                'COALESCE(ss.apply_error_count, 0) AS apply_errors, '
                'COALESCE(ss.sync_error_count, 0) AS sync_errors '
                'FROM pg_subscription s LEFT JOIN pg_stat_subscription st '
                'ON st.subid = s.oid AND st.relid IS NULL '
                'LEFT JOIN pg_stat_subscription_stats ss ON ss.subid = s.oid '
                # Only this database's (1.0.57): the catalog is the server's.
                'WHERE s.subdbid = (SELECT oid FROM pg_database WHERE datname = '
                'current_database())'):
            r['running'] = bool(r.get('pid'))
            out['incoming'].append(r)
        for r in db.rows(
                "SELECT slot_name AS name, active, wal_status, "
                "pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS behind "
                "FROM pg_replication_slots WHERE slot_name LIKE 'o__!_from!_%' ESCAPE '!' "
                "AND database = current_database()"):
            r['behind'] = int(float(r.get('behind') or 0))
            out['outgoing'].append(r)
    except Exception as e:                              # noqa: BLE001
        out['trouble'] = str(e).split('\n')[0][:300]
    healthy = bool(out['incoming']) and all(x['enabled'] and x['running'] for x in
                                            out['incoming']) and bool(out['outgoing']) and \
        all(x['wal_status'] not in ('lost',) for x in out['outgoing'])
    out['healthy'] = healthy
    out['lost'] = any(x.get('wal_status') == 'lost' for x in out['outgoing'])
    return out


def ha_peer_columns():
    """Columns of a later version added to the other node's tables too."""
    try:
        far = ha_peer_db()
    except Exception as e:                              # noqa: BLE001
        log('the other node\'s database could not be reached to add new columns: %s'
            % str(e).split('\n')[0][:200], 'warn')
        return
    try:
        far.add_missing_columns()
    except Exception as e:                              # noqa: BLE001
        log('new columns could not be added on the other node: %s' % e, 'warn')
    finally:
        try:
            far.close()
        except Exception:                               # noqa: BLE001
            pass


# ---- used once, on either node (1.0.101) -------------------------------------
# A code's time step, a recovery code, an answered question: each is written
# as a row of its own in token_once, by this node under its own number, and
# never changed - so replication, which writes whole rows, cannot write an
# older copy over it. And with two replicating databases, a node that takes
# one also looks in the other node's database for that node's row, after
# writing its own: of two nodes asked for the same code at the same moment,
# at least one sees the other's row - so it is never let in twice. (One may
# refuse it when both see each other; the next code then goes through.)
ONCE_PEER = {'db': None, 'down_until': 0.0, 'said': 0.0}
ONCE_PEER_LOCK = threading.Lock()
ONCE_KEEP_S = {'step': 3 * 86400, 'chal': 3 * 86400, 'scratch': 800 * 86400}


def once_node():
    return int(CONFIG.get('ha_slot') or 1) if CONFIG.get('ha_mode') == 'replicated' else 0


def once_key(kind, name, value):
    h = hashlib.sha256(('%s\n%s' % (norm_name(name), value)).encode('utf-8')).hexdigest()
    return '%s:%s' % (kind, h[:48])


def _once_peer_has(k, me):
    """Whether the other node's database has the other node's row for `k`:
    True, False, or None when it cannot be asked just now. Asked on a
    connection of its own with a 2 s limit, and waited for 2.5 s at most
    (1.0.101): a peer that drops packets without a word must not hold every
    sign-in that was let in."""
    with ONCE_PEER_LOCK:
        if ONCE_PEER['down_until'] > time.time():
            return None
        db = ONCE_PEER['db']
    got = {}

    def ask():
        nonlocal db
        try:
            if db is None:
                db = db_open(ha_peer_conf(timeout=2), statement_s=2)
                with ONCE_PEER_LOCK:
                    if ONCE_PEER['db'] is None:
                        ONCE_PEER['db'] = db
            got['v'] = bool(db.value('SELECT 1 FROM token_once WHERE k = ? AND node <> ?',
                                     (k, me)))
        except Exception as e:                          # noqa: BLE001
            got['e'] = e
    t = threading.Thread(target=ask, name='once-peer', daemon=True)
    t.start()
    t.join(2.5)
    if 'v' in got:
        return got['v']
    e = got.get('e') or TimeoutError('no answer within 2.5 s')
    with ONCE_PEER_LOCK:
        was, ONCE_PEER['db'] = ONCE_PEER['db'], None
        ONCE_PEER['down_until'] = time.time() + 20
        say = ONCE_PEER['said'] < time.time() - 300
        if say:
            ONCE_PEER['said'] = time.time()
    if was is not None and not t.is_alive():
        try:
            was.close()
        except Exception:                               # noqa: BLE001
            pass
    if say:
        log('the other node\'s database cannot be asked whether a code was used there '
            '(%s): codes are checked against this node\'s rows alone until it can'
            % str(e).split('\n')[0][:200], 'warn')
    return None


def once_take(store, kind, name, value):
    """True if this is the first use of it anywhere; False if it was used
    before, here or on the other node. A database error here raises: the
    request then goes unanswered, never let in."""
    k = once_key(kind, name, value)
    me = once_node()
    db = store.db
    if db.engine == 'mariadb':
        sql = 'INSERT IGNORE INTO token_once (k, node, ts) VALUES (?, ?, ?)'
    elif db.engine == 'sqlite':
        sql = 'INSERT OR IGNORE INTO token_once (k, node, ts) VALUES (?, ?, ?)'
    else:
        sql = 'INSERT INTO token_once (k, node, ts) VALUES (?, ?, ?) ON CONFLICT DO NOTHING'
    if not db.run(sql, (k, me, time.time())):
        return False                    # this node took it already
    if db.value('SELECT 1 FROM token_once WHERE k = ? AND node <> ?', (k, me)):
        return False                    # the other node took it, and it came over
    if me and CONFIG.get('ha_mode') == 'replicated' and CONFIG.get('ha_peer'):
        if _once_peer_has(k, me):
            return False                # the other node took it, not over yet
    return True


def once_tidy(store):
    """Rows no longer needed: a time step or a question long past."""
    t = time.time()
    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'scratchguard:%'"):
        try:
            last = max([float(x) for x in json.loads(r['v'] or '[]')] or [0])
        except (ValueError, TypeError):
            last = 0
        if t - last > 86400:
            store.db.run('DELETE FROM meta WHERE k = ? AND v = ?', (r['k'], r['v']))
    for kind, keep in ONCE_KEEP_S.items():
        store.db.run('DELETE FROM token_once WHERE substr(k, 1, ?) = ? AND ts < ?',
                     (len(kind) + 1, kind + ':', t - keep))


def ha_peer_db():
    return db_open(ha_peer_conf())


def ha_control(store, act, by=''):
    """Replication worked by hand: paused, resumed, switched off, refreshed.
    `in` is what this node takes from the other (its own subscription);
    `out` is what the other takes from this one (the other's subscription,
    reached over its PostgreSQL). (1.0.14)"""
    if CONFIG.get('ha_mode') != 'replicated':
        raise ValueError('this node does not replicate')
    slot = int(CONFIG.get('ha_slot') or 1)
    peer_slot = 3 - slot
    here = store.db
    sub_in = ha_sub_here(here, peer_slot)
    said = []

    def on_peer(fn):
        try:
            far = ha_peer_db()
        except Exception as e:                          # noqa: BLE001
            raise ValueError('the other node\'s PostgreSQL cannot be reached: %s'
                             % str(e).split('\n')[0][:200])
        try:
            return fn(far)
        finally:
            far.close()

    def has(db, sub):
        return bool(db.value(SUB_HERE_SQL, (sub,)))

    if act in ('pause_in', 'pause'):
        if has(here, sub_in):
            here.run('ALTER SUBSCRIPTION %s DISABLE' % sub_in)
            said.append('this node takes nothing from the other for now')
    if act in ('pause_out', 'pause'):
        def p(far):
            sub_out = ha_sub_here(far, slot)
            if has(far, sub_out):
                far.run('ALTER SUBSCRIPTION %s DISABLE' % sub_out)
                said.append('the other node takes nothing from this one for now')
        on_peer(p)
    if act in ('resume_in', 'resume'):
        if has(here, sub_in):
            here.run('ALTER SUBSCRIPTION %s ENABLE' % sub_in)
            said.append('this node takes the other\'s rows again, from where it stopped')
    if act in ('resume_out', 'resume'):
        def r(far):
            sub_out = ha_sub_here(far, slot)
            if has(far, sub_out):
                far.run('ALTER SUBSCRIPTION %s ENABLE' % sub_out)
                said.append('the other node takes this one\'s rows again, from where it '
                            'stopped')
        on_peer(r)
    if act == 'refresh':
        if has(here, sub_in):
            here.run('ALTER SUBSCRIPTION %s REFRESH PUBLICATION WITH (copy_data = false)'
                     % sub_in)
        said.append('the list of tables taken from the other was read again')
    if act == 'stop':
        # Both directions taken away; both nodes go on alone, each with what
        # it has. Joining them again is a rebuild of one from the other.
        ha_drop_sub(here, sub_in)
        try:
            on_peer(lambda far: (ha_drop_sub(far, ha_sub_name(slot)), ha_drop_slot(far, sub_in)))
        except ValueError as e:
            said.append('the other node could not be reached (%s): take its subscription '
                        'away there with otp --ha-stop' % e)
        ha_drop_slot(here, ha_sub_name(slot))
        said.append('replication is off: each node goes on alone with what it has')
    if not said:
        raise ValueError('nothing to do: %s' % act)
    store.add_event('settings', '%s: replication - %s' % (by or 'command line', '; '.join(said)),
                    'warn', who=by or 'command line')
    return {'message': '; '.join(said)}


def ha_resync_job(store, by):
    """This node rebuilt from the other, as a job the pages can follow."""
    if CONFIG.get('ha_mode') != 'replicated':
        raise ValueError('this node does not replicate')

    def work(progress):
        steps = []

        def say(t):
            steps.append(t)
            progress(len(steps), 8, t)
        progress(0, 8, 'making a copy of what is here first')
        copy = make_backup(store, 'before rebuilding from the other node, by %s' % by)
        remote = ha_peer_db()
        try:
            got = ha_rebuild(store.db, remote, int(CONFIG.get('ha_slot') or 2),
                             3 - int(CONFIG.get('ha_slot') or 2),
                             CONFIG.get('ha_address') or node_address(),
                             int(CONFIG.get('db_port') or 5432), CONFIG.get('ha_peer'),
                             int(CONFIG.get('ha_peer_port') or 5432), CONFIG.get('db_name'),
                             CONFIG.get('db_user'), CONFIG.get('db_password'), say)
        finally:
            remote.close()
        store._clients = store._realms = None
        store.set_meta('conf_serial', '%.6f:%s' % (time.time(), node_name()))
        store.add_event('settings', '%s rebuilt this node from the other: %d row(s); what it '
                        'held is in %s' % (by, got['rows'], copy.name), 'warn', who=by)
        progress(8, 8, 'done')
        return {'rows': got['rows'], 'copy': copy.name, 'where': CONFIG.get('ha_peer')}
    return db_job('rebuilding this node from the other', work)


def bytes_words(n):
    n = float(n or 0)
    for unit in ('B', 'kB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            return ('%d %s' % (n, unit)) if unit == 'B' else ('%.1f %s' % (n, unit))
        n /= 1024.0
