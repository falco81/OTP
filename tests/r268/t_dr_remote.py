# t_dr_remote.py VERSION - disaster recovery from a REMOTE backup, the cluster as it was (1.0.268):
# a cluster of two on PostgreSQL 16 with the link between the databases over TLS (verify-full), each daemon's
# own connection to its database over TLS (verify-full), the VIP address (VRRP) on and the guard of root's
# actions (signed rows) on - with tokens, accounts, clients, realms, a directory, settings, a local user with
# its SSH key and the password policy - backed up to three real remote destinations at once: SFTP (an SSH key
# made by otp, the host key trusted), SCP (a password) and SMB 3 (signing and encryption), on a "backup
# server" (sshd 127.0.0.1:2222, smbd 127.0.0.1:4445, account rbdr - rbsrv/up.sh). Both machines then lost.
# A machine installed from nothing gets the newest backup over SFTP as an administrator would (checked
# against its .sha256), puts it back (otp --restore-bundle) and a second machine from nothing joins it
# (--ha-setup / --ha-join); PostgreSQL's TLS of the first cluster is taken away before, as a new machine has
# none. Then the pair must be the same as at the time of the backup: every row of every table (logs: every
# row of before still there), every setting, the configuration of each node, keepalived's and nginx's files,
# the pages' certificates, the cluster's authority, PostgreSQL's TLS, the encrypted link and connections,
# the guard, the local user; RADIUS lets the tokens in on both; the destinations list their backups and take
# a new one. Usage (root): RBDR_PW_FILE=... python3 t_dr_remote.py VERSION
import os, sys, json, time, subprocess, re, glob, hashlib, base64, hmac, struct, socket, shutil

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.268'
V = '/home/claude/build/out/otp-%s' % VER
H = '/home/claude/work/hasb'
OLD = open(H + '/current').read().strip()
STAMP = time.strftime('%m%d%H%M%S')
S1, S2 = '/tmp/drr%s1' % STAMP, '/tmp/drr%s2' % STAMP
ADMIN_PW = 'Drr-Admin-Pass-268!'
SECRET = 'radius-secret-drr-268'
BKPW = 'Backup-Pass-268-drr-long-enough'
RBPW = open(os.environ.get('RBDR_PW_FILE') or '/tmp/claude-0/-home-user-OTP/1e6bf6cd-c213-509f-8166-be80d4ee4e34/scratchpad/rbsrv/pw').read().strip()
PGDATA = {'a': '/var/lib/postgresql/16/main', 'b': '/var/lib/postgresql/16/second'}
PGPORT = {'a': 5432, 'b': 5433}
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:700] if more and not c else ''), flush=True)


def sh(cmd, n=None, inp=None, timeout=600):
    pre = '. %s/env.sh %s; ' % (H, n) if n else ''
    return subprocess.run(['bash', '-c', pre + cmd], capture_output=True, text=True, input=inp, timeout=timeout)


def otp_(n, args, inp=None, timeout=600, extra=''):
    return sh('%s python3 -I %s/otp.py --no-color %s' % (extra, V, args), n, inp, timeout)


def py(n, code, timeout=300):
    pre = ('import sys, json; sys.path.insert(0, %r); sys.argv = ["x"]\nimport otp\n'
           'otp.load_config(saved=None)\nst = otp.Storage(otp.open_db())\n'
           'otp.load_config(saved=st.settings_saved())\n' % V)
    r = sh('python3 -I -', n, pre + code, timeout)
    if r.returncode:
        print(r.stderr[-1500:])
    return r.stdout.strip().split('\n')[-1] if r.stdout.strip() else ''


def psql(port, sql, db='postgres'):
    return subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port), '-d', db, '-XAtq', '-c', sql],
                          capture_output=True, text=True).stdout.strip()


def daemons_stop():
    for p in subprocess.run(['pgrep', '-f', 'otp.py --daemon'], capture_output=True, text=True).stdout.split():
        try:
            env = open('/proc/%s/environ' % p, 'rb').read().decode('utf-8', 'replace')
        except OSError:
            continue
        if 'OTP_CONFIG=/tmp/' in env:
            os.kill(int(p), 15)
    time.sleep(3)


def helpers_restart(ver):
    for p in subprocess.run(['pgrep', '-f', 'helpers[.]sh'], capture_output=True, text=True).stdout.split():
        os.kill(int(p), 15)
    subprocess.Popen(['bash', H + '/helpers.sh', ver], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def start(n):
    subprocess.run(['bash', H + '/start.sh', n, VER], capture_output=True)


def api(n, S, path, body=None, sess=None, timeout=120):
    import urllib.request
    conf = json.load(open('%s/%s/config.json' % (S, n)))
    tok = open('%s/%s/run/api-token' % (S, n)).read().strip()
    h = {'X-Otp-Token': tok, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess:
        h['X-Otp-Session'] = sess
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (conf['api_port'], path),
                                 data=json.dumps(body).encode() if body is not None else None, headers=h,
                                 method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}
    except Exception as e:                              # noqa: BLE001
        return 0, {'error': str(e)}


def up(n, S, secs=120):
    end = time.time() + secs
    while time.time() < end:
        try:
            if api(n, S, '/api/health')[0] in (200, 503):
                return True
        except Exception:                               # noqa: BLE001
            pass
        time.sleep(1)
    return False


def login(n, S):
    c, x = api(n, S, '/api/auth/login', {'name': 'local', 'password': ADMIN_PW})
    return x.get('token') if c == 200 else None


def until(fn, secs=60, every=1):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(every)
    return None


def totp(secret, off=0):
    key = base64.b32decode(secret.upper() + '=' * (-len(secret) % 8))
    c = int(time.time() // 30) + off
    d = hmac.new(key, struct.pack('>Q', c), hashlib.sha1).digest()
    o = d[-1] & 15
    return '%06d' % ((struct.unpack('>I', d[o:o + 4])[0] & 0x7fffffff) % 1000000)


def radius(S, n, user, pw):
    conf = json.load(open('%s/%s/config.json' % (S, n)))
    auth = os.urandom(16)
    u = user.encode()
    attrs = bytes([1, len(u) + 2]) + u
    p = pw.encode() + b'\0' * (-len(pw) % 16 or 0)
    out, last = b'', auth
    for i in range(0, len(p), 16):
        bx = hashlib.md5(SECRET.encode() + last).digest()
        chunk = bytes(a ^ b for a, b in zip(p[i:i + 16], bx))
        out += chunk; last = chunk
    attrs += bytes([2, len(out) + 2]) + out + bytes([4, 6]) + socket.inet_aton('127.0.0.1')
    pkt = struct.pack('>BBH', 1, 7, 20 + len(attrs)) + auth + attrs
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(4)
    try:
        s.sendto(pkt, ('127.0.0.1', conf['radius_auth_port']))
        d, _ = s.recvfrom(4096)
        return {2: 'accept', 3: 'reject', 11: 'challenge'}.get(d[0], str(d[0]))
    except socket.timeout:
        return 'timeout'
    finally:
        s.close()


def subs_drop():
    for port in (5432, 5433):
        for db in psql(port, "SELECT datname FROM pg_database WHERE datname LIKE 'otp_%'").split():
            for sub in psql(port, 'SELECT subname FROM pg_subscription', db).split():
                for q in ('ALTER SUBSCRIPTION %s DISABLE' % sub, 'ALTER SUBSCRIPTION %s SET (slot_name = NONE)' % sub,
                          'DROP SUBSCRIPTION %s' % sub):
                    psql(port, q, db)
    time.sleep(2)
    for port in (5432, 5433):
        psql(port, "SELECT pg_drop_replication_slot(slot_name) FROM pg_replication_slots WHERE slot_name LIKE 'otp_from_%' AND NOT active")


def cfg(S, n):
    return json.load(open('%s/%s/config.json' % (S, n)))


def dbtls(S, sess, body, wait=300):
    c, got = api('a', S, '/api/dbtls', dict(body, action='apply'), sess)
    if c != 200:
        return c, got
    end = time.time() + wait
    while time.time() < end:
        time.sleep(1)
        _, res = api('a', S, '/api/dbtls', {'action': 'result', 'id': got['id'], 'of': 'apply'}, sess)
        nodes = {k: v for k, v in (res.get('nodes') or {}).items() if k in got['nodes']}
        if nodes and all(v for v in nodes.values()):
            bad = {k: v for k, v in nodes.items() if not (isinstance(v, dict) and v.get('ok'))}
            return (200 if not bad else 409), nodes
    return 0, {'timeout': True}


def conns_encrypted(S, n):
    db = cfg(S, n)['db_name']
    got = psql(PGPORT[n], "SELECT s.ssl, count(*) FROM pg_stat_activity a JOIN pg_stat_ssl s USING (pid) "
               "WHERE a.usename = '%s' AND a.backend_type = 'client backend' AND a.client_addr = '127.0.0.1' GROUP BY 1" % db)
    return got.replace('\n', ' '), ('t|' in got and 'f|' not in got)


def link_state(S, n):
    """The subscription of node n: its sslmode, and whether its worker runs; the walsender of the other side over TLS."""
    db = cfg(S, n)['db_name']
    conn = psql(PGPORT[n], 'SELECT subconninfo FROM pg_subscription', db)
    run = psql(PGPORT[n], 'SELECT count(*) FROM pg_stat_subscription WHERE pid IS NOT NULL', db)
    mode = (re.search(r"sslmode='?([a-z-]+)", conn) or [None, ''])[1]
    other = 'b' if n == 'a' else 'a'
    walssl = psql(PGPORT[other], "SELECT s.ssl FROM pg_stat_replication r JOIN pg_stat_ssl s USING (pid)")
    return mode, run, walssl


def replicates(S, src, dst, tag, wait=90):
    mark = 'drr-%s-%d' % (tag, int(time.time() * 1000))
    psql(PGPORT[src], "INSERT INTO events (ts, kind, node, level, who, words) VALUES (%d, 'test', 'x', 'info', 't', '%s')"
         % (time.time(), mark), cfg(S, src)['db_name'])
    return until(lambda: psql(PGPORT[dst], "SELECT count(*) FROM events WHERE words = '%s'" % mark, cfg(S, dst)['db_name']) == '1', wait)


NODE_OWN = re.compile(r'(:node[ab]$|@@node[ab]$|:node[ab]:)|^(lockouts:|backup_day|seal:fp$|names:nfc|schema:|host:keep:|node:|sig:|host:[a-z]+:now:|host:sshkeys:want|host:users:want|ha:|repl|vip:state|vip:role|clock:|'
                      r'split:|health:|metrics:|snmp:|acme:state|osup:|alerts?:|upgrade:|beat_asked|conf_serial|'
                      r'dbguard|hb:|portal_sso:last|web:state|fw:now|net:|ntp:sync|sessions?:|lock:|seen:|ask:|rbackup:status|rbackup:runs|rbackup:job|rb:status|rb:runs)')
KEPT_TABLES = ('meta', 'settings', 'accounts', 'tokens', 'clients', 'realms', 'directories', 'token_once')
LOG_TABLES = ('radius_log', 'otp_log', 'events')


def snapshot(S, n):
    code = r'''
import hashlib
out = {}
for t in otp.TABLES:
    d = {}
    try:
        rows = st.db.rows('SELECT * FROM %s' % t)
    except Exception as e:
        out[t] = {'error': str(e)[:100]}
        continue
    for r in rows:
        r = dict(r)
        key = str(r.get('id') if 'id' in r else r.get('k'))
        d[key] = hashlib.sha256(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()[:20]
    out[t] = d
print(json.dumps(out))
'''
    got = json.loads(py(n, code, 600) or '{}')
    files = {}
    norm = lambda b: b.replace(S.encode(), b'@S@')
    for name in ('keepalived.conf', 'ha-ca.pem'):
        p = '%s/%s/%s' % (S, n, name)
        files[name] = hashlib.sha256(norm(open(p, 'rb').read())).hexdigest()[:20] if os.path.exists(p) else None
    for d in ('nginx', 'certs'):
        for p in sorted(glob.glob('%s/%s/%s/*' % (S, n, d))):
            files['%s/%s' % (d, os.path.basename(p))] = hashlib.sha256(norm(open(p, 'rb').read())).hexdigest()[:20]
    c = cfg(S, n)
    conf = {k: v for k, v in c.items() if k not in ('db_name', 'db_user', 'db_password')}
    conf = json.loads(json.dumps(conf).replace(S, '@S@'))
    pg = {k: psql(PGPORT[n], 'SHOW %s' % k) for k in ('ssl', 'ssl_cert_file', 'ssl_key_file', 'ssl_min_protocol_version')}
    # Its certificate: made anew on a new machine (its key never leaves the machine) - the same
    # authority and the same names are what makes it the same.
    crt = psql(PGPORT[n], 'SHOW ssl_cert_file')
    crt = crt if crt.startswith('/') else os.path.join(PGDATA[n], crt)
    if crt and os.path.exists(crt):
        o = subprocess.run(['openssl', 'x509', '-in', crt, '-noout', '-issuer', '-subject', '-ext', 'subjectAltName'],
                           capture_output=True, text=True).stdout
        pg['cert'] = ' '.join(sorted(x.strip() for x in re.split(r'[,\n]', o) if x.strip() and 'X509v3' not in x))
    else:
        pg['cert'] = None
    return {'tables': got, 'files': files, 'conf': conf, 'pg': pg}


def rb_files(where):
    return sorted(os.path.basename(p) for p in glob.glob(where + '/otp-backup-*.tar.gz.enc'))


SFTP_DIR, SCP_DIR, SMB_DIR = '/home/rbdr/sftp/drr', '/home/rbdr/scp/drr', '/srv/rbdr/smb/drr'
try:
    for d in (SFTP_DIR, SCP_DIR, SMB_DIR):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d); shutil.chown(d, 'rbdr', 'rbdr')
    helpers_restart(VER)
    daemons_stop()
    # ---- 1. the cluster as it was ---------------------------------------------------------------------------
    print('== 1. a cluster of two: PostgreSQL 16, TLS between the databases and to each, VIP, the guard', flush=True)
    r = subprocess.run(['bash', H + '/newsb.sh', S1, VER], capture_output=True, text=True)
    ok('sandbox %s made and joined' % S1, r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
    helpers_restart(VER)
    for n in 'ab':
        start(n)
    ok('both nodes up', up('a', S1) and up('b', S1))
    setup = r'''
st.add_account('local', 'fulladmin', %(pw)r, must_change=0)
st.add_account('second', 'tokenadmin', 'Second-Admin-Pass-268!', must_change=0)
st.client_save({'name': 'lo', 'address': '127.0.0.0/8', 'secret': %(sec)r, 'enabled': 1})
st.client_save({'name': 'vpn', 'address': '10.99.0.0/24', 'secret': 'vpn-secret-268-xx', 'enabled': 1})
st.directory_save({'name': 'MOCK', 'hosts': '127.0.0.1:3899', 'port': 389, 'tls': 'none', 'base': 'DC=corpnet,DC=loc',
                   'bind_dn': 'otp@corpnet.loc', 'bind_pw': 'the-otp-service-password', 'user_attr': 'sAMAccountName'})
st.realm_save({'name': 'local', 'suffix': '', 'lookup': 'none', 'auth_mode': 'otp'})
st.realm_save({'name': 'corp', 'suffix': 'corpnet.cz', 'directory': 'MOCK', 'lookup': 'upn', 'auth_mode': 'password_otp'})
tk = otp.Tokens(st)
out = {}
for u in ('anna', 'bob', 'cyril', 'dana', 'emil'):
    out[u] = tk.enroll(u, 'test')['secret']
print(json.dumps(out))
''' % {'pw': ADMIN_PW, 'sec': SECRET}
    KEYS = json.loads(py('a', setup) or '{}')
    ok('tokens, accounts, clients, realms, a directory made', len(KEYS) == 5, KEYS)
    S = login('a', S1)
    ok('the administrator signs in', bool(S))
    c, x = api('a', S1, '/api/settings', {'settings': {'site_name': 'drrsite', 'logs_keep': 21, 'alerts_cert_days': 33,
                                                     'portal': 1, 'code_ttl_s': 420, 'radius_guard': 1, 'dir_pw_tries': 3}}, S)
    ok('settings saved', c == 200, x)
    # -- TLS: the link between the databases, then each daemon's own connection
    c, x = api('a', S1, '/api/ha', {'action': 'tls_link'}, S)
    ok('the link\'s TLS asked (%s)' % c, c == 200, x)
    ok('...the link over TLS on both, verify-full', until(lambda: all(cfg(S1, n).get('ha_tls') == 'verify-full' for n in 'ab') and
       all(json.loads(psql(PGPORT['a'], "SELECT v FROM meta WHERE k = 'hatls:node:node%s'" % n, cfg(S1, 'a')['db_name']) or '{}').get('step') == 'done'
           for n in 'ab'), 300, 2))
    S = login('a', S1)
    s1_, g1 = dbtls(S1, S, {'phase': 'server', 'mode': 'verify-full'})
    s2_, g2 = dbtls(S1, S, {'phase': 'connect', 'mode': 'verify-full'})
    ok('each daemon\'s connection to its database over TLS, verify-full (%s %s)' % (s1_, s2_), s1_ == 200 and s2_ == 200, (g1, g2))
    S = login('a', S1)
    # -- the VIP address (VRRP)
    c, x = api('a', S1, '/api/web', {'action': 'vip_save', 'address': '10.99.0.200/24', 'fqdn': '', 'vrid': 62, 'ifaces': {}, 'address6': ''}, S)
    c2, x2 = api('a', S1, '/api/web', {'action': 'vip_on'}, S)
    ok('the VIP address (VRRP) set and on', c == 200 and c2 == 200, (x, x2))
    ok('...keepalived\'s configuration on both nodes', until(lambda: all(os.path.exists('%s/%s/keepalived.conf' % (S1, n)) and
       '10.99.0.200' in open('%s/%s/keepalived.conf' % (S1, n)).read() for n in 'ab'), 90))
    # -- a local user, its key, the password policy
    PW_POL = {'managed': True, 'minlen': 13, 'minclass': 3, 'maxrepeat': 3, 'dictcheck': 1, 'usercheck': 1, 'difok': 4,
              'remember': 4, 'max_days': 180, 'min_days': 0, 'warn_days': 14, 'deny': 0, 'unlock_time': 900, 'fail_interval': 900}
    c, x = api('a', S1, '/api/osusers', {'action': 'policy', 'policy': PW_POL}, S)
    ok('the password policy of the local users', c == 200, x)
    subprocess.run(['userdel', '-r', 'otpl_drr'], capture_output=True)
    c, x = api('a', S1, '/api/osusers', {'action': 'add', 'name': 'otpl_drr', 'gecos': 'DRR Test', 'shell': '/bin/bash',
                                         'password': 'Drr-Local-Pass-268-x', 'sudo': True, 'nodes': ['nodea', 'nodeb']}, S)
    ok('a local user on both', c == 200 and until(lambda: os.path.exists('/home/otpl_drr'), 60), x)
    KEYLINE = subprocess.run(['bash', '-c', 'rm -f /tmp/drrk /tmp/drrk.pub; ssh-keygen -q -t ed25519 -N "" -C drr@test -f /tmp/drrk; cat /tmp/drrk.pub'],
                             capture_output=True, text=True).stdout.strip()
    c, x = api('a', S1, '/api/sshkeys', {'action': 'add', 'line': KEYLINE, 'nodes': ['nodea'], 'user': 'otpl_drr'}, S)
    ok('...its SSH key', c == 200 and until(lambda: os.path.exists('/home/otpl_drr/.ssh/authorized_keys') and
       'drr@test' in open('/home/otpl_drr/.ssh/authorized_keys').read(), 60), x)
    SHADOW_BEFORE = [ln for ln in open('/etc/shadow') if ln.startswith('otpl_drr:')][0].split(':')
    UID_BEFORE = subprocess.run(['id', '-u', 'otpl_drr'], capture_output=True, text=True).stdout.strip()
    ok('...kept for the backups (host:keep)', until(lambda: 'otpl_drr' in (py('a', 'k = otp.keep_open(otp._meta_json(st, "host:keep:nodea") or {}, "nodea") or {}\n'
                                                                              'print(json.dumps([u["name"] for u in k.get("users") or []]))') or ''), 120, 3))
    # -- three remote destinations, the backups' password
    c, x = api('a', S1, '/api/settings', {'settings': {'rbackup_password': BKPW}}, S)
    ok('the backups\' password', c == 200, x)
    TGT = {}
    for t in ({'name': 'sftp-box', 'kind': 'sftp', 'host': '127.0.0.1', 'port': 2222, 'user': 'rbdr', 'path': 'sftp/drr', 'enabled': 1, 'keep': 10},
              {'name': 'scp-box', 'kind': 'scp', 'host': '127.0.0.1', 'port': 2222, 'user': 'rbdr', 'password': RBPW, 'path': 'scp/drr', 'enabled': 1, 'keep': 10},
              {'name': 'nas', 'kind': 'smb', 'host': '127.0.0.1', 'port': 4445, 'share': 'rb', 'user': 'rbdr', 'password': RBPW, 'path': 'drr',
               'smb_encrypt': 1, 'enabled': 1, 'keep': 10}):
        c, x = api('a', S1, '/api/rbackup', {'action': 'save', 'target': t}, S)
        ok('destination %s (%s) saved' % (t['name'], t['kind']), c == 200, x)
        TGT[t['name']] = (x.get('target') or {}).get('id')
    c, x = api('a', S1, '/api/rbackup', {'action': 'keygen', 'id': TGT['sftp-box']}, S)
    pub = x.get('pub') or ''
    os.makedirs('/home/rbdr/.ssh', exist_ok=True)
    open('/home/rbdr/.ssh/authorized_keys', 'w').write(pub.strip() + '\n')
    subprocess.run(['chown', '-R', 'rbdr:rbdr', '/home/rbdr/.ssh']); os.chmod('/home/rbdr/.ssh', 0o700); os.chmod('/home/rbdr/.ssh/authorized_keys', 0o600)
    ok('SFTP: an SSH key made by otp, put on the backup server', c == 200 and pub.startswith('ssh-'), x)
    for name in ('sftp-box', 'scp-box'):
        c, x = api('a', S1, '/api/rbackup', {'action': 'hostkey_scan', 'id': TGT[name]}, S)
        c2, x2 = api('a', S1, '/api/rbackup', {'action': 'hostkey_trust', 'id': TGT[name], 'hostkey': x.get('hostkey')}, S)
        ok('%s: the server\'s host key trusted' % name, c == 200 and c2 == 200, (x, x2))
    for name in TGT:
        c, x = api('a', S1, '/api/rbackup', {'action': 'try', 'id': TGT[name]}, S)
        ok('%s: Try it - it works' % name, c == 200 and x.get('ok'), x)
    # -- the guard of root's actions, on both
    for n in 'ab':
        c, x = api(n, S1, '/api/settings', {'settings': {'db_guard': 1}}, login(n, S1))
        ok('the guard of root\'s actions on, node %s' % n, c == 200, x)
    ok('replication a -> b', replicates(S1, 'a', 'b', 'pre-ab'))
    ok('replication b -> a', replicates(S1, 'b', 'a', 'pre-ba'))
    for n in 'ab':
        got, enc = conns_encrypted(S1, n)
        ok('node %s: its daemon\'s connections encrypted (%s)' % (n, got), enc and cfg(S1, n).get('db_tls') == 'verify-full')
        mode, run, walssl = link_state(S1, n)
        ok('node %s: its subscription verify-full, running, the other side\'s sender over TLS (%s %s %s)' % (n, mode, run, walssl),
           mode == 'verify-full' and run == '1' and walssl == 't')
    for u, sec in KEYS.items():
        ok('before: %s let in on node a' % u, radius(S1, 'a', u, totp(sec)) == 'accept')
        break
    time.sleep(10)
    BEFORE = {n: snapshot(S1, n) for n in 'ab'}
    keep = lambda snap, t: {k: v for k, v in snap['tables'].get(t, {}).items() if not (t == 'meta' and NODE_OWN.search(k))}
    for t in KEPT_TABLES:
        ok('before: the two nodes hold the same %s (%d rows)' % (t, len(keep(BEFORE['a'], t))), keep(BEFORE['a'], t) == keep(BEFORE['b'], t),
           sorted(set(keep(BEFORE['a'], t).items()) ^ set(keep(BEFORE['b'], t).items()))[:8])
    # -- SELinux enforcing on both, as the nodes said it (no SELinux in this container: the nodes' own
    #    rows, as the root helper writes them on an enforcing machine)
    for n in 'ab':
        row = json.dumps({'data': {'mode': 'Enforcing', 'config': 'enforcing', 'policy': 'targeted', 'module': True,
                                   'problems': [], 'denials': {'tool': True, 'total': 0, 'groups': []}},
                          'at': time.time(), 'done': 'x', 'error': '', 'said': [], 'action': 'check'})
        psql(PGPORT['a'], "INSERT INTO meta (k, v) VALUES ('host:selinux:now:node%s', '%s') ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v"
             % (n, row.replace("'", "''")), cfg(S1, 'a')['db_name'])
    LEGACY = os.environ.get('DRR_LEGACY') == '1'
    if LEGACY:
        # A backup as one before 1.0.268 makes it: no wish of the cluster for the connections. The
        # daemons stopped first (they take the wish from the nodes' rows at once - the upgrade of a
        # running cluster); the backup made on the command line.
        daemons_stop()
        for n in 'ab':
            psql(PGPORT[n], "DELETE FROM meta WHERE k = 'dbtls_want'", cfg(S1, n)['db_name'])
        time.sleep(5)
        ok('(a backup as one before 1.0.268: no dbtls_want in it)', psql(PGPORT['a'], "SELECT count(*) FROM meta WHERE k = 'dbtls_want'",
                                                                         cfg(S1, 'a')['db_name']) == '0')
    else:
        ok('the cluster\'s wish for the connections kept (dbtls_want: verify-full) - in every backup',
           '"verify-full"' in psql(PGPORT['a'], "SELECT v FROM meta WHERE k = 'dbtls_want'", cfg(S1, 'a')['db_name']))
    time.sleep(5)
    # -- the backup, to the three at once
    r = otp_('a', '--rbackup-now', timeout=900)
    got = {d: rb_files(d) for d in (SFTP_DIR, SCP_DIR, SMB_DIR)}
    ok('the backup sent to SFTP, SCP and SMB at once', r.returncode == 0 and all(got.values()), r.stdout[-600:] + r.stderr[-600:] + str(got))
    NAME = got[SFTP_DIR][-1] if got[SFTP_DIR] else ''
    same = len({hashlib.sha256(open(os.path.join(d, NAME), 'rb').read()).hexdigest() for d in got if NAME in got[d]}) == 1
    ok('...the same file at all three (%s)' % NAME, NAME and all(NAME in v for v in got.values()) and same)
    for d in got:
        ok('...with its .sha256 and -RESTORE.md beside it at %s' % d.split('/')[-2],
           os.path.exists(os.path.join(d, NAME + '.sha256')) and glob.glob(os.path.join(d, NAME.replace('.tar.gz.enc', '') + '*RESTORE.md')))
    ok('...locked: not a gzip, no PEM, no token secret readable in it', NAME and open(os.path.join(SFTP_DIR, NAME), 'rb').read(2) != b'\x1f\x8b'
       and b'PRIVATE KEY' not in open(os.path.join(SFTP_DIR, NAME), 'rb').read())

    # ---- 2. both machines lost; one installed from nothing gets the backup over SFTP --------------------------
    print('== 2. both machines lost - a new one, from nothing, the backup fetched over SFTP', flush=True)
    daemons_stop()
    subs_drop()
    subprocess.run(['userdel', '-r', 'otpl_drr'], capture_output=True)
    ok('the machines lost: the local user gone too', subprocess.run(['id', 'otpl_drr'], capture_output=True).returncode != 0)
    # A new machine's PostgreSQL has no TLS: what the first cluster put in is taken away.
    for n in 'ab':
        for k in ('ssl', 'ssl_cert_file', 'ssl_key_file', 'ssl_min_protocol_version'):
            psql(PGPORT[n], 'ALTER SYSTEM RESET %s' % k)
        for f in glob.glob(PGDATA[n] + '/otp-*.crt') + glob.glob(PGDATA[n] + '/otp-*.key'):
            os.unlink(f)
        psql(PGPORT[n], 'SELECT pg_reload_conf()')
    time.sleep(2)
    # (Ubuntu's PostgreSQL has ssl = on with its own snakeoil certificate out of the box; RHEL's off.)
    ok('PostgreSQL of both: nothing of otp\'s TLS left, as on a machine from nothing',
       all('otp' not in psql(PGPORT[n], 'SHOW ssl_cert_file') and not glob.glob(PGDATA[n] + '/otp-*') for n in 'ab'),
       [psql(PGPORT[n], 'SHOW ssl_cert_file') for n in 'ab'])
    r = subprocess.run(['bash', H + '/setup.sh', S2], capture_output=True, text=True)
    ok('two machines from nothing (%s)' % S2, r.returncode == 0, r.stderr)
    for n in 'ab':
        subprocess.run(['cp', V + '/deploy/nginx-otp.conf', '%s/%s/nginx/otp.conf' % (S2, n)])
        ok('node %s: nothing there - no key, no database rows' % n, not os.path.exists('%s/%s/state/secrets.key' % (S2, n)))
    open(H + '/current', 'w').write(S2)
    # The administrator fetches the newest backup from the backup server, over SFTP, with its .sha256.
    os.makedirs(S2 + '/fetch', exist_ok=True)
    open(S2 + '/askpass', 'w').write('#!/bin/sh\ncat %s\n' % (os.environ.get('RBDR_PW_FILE') or
                                     '/tmp/claude-0/-home-user-OTP/1e6bf6cd-c213-509f-8166-be80d4ee4e34/scratchpad/rbsrv/pw'))
    os.chmod(S2 + '/askpass', 0o700)
    r = subprocess.run(['setsid', 'sftp', '-P', '2222', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=%s/kh' % S2,
                        '-o', 'PubkeyAuthentication=no', '-o', 'PreferredAuthentications=password',
                        'rbdr@127.0.0.1:sftp/drr/%s*' % NAME, S2 + '/fetch/'],
                       capture_output=True, text=True, env=dict(os.environ, SSH_ASKPASS=S2 + '/askpass', SSH_ASKPASS_REQUIRE='force', DISPLAY=':0'), timeout=120)
    FETCHED = os.path.join(S2, 'fetch', NAME)
    ok('the backup fetched over SFTP from the backup server', r.returncode == 0 and os.path.exists(FETCHED), r.stderr[-400:])
    want = (open(FETCHED + '.sha256').read().split() or [''])[0] if os.path.exists(FETCHED + '.sha256') else ''
    ok('...it is whole: its SHA-256 as the .sha256 beside it says', want and hashlib.sha256(open(FETCHED, 'rb').read()).hexdigest() == want)
    open(S2 + '/bkpw', 'w').write(BKPW + '\n'); os.chmod(S2 + '/bkpw', 0o600)
    r = otp_('a', '--restore-bundle %s --passphrase-file %s/bkpw' % (FETCHED, S2), timeout=600)
    ok('what is in it, before anything is done (cluster, nodes, version)', r.returncode == 0 and 'node' in r.stdout.lower(), r.stdout[-600:] + r.stderr[-400:])
    r = otp_('a', '--restore-bundle %s --passphrase-file %s/bkpw --yes' % (FETCHED, S2), timeout=900)
    ok('node a restored from it (--restore-bundle)', r.returncode == 0, r.stdout[-800:] + r.stderr[-800:])
    ok('...it says it came from a cluster: make it two again', '--ha-setup' in r.stdout, r.stdout[-400:])
    open(S2 + '/restore.out', 'w').write(r.stdout + r.stderr)
    # ---- 3. HA again ------------------------------------------------------------------------------------------
    print('== 3. a cluster of two again', flush=True)
    r = otp_('a', '--ha-setup --ha-peer 10.99.0.2 --ha-peer-port 5433 --ha-address 10.99.0.1 --yes --ha-bundle %s/bundle.json' % S2)
    m = re.search(r'shown only now:\s*(\S+)', r.stdout)
    ok('node a: the first of two again (--ha-setup)', r.returncode == 0 and m, r.stdout[-800:] + r.stderr[-800:])
    open(S2 + '/ha-setup.out', 'w').write(r.stdout + r.stderr)
    r = otp_('b', '--ha-join %s/bundle.json --node-name nodeb --ha-address 10.99.0.2 --yes' % S2, extra='OTP_HA_PASSPHRASE=%s' % (m.group(1) if m else ''))
    open(S2 + '/ha-join.out', 'w').write(r.stdout + r.stderr)
    ok('node b from nothing joined (--ha-join)', r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:])
    helpers_restart(VER)
    for n in 'ab':
        start(n)
    ok('both nodes up', up('a', S2) and up('b', S2))
    # Whatever the nodes put back by themselves (TLS of the link and to the databases, keepalived, the user),
    # given the time they take - then compared, before any sign-in or RADIUS request changes a row.
    ok('the link over TLS again on both, verify-full', until(lambda: all(cfg(S2, n).get('ha_tls') == 'verify-full' for n in 'ab'), 420, 3),
       [cfg(S2, n).get('ha_tls') for n in 'ab'])
    ok('each daemon\'s connection to its database over TLS again, verify-full', until(lambda: all(cfg(S2, n).get('db_tls') == 'verify-full' for n in 'ab'), 420, 3),
       [cfg(S2, n).get('db_tls') for n in 'ab'])
    ok('keepalived\'s configuration with the VIP address on both', until(lambda: all(os.path.exists('%s/%s/keepalived.conf' % (S2, n)) and
       '10.99.0.200' in open('%s/%s/keepalived.conf' % (S2, n)).read() for n in 'ab'), 120))
    ok('the local user made again - its UID, its password, sudo', until(lambda: subprocess.run(['id', '-u', 'otpl_drr'],
       capture_output=True, text=True).stdout.strip() == UID_BEFORE, 180, 3) and
       [ln for ln in open('/etc/shadow') if ln.startswith('otpl_drr:')][0].split(':')[1] == SHADOW_BEFORE[1])
    ok('...its SSH key back', until(lambda: os.path.exists('/home/otpl_drr/.ssh/authorized_keys') and 'drr@test' in open('/home/otpl_drr/.ssh/authorized_keys').read(), 120, 3))
    ok('replication a -> b', replicates(S2, 'a', 'b', 'post-ab'))
    ok('replication b -> a', replicates(S2, 'b', 'a', 'post-ba'))
    time.sleep(15)
    AFTER = {n: snapshot(S2, n) for n in 'ab'}
    for n in 'ab':
        for t in KEPT_TABLES:
            a_, b_ = keep(BEFORE[n], t), keep(AFTER[n], t)
            missing = sorted(k for k in a_ if k not in b_)
            changed = sorted(k for k in a_ if k in b_ and a_[k] != b_[k] and not (LEGACY and k == 'dbtls_want'))
            # A backup of before 1.0.268 had no wish for the connections: written after it is put back.
            extra = sorted(k for k in b_ if k not in a_ and not (LEGACY and k == 'dbtls_want'))
            ok('node %s: %s - all %d rows back, as they were' % (n, t, len(a_)), not missing and not changed,
               {'missing': missing[:12], 'changed': changed[:12]})
            ok('node %s: %s - nothing more than before' % (n, t), not extra, extra[:12])
        for t in LOG_TABLES:
            a_, b_ = BEFORE[n]['tables'].get(t, {}), AFTER[n]['tables'].get(t, {})
            lost = sorted(k for k in a_ if a_[k] != b_.get(k))
            ok('node %s: %s - every row of before still there (%d)' % (n, t, len(a_)), not lost, lost[:10])
        ca, cb = BEFORE[n]['conf'], AFTER[n]['conf']
        diff = sorted(k for k in set(ca) | set(cb) if ca.get(k) != cb.get(k))
        ok('node %s: its configuration (config.json) as it was' % n, not diff, {k: (ca.get(k), cb.get(k)) for k in diff[:10]})
        fa, fb = BEFORE[n]['files'], AFTER[n]['files']
        diff = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
        ok('node %s: keepalived, nginx, the pages\' certificates, the cluster\'s authority - the same files (%d)' % (n, len(fa)), not diff,
           {k: (fa.get(k), fb.get(k)) for k in diff[:10]})
        pa, pb = BEFORE[n]['pg'], AFTER[n]['pg']
        ok('node %s: PostgreSQL\'s TLS as it was (%s)' % (n, pb.get('ssl')), pa == pb, (pa, pb))
        got, enc = conns_encrypted(S2, n)
        ok('node %s: its daemon\'s connections encrypted (%s)' % (n, got), enc)
        mode, run, walssl = link_state(S2, n)
        ok('node %s: its subscription verify-full, running, over TLS (%s %s %s)' % (n, mode, run, walssl),
           mode == 'verify-full' and run == '1' and walssl == 't')
        ok('node %s: the guard of root\'s actions on' % n, cfg(S2, n).get('db_guard') == 1)
    # ---- 4. it works as it did --------------------------------------------------------------------------------
    print('== 4. it works as it did', flush=True)
    Sa, Sb = login('a', S2), login('b', S2)
    ok('the administrator signs in on both, with the password of before', bool(Sa) and bool(Sb))
    time.sleep(31 - time.time() % 30)
    for n in 'ab':
        for u, sec in KEYS.items():
            ok('node %s: %s let in by RADIUS' % (n, u), until(lambda: radius(S2, n, u, totp(sec)) == 'accept', 40))
    ok('the password policy put in by both nodes', until(lambda: all(nn.get('policy_applied') and (nn.get('policy') or {}).get('managed')
       and (nn.get('policy') or {}).get('pwquality', {}).get('minlen') == 13 for nn in api('a', S2, '/api/osusers', None, Sa)[1].get('nodes') or [{}]), 180, 3))
    def after_has(n):
        sess = login(n, S2)
        api(n, S2, '/api/after', {'action': 'check', 'node': 'node' + n}, sess)     # Look again
        time.sleep(3)
        c, x = api(n, S2, '/api/after', None, sess)
        return [i for i in x.get('items') or [] if i.get('id') == 'selinux-was-enforcing' and i.get('node') == 'node' + n]
    for n in 'ab':
        got = until(lambda: after_has(n), 300, 10)
        ok('node %s: To be done by hand says SELinux was enforcing there before the backup was put back' % n,
           got and any('enforcing' in json.dumps(i).lower() for i in got), got)
    for name, tid in TGT.items():
        c, x = api('a', S2, '/api/rbackup', {'action': 'list', 'id': tid}, Sa)
        ok('%s: its backups listed from the restored cluster (its key, password and host key back)' % name,
           c == 200 and any(f.get('name') == NAME for f in x.get('files') or []), str(x)[:300])
    r = otp_('a', '--rbackup-now', timeout=900)
    ok('a new backup to all three from the restored cluster', r.returncode == 0 and all(len(rb_files(d)) >= 2 for d in (SFTP_DIR, SCP_DIR, SMB_DIR)),
       r.stdout[-500:] + r.stderr[-500:])
    c, x = api('a', S2, '/api/osusers', {'action': 'policy', 'policy': dict(PW_POL, managed=False)}, Sa)
    until(lambda: all(nn.get('policy_applied') and not (nn.get('policy') or {}).get('managed')
                      for nn in api('a', S2, '/api/osusers', None, Sa)[1].get('nodes') or [{}]), 90)
finally:
    subprocess.run(['userdel', '-r', 'otpl_drr'], capture_output=True)
    daemons_stop()
    open(H + '/current', 'w').write(S2 if os.path.exists(S2 + '/b/config.json') else OLD)
    helpers_restart(os.environ.get('OTP_BACK_VER') or VER)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
