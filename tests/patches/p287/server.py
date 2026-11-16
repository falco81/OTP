# 1.0.287: the bug hunt's fixes in the daemon - python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


# R1/3.2: a replicated node's nightly dump could never be put back there (a dump makes tables anew, which
# replication does not carry - refused, "put a copy back instead"), and no copy was made by itself: the
# night's backup of a cluster node is a portable copy, put back row by row.
edit('85_dbfiles.py', [(
"""    info = dump_info(engine)
    kind = engine if info['ready'] else 'copy'""",
"""    info = dump_info(engine)
    kind = engine if info['ready'] else 'copy'
    if label == 'daily' and CONFIG.get('ha_mode') == 'replicated' and engine in ('postgres', 'mariadb'):
        kind = 'copy'           # 1.0.287: the night's - the one a replicated node can put back"""),
# R1/3.3: a copy put back straight from a request (the page's upload, a kept one, otp --restore) was no
# job: two at once on one node (the first to end said "done" while the other still loaded), or one on each
# node of a cluster (the same rows inserted on both stopped replication both ways). One at a time on this
# node, said to the other node while it runs - as the jobs are.
(
"""    other = db_job_elsewhere()
    if other:
        # One at a time on the cluster (1.0.211).
        raise ValueError('%s is going on on %s - wait for it to end'
                         % (other.get('what') or 'a job on the database', other['node']))
    if CONFIG.get('ha_mode') == 'replicated' and kind in ('postgres', 'mariadb'):""",
"""    other = db_job_elsewhere()
    if other:
        # One at a time on the cluster (1.0.211).
        raise ValueError('%s is going on on %s - wait for it to end'
                         % (other.get('what') or 'a job on the database', other['node']))
    # Inside a job of its own (an upload, a remote backup put back) the job says it to the other node.
    in_job = bool(DB_JOB.get('running')) and threading.current_thread().name == 'db-job'
    if not in_job and DB_JOB.get('running'):
        raise ValueError('%s is going on - wait for it to end' % (DB_JOB.get('what') or 'a job on the database'))
    if not RESTORE_ONE.acquire(blocking=False):
        raise ValueError('a database is being put back already - wait for it to end')
    beat = threading.Event()
    try:
        if not in_job:
            said = {'running': True, 'what': 'putting a database back', 'began': time.time()}
            job_publish(said)

            def _beat():
                while not beat.wait(30):
                    job_publish(said)
            threading.Thread(target=_beat, name='restore-beat', daemon=True).start()
        return _db_file_restore_one(store, path, by, key_file, from_name, need_admin, said_kind=kind)
    finally:
        beat.set()
        if not in_job:
            job_publish({'running': False, 'what': 'putting a database back', 'ended': time.time()})
        RESTORE_ONE.release()


RESTORE_ONE = threading.Lock()


def _db_file_restore_one(store, path, by, key_file, from_name, need_admin, said_kind):
    kind = said_kind
    if CONFIG.get('ha_mode') == 'replicated' and kind in ('postgres', 'mariadb'):""")])

# R1/3.4: a kept copy downloaded "with its key" while no .key lay beside it carried the key in use now -
# which need not open it; put back on a server, that key replaced the one there and every token was refused.
edit('90_api.py', [(
"""            if keyf.is_file() and sealing_key() and \\
                    keyf.read_text().strip() != sealing_key().hex():""",
"""            if not keyf.is_file():
                raise ApiError(409, 'no .key lies beside %s - which key opens it is not known here: '
                                    'download it without the key' % src.name)
            if keyf.is_file() and sealing_key() and \\
                    keyf.read_text().strip() != sealing_key().hex():""")])
# R1/4.1: an address of these settings with an IPv6 scope id (fe80::1%ens192) was taken - and root's helper
# refused it inside the firewall rules and nginx's real_ip lines, with it the whole request, again and again:
# no certificate, VIP, access list or firewall change reached the node. Refused when set; one kept from before
# left out of what root is asked.
s = open(P + '00_head.py').read()
a = """            try:
                ipaddress.ip_network(one, strict=False)
            except ValueError:"""
assert s.count(a) == 5, s.count(a)
s = s.replace(a, """            try:
                plain_net(one)                  # no scope id (1.0.287): root's helper refuses one
            except ValueError:""")
open(P + '00_head.py', 'w').write(s)
s = open(P + '88w_web.py').read()
a = """                    nets.append(str(ipaddress.ip_network(w, strict=False)))"""
assert s.count(a) == 1
s = s.replace(a, """                    nets.append(str(plain_net(w)))     # no scope id (1.0.287)""")
a = """                nets.append(str(ipaddress.ip_network(w, strict=False)))"""
assert s.count(a) == 1
s = s.replace(a, """                nets.append(str(plain_net(w)))         # no scope id (1.0.287)""")
a = """        nets = [w for w in re.split(r'[\\s,;]+', str(CONFIG.get('snmp_from') or '')) if w]
        port = str(int(CONFIG.get('snmp_port') or 161))"""
assert s.count(a) == 1, 'snmp fw'
s = s.replace(a, """        nets = []
        for w in re.split(r'[\\s,;]+', str(CONFIG.get('snmp_from') or '')):
            try:
                nets.append(str(plain_net(w))) if w else None     # no scope id (1.0.287)
            except ValueError:
                continue
        if not nets and str(CONFIG.get('snmp_from') or '').strip():
            nets = ['127.0.0.1/32']     # every one left out: closed, never opened to everybody
        port = str(int(CONFIG.get('snmp_port') or 161))""")
open(P + '88w_web.py', 'w').write(s)
edit('90o_sso.py', [(
"""            out.append(ipaddress.ip_network(w, strict=False))""",
"""            out.append(plain_net(w))      # no scope id (1.0.287)""")])
edit('87m_ntp.py', [(
"""            allow.append(str(ipaddress.ip_network(a, strict=False)))""",
"""            allow.append(str(plain_net(a)))   # no scope id (1.0.287): root refused it""")])
# R1/4.4: a change on trial that cut the node off from a shared database came back only after the hour a
# reboot is given to happen (NET_REBOOT_GIVE_UP_S) plus the trial - not the minutes the page promised. Once
# the machine has started again after the change, its time runs from that start.
edit('87n_net.py', [(
"""        write_replacing(NET_LOCAL_TRIAL, json.dumps({
            'id': job.get('id'), 'snap': job['snap'],
            'until': time.time() + NET_REBOOT_GIVE_UP_S + 60 * int(job.get('trial_min') or 0) + 300}),
            0o600)""",
"""        write_replacing(NET_LOCAL_TRIAL, json.dumps({
            'id': job.get('id'), 'snap': job['snap'], 'set': time.time(),
            'trial_min': int(job.get('trial_min') or 0),
            'until': time.time() + NET_REBOOT_GIVE_UP_S + 60 * int(job.get('trial_min') or 0) + 300}),
            0o600)"""), (
"""    if time.time() < fnum(t.get('until')) or time.time() - fnum(t.get('asked')) < 600:
        return""",
"""    until = fnum(t.get('until'))
    try:
        started = float(boot_time() or 0)
    except Exception:                                   # noqa: BLE001
        started = 0.0
    if t.get('set') and started > fnum(t.get('set')):
        # Started again since the change (1.0.287): the trial's minutes from that start.
        until = min(until, started + 60 * int(t.get('trial_min') or 0) + 300)
    if time.time() < until or time.time() - fnum(t.get('asked')) < 600:
        return""")])
# R1/1.1: the ten-minute look at a directory administrator asked a directory whose row was not as otp wrote
# it (the guard) - a sign-in refuses that one; the role it answered was written and signed.
# R1/1.3: a directory or a revocation server that cannot be reached counted as a wrong password - after it was
# back, the name (or the office's whole address) was locked out for the waiting time.
edit('90_api.py', [(
"""        ad = self.d.dirs.get(str(CONFIG.get('admin_directory') or '').lower())
        if not ad:
            self.end_all(name, 'the directory administrators sign in against is gone')""",
"""        ad = self.d.dirs.get(str(CONFIG.get('admin_directory') or '').lower())
        if not ad:
            self.end_all(name, 'the directory administrators sign in against is gone')
        if not dbguard_directory_ok(self.store.db, ad.name):
            # Not as otp wrote it (1.0.287): not asked - and signed out, as a sign-in is refused.
            self.end_all(name, 'the directory %s is not as otp wrote it' % ad.name)"""), (
"""        try:
            ok = admin_from_directory(h, name, password)
        except ApiError as e:
            h.failed(key)""",
"""        try:
            ok = admin_from_directory(h, name, password)
        except ApiError as e:
            if e.status < 500:          # the directory not reached is no wrong password (1.0.287)
                h.failed(key)"""),
# R1/1.4: the columns switched on or off wrote back the whole of the sign-in's data as read - a card's mark
# written meanwhile (out, found) was put back as it was.
(
"""    data = row['data']
    if on:
        data['cols_edit'] = 1
    else:
        data.pop('cols_edit', None)
    store.session_set_data(row['id'], data)
    return bool(on)""",
"""    store.session_merge(row['id'], {'cols_edit': 1 if on else None})     # that key alone (1.0.287)
    return bool(on)""")])
for f in ('90c_certlogin_api.py', '90g_kerberos_api.py'):
    edit(f, [(
"""    except ApiError:
        h.failed(key)
        raise""",
"""    except ApiError as e:
        if e.status < 500:              # the directory not reached is no wrong try (1.0.287)
            h.failed(key)
        raise""")])
edit('90c_certlogin_api.py', [(
"""    except CertError as e:
        h.failed(key)
        h.store.add_event('sign-ins', 'a sign-in with a certificate from %s was refused: %s'""",
"""    except CertError as e:
        if not isinstance(e, CrlRefused):   # a revocation server not reached is no wrong try (1.0.287)
            h.failed(key)
        h.store.add_event('sign-ins', 'a sign-in with a certificate from %s was refused: %s'"""),
# R1/1.4: "cannot be checked" written over a check that found the card at the same moment.
(
"""        d['card_ok'], d['card_out'] = -1, None
        h.store.session_merge(s['id'], {'card_ok': -1, 'card_out': None})""",
"""        if h.store.session_merge(s['id'], {'card_ok': -1, 'card_out': None},
                                 expect={'card_ok': d.get('card_ok')}) is False:
            return False                # found meanwhile (1.0.287): a card out, not "cannot be checked"
        d['card_ok'], d['card_out'] = -1, None"""),
# R1/1.5: the check is a picture - a page of another host of the same site could load it (a SameSite cookie
# goes with it) and end or unwatch the session, and read its state from the width. The page's own address
# carries a key made from the session, which no other page can know.
(
"""def card_conf(state):
    \"\"\"What the page is to do: None, or {mode, every, grace, port, out}.\"\"\"
    if not state:
        return None
    return {'mode': card_mode(), 'every': card_every(), 'grace': card_grace(),""",
"""def card_key(token):
    \"\"\"The key of a sign-in's checks (1.0.287) - from its token, which only its own pages hold.\"\"\"
    return hashlib.sha256(('otp-card-check:' + str(token or '')).encode()).hexdigest()[:32]


def card_conf(state, token=''):
    \"\"\"What the page is to do: None, or {mode, every, grace, port, out, key}.\"\"\"
    if not state:
        return None
    return {'mode': card_mode(), 'every': card_every(), 'grace': card_grace(), 'key': card_key(token),"""), (
"""    if not card_bound(s):
        return {'watched': False, 'alive': True, 'gone': False}
    d = s['data']
    pem = str(h.body().get('cert') or '')""",
"""    if not card_bound(s):
        return {'watched': False, 'alive': True, 'gone': False}
    # The page's own key (1.0.287): without it (another host's page of the same site - or a page loaded
    # before the upgrade) only the card found counts - a stranger's page cannot make the card sign; nothing
    # else is changed or told.
    keyed = hmac.compare_digest(str(h.body().get('k') or ''), card_key(h.headers.get('X-Otp-Session')))
    d = s['data']
    pem = str(h.body().get('cert') or '')
    if not keyed and (not pem or cert_sha(pem) != d.get('card')):
        return {'watched': False, 'alive': True, 'gone': False}""")])
edit('90_api.py', [(
"""                    'card': card_conf(card), 'source': acc.get('source'),""",
"""                    'card': card_conf(card, h.headers.get('X-Otp-Session')), 'source': acc.get('source'),""")])
# R1/1.2: an account's row read without its signature checked and written back signed - a field somebody
# else changed in the database (a role, "switched off") was signed with it by a password reset or a sign-in.
edit('50_storage.py', [(
"""        with self.db.transaction():                 # with its signature (1.0.234)
            self.db.update('accounts', one['id'], fields)
            dbguard_account_sign(self.db, fields.get('name') or one['name'])""",
"""        if not _resign and not dbguard_account_ok(self.db, one):
            # Not as otp wrote it (1.0.287): never signed now with what somebody else put in.
            raise ValueError('the account %s is not as otp wrote it in the database - nothing of it is '
                             'changed; as root: otp --passwd %s signs it again as it is now' % (name, name))
        with self.db.transaction():                 # with its signature (1.0.234)
            self.db.update('accounts', one['id'], fields)
            dbguard_account_sign(self.db, fields.get('name') or one['name'])""")])
# R1/2.1: RADIUS on '::' (both families): an IPv4 client came as ::ffff:a.b.c.d, matched no client's IPv4
# range, and every real NAS shared the one line of the queue meant for the addresses of nobody's.
# R1/2.2: the request's Proxy-State was left out of the reply measured before the code is used - a reply near
# 4 KB through a proxy refused after the code was taken (the VPN's retry refused as used).
edit('70_radius_server.py', [(
"""        try:
            addr = ipaddress.ip_address(ip)
            return any(r.get('_net') is not None and addr.version == r['_net'].version and addr in r['_net']""",
"""        try:
            addr = ipaddress.ip_address(ip)
            addr = getattr(addr, 'ipv4_mapped', None) or addr      # ::ffff:a.b.c.d is a.b.c.d (1.0.287)
            return any(r.get('_net') is not None and addr.version == r['_net'].version and addr in r['_net']"""), (
"""    try:
        size = 20 + (18 if CONFIG.get('radius_reply_ma', 1) else 0) + \\
            sum(len(attr_bytes(n, v)) for n, v in pairs)""",
"""    try:
        size = 20 + (18 if CONFIG.get('radius_reply_ma', 1) else 0) + \\
            sum(len(attr_bytes(n, v)) for n, v in pairs) + int(getattr(RADIUS_PROXY_STATE, 'size', 0) or 0)"""), (
"""def reply_too_long(pairs):""",
"""# The request's Proxy-State, measured for the reply it goes back in (1.0.287) - one request a thread.
RADIUS_PROXY_STATE = threading.local()


def reply_too_long(pairs):"""), (
"""        try:
            if blocked:
                d = Decision()
                d.user = str(user or '')[:190]""",
"""        RADIUS_PROXY_STATE.size = sum(len(ps) + 2 for ps in pkt.all(33))
        try:
            if blocked:
                d = Decision()
                d.user = str(user or '')[:190]""")])
# R2/4.1: an alert mail that failed with anything but MailError (the key that seals the queued mail missing -
# the very alert about it) left alert_send: no alert went out, the "right again" ones were lost for good.
edit('88z_alerts.py', [(
"""        mail_deliver(store, msg, to, kind='alert', purpose=kind)
    except MailError as e:""",
"""        mail_deliver(store, msg, to, kind='alert', purpose=kind)
    except Exception as e:                              # noqa: BLE001 - not a MailError alone (1.0.287)"""),
# R2/4.2: in a cluster with one database (not replicated) only one node makes the nightly dump - the other
# was told "no nightly copy" every day, or it flapped. The cluster's newest copy counts there, said once.
(
"""        if CONFIG.get('backup_daily'):
            for n in names:
                h = health.get(n) or {}
                if not h:
                    continue
                last = fnum(h.get('last_backup'))
                if now - last > 36 * 3600:""",
"""        if CONFIG.get('backup_daily'):
            shared = CONFIG.get('ha_mode') != 'replicated'
            newest = max([fnum((health.get(x) or {}).get('last_backup')) for x in names] or [0])
            said_shared = False
            for n in names:
                h = health.get(n) or {}
                if not h:
                    continue
                last = newest if shared else fnum(h.get('last_backup'))
                if shared and said_shared:
                    continue
                if now - last > 36 * 3600:
                    said_shared = shared""")])
# R2/4.3: written and renamed without a sync - after a power cut the new name could be an empty file
# (config.json: the daemon did not start until it was mended by hand; secrets.key).
# R2/4.6: log_sparing by the wall clock - a clock stepped back kept the lines quiet for the step.
# R2/4.4: config.json changed while the daemon started (otp --set, --ha-readdress and a reload) was taken as
# the one already read: its signature was taken after the change.
edit('00_head.py', [(
"""        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, str(path))
        if path.name == 'secrets.key':""",
"""        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())                # on the disk before the name (1.0.287)
        os.replace(tmp, str(path))
        try:
            dfd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
        if path.name == 'secrets.key':"""), (
"""    t = time.time()
    with _LOG_LOCK:
        at, quiet = _LOG_SPARING.get(key, (0.0, 0))
        if t - at < every:""",
"""    t = time.monotonic()                        # not stepped with the clock (1.0.287)
    with _LOG_LOCK:
        at, quiet = _LOG_SPARING.get(key, (None, 0))
        if at is not None and t - at < every:"""), (
"""    try:
        with open(where, encoding='utf-8') as f:
            given = json.load(f)
        if not isinstance(given, dict):
            raise ValueError('the config file is not an object')""",
"""    try:
        raw = Path(where).read_bytes()
        given = json.loads(raw.decode('utf-8'))
        if Path(where) == Path(CONFIG_FILE):
            CONFIG_READ_SIG[0] = hashlib.sha256(raw).hexdigest()    # what was read (1.0.287)
        if not isinstance(given, dict):
            raise ValueError('the config file is not an object')"""), (
"""def load_config(path=None, saved=None):""",
"""CONFIG_READ_SIG = [None]


def load_config(path=None, saved=None):""")])
edit('80_daemon.py', [(
"""        try:
            self.conf_sig = hashlib.sha256(CONFIG_FILE.read_bytes()).hexdigest()
        except OSError:
            self.conf_sig = None""",
"""        try:
            # The bytes load_config read (1.0.287): a change made while the daemon started is one.
            self.conf_sig = CONFIG_READ_SIG[0] or hashlib.sha256(CONFIG_FILE.read_bytes()).hexdigest()
        except OSError:
            self.conf_sig = None""")])
# R2/4.5: the console switch whose ask could not be written (a full disk: OSError) died in its thread, again
# every 5 s, and the page showed it pending for good.
edit('96_console.py', [(
"""                    root_ask('console.ask', 'console.json', ask, 60)
                except ValueError as e:""",
"""                    root_ask('console.ask', 'console.json', ask, 60)
                except (ValueError, OSError) as e:      # a full disk too (1.0.287)""")])
# R2 review: plain_ip took /NN alone - a network written with its mask (10.0.0.0/255.0.0.0), taken before, was
# then left out or refused. Any network ipaddress reads, without a scope id or anything but its letters.
edit('50_storage.py', [(
"""def address_net(text):""",
"""def plain_net(text):
    \"\"\"A network - /24 or /255.255.255.0 - as ipaddress reads it; never a scope id (1.0.287).\"\"\"
    said = str(text or '').strip()
    if not re.match(r'^[0-9A-Fa-f:.]+(/[0-9.]{1,15})?\\Z', said):
        raise ValueError('%r is not a plain address or network' % said[:60])
    return ipaddress.ip_network(said, strict=False)


def address_net(text):"""), (
"""    def set_account(self, name, **fields):""",
"""    def set_account(self, name, _resign=False, **fields):""")])
# R2 review: root's way back for an account whose row the guard refuses (otp --passwd signs it again).
# R2/2.5: --set-role and --passwd on an account of the directory - the pages refuse both (the directory
# decides its role, its password is the directory's); the command line said "done".
edit('95_cli.py', [(
"""            store.set_account(args.passwd, password=pw, must_change=0)""",
"""            one = store.account(args.passwd)
            if one and one.get('source') == 'directory':
                raise ValueError('%s is an account of the directory - its password is the directory\\'s' % args.passwd)
            store.set_account(args.passwd, password=pw, must_change=0, _resign=True)"""), (
"""            if flag == 'set_role':
                store.set_account(name, role=args.role)""",
"""            if flag == 'set_role':
                if acc.get('source') == 'directory':
                    raise ValueError('%s is an account of the directory - its groups there give its role '
                                     '(1.0.287)' % name)
                store.set_account(name, role=args.role)"""), (
"""                r'pass|secret|token|key|pin', k, re.I)""",
"""                r'pass|secret|token|key|pin|(^|_)pw$', k, re.I)""")])
# R2 review: a job (an erase, a move) could start while a copy was put back from a request; and otp --restore
# (a process of its own) beside the daemon's restore or job on the same node.
edit('80_daemon.py', [(
"""    with DB_JOB_LOCK:
        if DB_JOB['running']:
            raise ValueError('%s is going on already' % DB_JOB['what'])""",
"""    with DB_JOB_LOCK:
        if DB_JOB['running']:
            raise ValueError('%s is going on already' % DB_JOB['what'])
        if RESTORE_ONE.locked():
            raise ValueError('a database is being put back - wait for it to end')      # 1.0.287""")])
edit('85_dbfiles.py', [(
"""    if not RESTORE_ONE.acquire(blocking=False):
        raise ValueError('a database is being put back already - wait for it to end')""",
"""    if not in_job and not DB_JOB.get('running'):
        # Another process of this node (otp --restore beside the daemon) at it now (1.0.287).
        try:
            here = json.loads(store.get_meta('db_job:' + node_name()) or 'null') or {}
            if here.get('running') and time.time() - float(here.get('at') or 0) < 300:
                raise ValueError('%s is going on on this node - wait for it to end'
                                 % (here.get('what') or 'a job on the database'))
        except (TypeError, AttributeError):
            pass
    if not RESTORE_ONE.acquire(blocking=False):
        raise ValueError('a database is being put back already - wait for it to end')""")])
# R2/2.1: a configuration file's VIP was kept as it came when it named no address - a vrid that is no number
# broke what root is asked, on both nodes, every few seconds. R2/2.2: realms and clients matched by their
# exact name - "Corp" in the file, "corp" here: the import stopped half way.
edit('90_api.py', [(
"""    vip_in = web.get('vip')
    if isinstance(vip_in, dict) and vip_in.get('address'):""",
"""    vip_in = web.get('vip')
    if isinstance(vip_in, dict) and not vip_in.get('address'):
        # No address: nothing of it is on (1.0.287), and its number read as the pages read it.
        vip_in['on'] = False
        try:
            vip_in['vrid'] = max(1, min(255, int(vip_in.get('vrid') or 51)))
        except (TypeError, ValueError):
            vip_in['vrid'] = 51
    if isinstance(vip_in, dict) and vip_in.get('address'):"""), (
"""            old = next((x for x in store.realms() if x['name'] == r.get('name')), None)""",
"""            old = next((x for x in store.realms() if x['name'].strip().lower() ==
                        str(r.get('name') or '').strip().lower()), None)      # in any case (1.0.287)"""), (
"""            old = next((x for x in store.clients() if x['name'] == c.get('name')), None)""",
"""            old = next((x for x in store.clients() if x['name'].strip().lower() ==
                        str(c.get('name') or '').strip().lower()), None)      # in any case (1.0.287)""")])
# R3/HA.3: "the other node" was the first by name - a node reinstalled under another name and never forgotten
# was taken for it: the clock guard never stepped aside for a live peer, the measured skew was written under the
# dead one's name, a slot-2 node looked at the dead one's state on a split. The live one first, then the newest
# heartbeat - as hatls_peer_name (1.0.271), one helper for them all.
edit('87z_clock.py', [(
"""def clock_peer_row(store, now=None):""",
"""def ha_peer_rows(store):
    \"\"\"The other nodes, the live one first, then the newest heartbeat (1.0.287).\"\"\"
    others = [n for n in ha_nodes(store) if not n.get('me')]
    others.sort(key=lambda n: (not n.get('alive'), -fnum(n.get('at')), n['name']))
    return others


def clock_peer_row(store, now=None):"""), (
"""    now = time.time() if now is None else now
    for n in ha_nodes(store):
        if n.get('me'):
            continue
        row = _meta_json(store, 'clock:state:' + n['name']) or {}""",
"""    now = time.time() if now is None else now
    for n in ha_peer_rows(store):
        row = _meta_json(store, 'clock:state:' + n['name']) or {}"""), (
"""        name = next((n['name'] for n in ha_nodes(store) if not n.get('me')), 'the other node')""",
"""        name = next((n['name'] for n in ha_peer_rows(store)), 'the other node')""")])
# R3/HA.2: arbiter mode - one ping not answered (a router rate-limiting ICMP to itself) took the only node
# left out of service at once, and back at the next answer. Out after three checks in a row without an answer
# (about 6 s); back at the first one. R3/HA.5: "its word from about when the nodes lost each other" read the
# preferred node's time as this one's - off by the very clock that put it aside.
edit('87y_split.py', [(
"""    if store is not None:
        for n in ha_nodes(store):
            if not n.get('me'):
                return n['name']
    return ''""",
"""    if store is not None:
        for n in ha_peer_rows(store):           # the live one first (1.0.287)
            return n['name']
    return ''"""), (
"""        got, verdict = split_arbiter_check()
        SPLIT.update(arb=got, arb_state=verdict, arb_at=mono)""",
"""        got, verdict = split_arbiter_check()
        if verdict is False and SPLIT.get('arb_state') is True:
            SPLIT['arb_miss'] = int(SPLIT.get('arb_miss') or 0) + 1
            if SPLIT['arb_miss'] < 3:
                verdict = True                  # one lost answer is not the arbiter gone (1.0.287)
        else:
            SPLIT['arb_miss'] = 0
        SPLIT.update(arb=got, arb_state=verdict, arb_at=mono)"""), (
"""        recent = fnum(row.get('at')) >= (SPLIT['apart_since'] or time.time()) - \\
            max(5, int(CONFIG.get('split_after_s') or 20)) - 30""",
"""        recent = fnum(row.get('at')) - (clock_skew_of(store, name) or 0.0) >= \\
            (SPLIT['apart_since'] or time.time()) - max(5, int(CONFIG.get('split_after_s') or 20)) - 30""")])
# R2/3.2 (as the review of round 3 had it): a sign-in by the load balancer refused before it looked at who was
# signed in (too many tries, no key set here: 429, 503) left the portal of whoever was signed in in that browser
# before - shown to the next person. Somebody else's session ends first, whatever comes after.
edit('90o_sso.py', [(
"""    peer = str(h.headers.get('X-Otp-Peer') or '').strip()
    # Counted per address and per name as the sign-in is""",
"""    peer = str(h.headers.get('X-Otp-Peer') or '').strip()
    s0 = h.session('portal')
    if s0:
        d0 = s0.get('data') or {}
        full0 = Authenticator.full_name(name, CONFIG.get('portal_realm') or CONFIG.get('default_realm') or '') \\
            if name else ''
        if not (d0.get('sso') and str(d0.get('login') or '').lower() == str(full0 or '').lower()):
            h.store.session_end(h.headers.get('X-Otp-Session'))       # 1.0.287
    # Counted per address and per name as the sign-in is""")])
# R3/rb.1: a destination that listed the backup as 0 bytes (FTP, smbclient - or a server lying) switched the
# cap off: a server sending without end filled the state folder during the weekly check by itself. Without a
# size, never more than the room there is.
edit('86b_rbackup.py', [(
"""        cap = listed + (1 << 20) if listed > 0 else 0     # 0: the destination does not say (FTP)
        try:
            free = shutil.disk_usage(os.path.dirname(os.path.abspath(dst)) or '.').free
        except OSError:
            free = None
        if cap and free is not None and free < cap + BACKUP_ROOM_MIN:""",
"""        try:
            free = shutil.disk_usage(os.path.dirname(os.path.abspath(dst)) or '.').free
        except OSError:
            free = None
        exact = listed > 0
        cap = listed + (1 << 20) if exact else 0
        if not exact:
            # Not said (1.0.287): never more than the room there is, less the room kept free.
            cap = max(16 << 20, (free - BACKUP_ROOM_MIN) if free is not None else (8 << 30))
        if exact and free is not None and free < cap + BACKUP_ROOM_MIN:"""), (
"""        if cap and os.path.getsize(dst) > cap:""",
"""        if exact and os.path.getsize(dst) > cap:"""),
# R3/rb.2: high security looked at the destinations switched on alone, when saved: a switched-off one with plain
# FTP was sent to by "Back up now" with its id, verified and put back from, and "Try it" took any. Each time one
# is used, whatever its switch.
(
"""def rb_transport(t):
    return""",
"""def rb_transport(t):
    hisec_backup_target(dict(t, enabled=1))         # used: high security's rules (1.0.287)
    return""")])
# R3 review: a directory account whose row the guard refuses, signing in - the ValueError of set_account came
# back as a 400 with its words; refused as a sign-in is, said in the events. Root's way back for one of them.
edit('90_api.py', [(
"""        h.store.set_account(name, role=role, display=entry.get('display') or '',
                            dn=entry['dn'], group_list=groups)
    elif CONFIG.get('ha_mode') == 'replicated' and not ha_lead(h.store):""",
"""        if not dbguard_account_ok(h.store.db, acc):
            # Not as otp wrote it (1.0.287): refused as a sign-in, never signed again with what is in it.
            h.store.add_event('sign-ins', 'the account %s is not as otp wrote it in the database - not let in'
                              % name, 'bad', who=name)
            raise ApiError(401, 'that account may not sign in here')
        h.store.set_account(name, role=role, display=entry.get('display') or '',
                            dn=entry['dn'], group_list=groups)
    elif CONFIG.get('ha_mode') == 'replicated' and not ha_lead(h.store):""")])
s95 = open(P + '95_cli.py').read()
a = """    if args.passwd:
        pw = ask_password('a new password for %s' % args.passwd)"""
assert s95.count(a) == 1
s95 = s95.replace(a, """    if args.passwd:
        one = store.account(args.passwd)
        if one and one.get('source') == 'directory':
            # Its password is the directory's; its row signed again as it is (1.0.287) - root's way back
            # for one the guard refuses.
            store.set_account(args.passwd, must_change=0, _resign=True)
            print('%s is an account of the directory: its row is signed again as it is (its password is the '
                  'directory\\'s)' % one['name'])
            return 0
        pw = ask_password('a new password for %s' % args.passwd)""")
open(P + '95_cli.py', 'w').write(s95)
# R3 review: a restore by otp --restore (a process of its own) was not seen by the daemon: a job from the pages
# started on the same database. The restore's row carries its process; a job refuses while it lives.
edit('85_dbfiles.py', [(
"""            said = {'running': True, 'what': 'putting a database back', 'began': time.time()}""",
"""            said = {'running': True, 'what': 'putting a database back', 'began': time.time(), 'pid': os.getpid()}""")])
edit('80_daemon.py', [(
"""        if RESTORE_ONE.locked():
            raise ValueError('a database is being put back - wait for it to end')      # 1.0.287""",
"""        if RESTORE_ONE.locked():
            raise ValueError('a database is being put back - wait for it to end')      # 1.0.287
        try:
            here = json.loads(HA_STORE['store'].get_meta('db_job:' + node_name()) or 'null') or {}
        except Exception:                               # noqa: BLE001
            here = {}
        pid = int(here.get('pid') or 0) if isinstance(here, dict) else 0
        if pid and pid != os.getpid() and here.get('running') and time.time() - float(here.get('at') or 0) < 300:
            try:
                os.kill(pid, 0)
                raise ValueError('%s is going on on this node (otp on the command line) - wait for it to end'
                                 % (here.get('what') or 'a job on the database'))
            except ProcessLookupError:
                pass
            except PermissionError:
                raise ValueError('a database is being put back on this node - wait for it to end')""")])
print('1.0.287 server patched')
