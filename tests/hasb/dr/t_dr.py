# t_dr.py VERSION - disaster recovery, end to end: a cluster of two, set up with much of what otp keeps - tokens,
# accounts, clients, realms, a directory, settings, a VIP address, the password policy of the local users, a
# destination for the backups with its sealed password, page texts - backed up to the destination (a folder: the
# "remote" backup); both machines then lost. A machine installed from nothing (an empty database, no key, no
# state) restored from that backup alone (otp --restore-bundle); a second machine installed from nothing joined to
# it (otp --ha-setup / --ha-join). Then, on both nodes: every row of what was kept as it was (the node-own rows
# aside), the tokens let in by RADIUS, the administrator signs in, the VIP address put to keepalived, the password
# policy put in by both, a backup to the destination made again (its password opened with the key that came back).
# Two new sandboxes (setup.sh), nothing of the current one touched; the sandbox remembered before is put back.
# Usage (root): python3 t_dr.py VERSION
import os, sys, json, time, subprocess, re, glob, hashlib, base64, hmac, struct, socket

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.246'
V = '/home/claude/build/out/otp-%s' % VER
H = '/home/claude/work/hasb'
OLD = open(H + '/current').read().strip()
STAMP = time.strftime('%H%M%S')
S1, S2 = '/tmp/dr%s1' % STAMP, '/tmp/dr%s2' % STAMP
ADMIN_PW = 'Dr-Admin-Pass-246!'
SECRET = 'radius-secret-dr-246'
BKPW = 'Backup-Pass-246-dr-long'
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:500] if more and not c else ''), flush=True)


def sh(cmd, n=None, inp=None, timeout=600):
    """A command in node n's environment (env.sh) of the current sandbox."""
    pre = '. %s/env.sh %s; ' % (H, n) if n else ''
    return subprocess.run(['bash', '-c', pre + cmd], capture_output=True, text=True, input=inp, timeout=timeout)


def otp_(n, args, inp=None, timeout=600, extra=''):
    return sh('%s python3 -I %s/otp.py --no-color %s' % (extra, V, args), n, inp, timeout)


def py(n, code, timeout=300):
    """Python with otp loaded in node n's environment: st (the store) ready."""
    pre = ('import sys, json; sys.path.insert(0, %r); sys.argv = ["x"]\nimport otp\n'
           'otp.load_config(saved=None)\nst = otp.Storage(otp.open_db())\n'
           'otp.load_config(saved=st.settings_saved())\n' % V)
    r = sh('python3 -I -', n, pre + code, timeout)
    if r.returncode:
        print(r.stderr[-1500:])
    return r.stdout.strip().split('\n')[-1] if r.stdout.strip() else ''


def daemons_stop():
    for p in subprocess.run(['pgrep', '-f', 'otp.py --daemon'], capture_output=True, text=True).stdout.split():
        try:
            env = open('/proc/%s/environ' % p, 'rb').read().decode('utf-8', 'replace')
        except OSError:
            continue
        if 'OTP_CONFIG=/tmp/' in env:            # the sandboxes' only - never the installed one
            os.kill(int(p), 15)
    time.sleep(3)


def helpers_restart(ver):
    for p in subprocess.run(['pgrep', '-f', 'helpers[.]sh'], capture_output=True, text=True).stdout.split():
        os.kill(int(p), 15)
    subprocess.Popen(['bash', H + '/helpers.sh', ver], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def start(n):
    subprocess.run(['bash', H + '/start.sh', n, VER], capture_output=True)


def api(n, S, path, body=None, sess=None):
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
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')
    except Exception as e:                              # noqa: BLE001
        return 0, {'error': str(e)}


def up(n, S, secs=90):
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


def until(fn, secs=60):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(1)
    return None


def totp(secret, off=0):
    key = base64.b32decode(secret.upper() + '=' * (-len(secret) % 8))
    c = int(time.time() // 30) + off
    d = hmac.new(key, struct.pack('>Q', c), hashlib.sha1).digest()
    o = d[-1] & 15
    return '%06d' % ((struct.unpack('>I', d[o:o + 4])[0] & 0x7fffffff) % 1000000)


def radius(S, n, user, pw):
    """Access-Request with PAP, (accept|reject|timeout)."""
    conf = json.load(open('%s/%s/config.json' % (S, n)))
    auth = os.urandom(16)
    attrs = b''
    u = user.encode()
    attrs += bytes([1, len(u) + 2]) + u
    p = pw.encode() + b'\0' * (-len(pw) % 16 or 0)
    if not p:
        p = b'\0' * 16
    out, last = b'', auth
    for i in range(0, len(p), 16):
        bx = hashlib.md5(SECRET.encode() + last).digest()
        chunk = bytes(a ^ b for a, b in zip(p[i:i + 16], bx))
        out += chunk; last = chunk
    attrs += bytes([2, len(out) + 2]) + out
    attrs += bytes([4, 6]) + socket.inet_aton('127.0.0.1')
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
    """Every subscription of otp on the two PostgreSQL clusters dropped, with its slot: the
    sandboxes share the clusters, and a slot's name is the cluster's (otp_from_1/2)."""
    for port in (5432, 5433):
        dbs = subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port), '-XAtq', '-c',
                              "SELECT datname FROM pg_database WHERE datname LIKE 'otp_%'"], capture_output=True, text=True).stdout.split()
        for db in dbs:
            for sub in subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port), '-d', db, '-XAtq', '-c',
                                       'SELECT subname FROM pg_subscription'], capture_output=True, text=True).stdout.split():
                for q in ('ALTER SUBSCRIPTION %s DISABLE' % sub, 'ALTER SUBSCRIPTION %s SET (slot_name = NONE)' % sub,
                          'DROP SUBSCRIPTION %s' % sub):
                    subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port), '-d', db, '-XAtq', '-c', q], capture_output=True)
    time.sleep(2)
    for port in (5432, 5433):          # the slots last: a subscription on the other cluster held them
        subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port), '-XAtq', '-c',
                        "SELECT pg_drop_replication_slot(slot_name) FROM pg_replication_slots WHERE slot_name LIKE 'otp_from_%' AND NOT active"],
                       capture_output=True)


def make_cluster(S, fresh_b=True):
    """setup.sh S; node a set up as the first of two, node b joined. Returns the passphrase of the bundle."""
    r = subprocess.run(['bash', H + '/setup.sh', S], capture_output=True, text=True)
    ok('sandbox %s made' % S, r.returncode == 0, r.stderr)
    for n in 'ab':
        os.makedirs('%s/%s/state/web' % (S, n), exist_ok=True)
        # setup.sh copies it from otp-*: with many versions in out/ the copy failed
        subprocess.run(['cp', V + '/deploy/nginx-otp.conf', '%s/%s/nginx/otp.conf' % (S, n)])
    return r


def ha_setup(S):
    subs_drop()
    r = otp_('a', '--ha-setup --ha-peer 10.99.0.2 --ha-peer-port 5433 --ha-address 10.99.0.1 --yes --ha-bundle %s/bundle.json' % S)
    m = re.search(r'shown only now:\s*(\S+)', r.stdout)
    ok('node a: the first of two (--ha-setup)', r.returncode == 0 and m, r.stdout[-600:] + r.stderr[-600:])
    phrase = m.group(1) if m else ''
    open(S + '/ha-setup.out', 'w').write(r.stdout + r.stderr)
    r = otp_('b', '--ha-join %s/bundle.json --node-name nodeb --ha-address 10.99.0.2 --yes' % S, extra='OTP_HA_PASSPHRASE=%s' % phrase)
    open(S + '/ha-join.out', 'w').write(r.stdout + r.stderr)
    ok('node b joined (--ha-join)', r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:])


NODE_OWN = re.compile(r'(:node[ab]$|@@node[ab]$|:node[ab]:)|^(lockouts:|backup_day|seal:fp$|names:nfc|schema:|host:keep:|node:|sig:|host:[a-z]+:now:|host:sshkeys:want|host:users:want|ha:|repl|vip:|clock:|'
                      r'split:|health:|metrics:|snmp:|acme:state|osup:|alerts?:|upgrade:|beat_asked|conf_serial|'
                      r'dbguard|hb:|portal_sso:last|web:state|fw:now|net:|ntp:sync|sessions?:|lock:|seen:|ask:)')


def snapshot(n):
    """What is kept, as rows: every table counted, every kept row's hash (the node-own ones aside)."""
    code = r'''
import hashlib
out = {'counts': {}, 'rows': {}, 'settings': {}}
for t in otp.TABLES:
    try:
        out['counts'][t] = st.db.value('SELECT COUNT(*) FROM %s' % t)
    except Exception as e:
        out['counts'][t] = str(e)[:60]
for r in st.db.rows('SELECT k, v FROM meta'):
    out['rows'][r['k']] = hashlib.sha256(str(r['v']).encode()).hexdigest()[:16]
for r in st.db.rows('SELECT * FROM settings'):
    d = dict(r)
    out['settings'][d.get('k') or d.get('key') or str(d)] = hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:16]
print(json.dumps(out))
'''
    return json.loads(py(n, code) or '{}')


try:
    helpers_restart(VER)
    daemons_stop()
    # ---- 1. the cluster as it was --------------------------------------------------------------------------------
    print('== 1. a cluster of two, set up')
    open(H + '/current', 'w').write('')
    make_cluster(S1)
    open(H + '/current', 'w').write(S1)
    ha_setup(S1)
    helpers_restart(VER)
    for n in 'ab':
        start(n)
    ok('both nodes up', up('a', S1) and up('b', S1))
    setup = r'''
st.add_account('local', 'fulladmin', %(pw)r, must_change=0)
st.add_account('second', 'tokenadmin', 'Second-Admin-Pass-246!', must_change=0)
st.client_save({'name': 'lo', 'address': '127.0.0.0/8', 'secret': %(sec)r, 'enabled': 1})
st.client_save({'name': 'vpn', 'address': '10.99.0.0/24', 'secret': 'vpn-secret-246', 'enabled': 1})
st.directory_save({'name': 'MOCK', 'hosts': '127.0.0.1:3899', 'port': 389, 'tls': 'none', 'base': 'DC=corpnet,DC=loc',
                   'bind_dn': 'otp@corpnet.loc', 'bind_pw': 'the-otp-service-password', 'user_attr': 'sAMAccountName'})
st.realm_save({'name': 'local', 'suffix': '', 'lookup': 'none', 'auth_mode': 'otp'})
st.realm_save({'name': 'corp', 'suffix': 'corpnet.cz', 'directory': 'MOCK', 'lookup': 'upn', 'auth_mode': 'password_otp'})
tk = otp.Tokens(st)
out = {}
for u in ('anna', 'bob', 'cyril', 'dana'):
    out[u] = tk.enroll(u, 'test')['secret']
print(json.dumps(out))
''' % {'pw': ADMIN_PW, 'sec': SECRET}
    KEYS = json.loads(py('a', setup) or '{}')
    ok('tokens, accounts, clients, realms, a directory made on node a', len(KEYS) == 4, KEYS)
    S = login('a', S1)
    ok('the administrator signs in on node a', bool(S))
    c, x = api('a', S1, '/api/settings', {'settings': {'site_name': 'drsite', 'logs_keep': 21, 'alerts_cert_days': 33,
                                                     'portal': 1, 'code_ttl_s': 420, 'radius_guard': 1, 'dir_pw_tries': 3}}, S)
    ok('settings saved', c == 200, x)
    c, x = api('a', S1, '/api/web', {'action': 'vip_save', 'address': '10.99.0.200/24', 'fqdn': '', 'vrid': 61, 'ifaces': {}, 'address6': ''}, S)
    c2, x2 = api('a', S1, '/api/web', {'action': 'vip_on'}, S)
    ok('a VIP address set and on', c == 200 and c2 == 200, (x, x2))
    PW_POL = {'managed': True, 'minlen': 13, 'minclass': 3, 'maxrepeat': 3, 'dictcheck': 1, 'usercheck': 1, 'difok': 4,
              'remember': 4, 'max_days': 180, 'min_days': 0, 'warn_days': 14, 'deny': 0, 'unlock_time': 900, 'fail_interval': 900}
    c, x = api('a', S1, '/api/osusers', {'action': 'policy', 'policy': PW_POL}, S)
    ok('the password policy of the local users set', c == 200, x)
    os.makedirs(S1 + '/dest', exist_ok=True)
    os.chmod(S1 + '/dest', 0o777)
    c, x = api('a', S1, '/api/settings', {'settings': {'rbackup_password': BKPW}}, S)
    c2, x2 = api('a', S1, '/api/rbackup', {'action': 'save', 'target': {'name': 'drfolder', 'kind': 'folder', 'path': S1 + '/dest', 'enabled': 1, 'keep': 5}}, S)
    ok('a destination for the backups (a folder) and the backups\' password', c == 200 and c2 == 200, (x, x2))
    ok('the policy put in by both nodes', until(lambda: all(nn.get('policy_applied') and (nn.get('policy') or {}).get('managed')
                                                           for nn in api('a', S1, '/api/osusers', None, S)[1].get('nodes') or [{}]), 90))
    subprocess.run(['userdel', '-r', 'otpl_dr'], capture_output=True)
    c, x = api('a', S1, '/api/osusers', {'action': 'add', 'name': 'otpl_dr', 'gecos': 'DR Test', 'shell': '/bin/bash',
                                         'password': 'Dr-Local-Pass-246-x', 'sudo': True, 'nodes': ['nodea', 'nodeb']}, S)
    ok('a local user (password, sudo) made on both', c == 200 and until(lambda: os.path.exists('/home/otpl_dr'), 60), x)
    KEYLINE = subprocess.run(['bash', '-c', 'rm -f /tmp/drk /tmp/drk.pub; ssh-keygen -q -t ed25519 -N "" -C dr@test -f /tmp/drk; cat /tmp/drk.pub'],
                             capture_output=True, text=True).stdout.strip()
    c, x = api('a', S1, '/api/sshkeys', {'action': 'add', 'line': KEYLINE, 'nodes': ['nodea'], 'user': 'otpl_dr'}, S)
    ok('...an SSH key of it', c == 200 and until(lambda: os.path.exists('/home/otpl_dr/.ssh/authorized_keys') and
                                               'dr@test' in open('/home/otpl_dr/.ssh/authorized_keys').read(), 60), x)
    SHADOW_BEFORE = [ln for ln in open('/etc/shadow') if ln.startswith('otpl_dr:')][0].split(':')
    UID_BEFORE = subprocess.run(['id', '-u', 'otpl_dr'], capture_output=True, text=True).stdout.strip()
    def kept_has_user():
        # the user is in what is kept: its row of host:keep opened as the daemon would
        got = py('a', 'k = otp.keep_open(otp._meta_json(st, "host:keep:nodea") or {}, "nodea") or {}\n'
                      'print(json.dumps([u["name"] for u in k.get("users") or []]))')
        try:
            return 'otpl_dr' in json.loads(got or '[]')
        except ValueError:
            return False
    ok('...kept for the backups (host:keep) on node a, the new user among them', until(kept_has_user, 120),
       otp_('a', '--machine-kept').stdout)
    for n in 'ab':
        c, x = api(n, S1, '/api/settings', {'settings': {'db_guard': 1}}, login(n, S1))
        ok('the guard of root\'s actions on, node %s (%s)' % (n, c), c == 200, x)
    time.sleep(8)                      # replication of the last rows
    BEFORE = snapshot('a')
    BEFORE_B = snapshot('b')
    ok('the two nodes hold the same rows before', {k: v for k, v in BEFORE['rows'].items() if not NODE_OWN.search(k)} ==
       {k: v for k, v in BEFORE_B['rows'].items() if not NODE_OWN.search(k)},
       sorted(set(k for k in BEFORE['rows'] if not NODE_OWN.search(k)) ^ set(k for k in BEFORE_B['rows'] if not NODE_OWN.search(k)))[:10])
    for u, sec in KEYS.items():
        ok('before: %s let in on node a' % u, radius(S1, 'a', u, totp(sec)) == 'accept')
        break
    r = otp_('a', '--rbackup-now', timeout=900)
    files = glob.glob(S1 + '/dest/otp-backup-*.tar.gz.enc')
    ok('the backup sent to the destination, locked', r.returncode == 0 and files, r.stdout[-500:] + r.stderr[-500:])
    BUNDLE = sorted(files)[-1] if files else ''

    # ---- 2. both machines lost; two installed from nothing ---------------------------------------------------------
    print('== 2. both machines lost - two new ones, from nothing')
    daemons_stop()
    subprocess.run(['userdel', '-r', 'otpl_dr'], capture_output=True)
    ok('the machine lost: the local user and its key gone too', subprocess.run(['id', 'otpl_dr'], capture_output=True).returncode != 0)
    open(H + '/current', 'w').write('')
    make_cluster(S2)
    open(H + '/current', 'w').write(S2)
    for n in 'ab':
        ok('node %s: nothing there - no key, no tokens' % n, not os.path.exists('%s/%s/state/secrets.key' % (S2, n)))
    open(S2 + '/bkpw', 'w').write(BKPW + '\n')
    r = otp_('a', '--restore-bundle %s --passphrase-file %s/bkpw --yes' % (BUNDLE, S2), timeout=900)
    ok('node a restored from the backup alone (--restore-bundle)', r.returncode == 0, r.stdout[-800:] + r.stderr[-800:])
    ok('...it says it came from a cluster: make it two again', '--ha-setup' in r.stdout, r.stdout[-400:])
    left = py('a', 'print(st.db.value("SELECT COUNT(*) FROM meta WHERE k LIKE \'host:sshd:now:%\' OR k LIKE \'host:users:now:%\' '
                   'OR k LIKE \'ntp:applied:%\' OR k LIKE \'console:now:%\' OR k LIKE \'host:selinux:now:%\'"))')
    ok('...not the old machines\' "put in here" rows: each node puts everything in again (%s)' % left, left == '0')
    helpers_restart(VER)
    start('a')
    ok('node a up', up('a', S2))
    S = login('a', S2)
    ok('the administrator signs in on the restored node, with the password of before', bool(S))
    time.sleep(31 - time.time() % 30)    # a step of the clock not used before the backup
    for u, sec in KEYS.items():
        ok('restored node: %s let in by RADIUS' % u, radius(S2, 'a', u, totp(sec)) == 'accept')
    ok('restored node: the guard of root\'s actions on, as it was', json.load(open(S2 + '/a/config.json')).get('db_guard') == 1)
    ok('restored node: the local user made again - its UID, its password, sudo', until(lambda: subprocess.run(['id', '-u', 'otpl_dr'],
       capture_output=True, text=True).stdout.strip() == UID_BEFORE, 120) and
       [ln for ln in open('/etc/shadow') if ln.startswith('otpl_dr:')][0].split(':')[1] == SHADOW_BEFORE[1] and
       'otpl_dr' in subprocess.run(['getent', 'group', 'sudo'], capture_output=True, text=True).stdout)
    ok('...its SSH key back, its own file', os.path.exists('/home/otpl_dr/.ssh/authorized_keys') and 'dr@test' in
       open('/home/otpl_dr/.ssh/authorized_keys').read() and os.stat('/home/otpl_dr/.ssh/authorized_keys').st_uid == int(UID_BEFORE or -1))
    # ---- 3. HA again ----------------------------------------------------------------------------------------------
    print('== 3. a cluster of two again')
    daemons_stop()
    ha_setup(S2)
    for n in 'ab':
        start(n)
    ok('both nodes up', up('a', S2) and up('b', S2))
    Sa, Sb = login('a', S2), login('b', S2)
    ok('the administrator signs in on both', bool(Sa) and bool(Sb))
    time.sleep(10)
    AFTER = {n: snapshot(n) for n in 'ab'}
    keep = lambda snap: {k: v for k, v in snap['rows'].items() if not NODE_OWN.search(k)}
    for n in 'ab':
        a_, b_ = keep(BEFORE), keep(AFTER[n])
        missing = sorted(k for k in a_ if k not in b_)
        changed = sorted(k for k in a_ if k in b_ and a_[k] != b_[k])
        ok('node %s: every kept row of meta back (%d), none missing' % (n, len(a_)), not missing, missing[:15])
        ok('node %s: ...and as it was' % n, not changed, changed[:15])
        ok('node %s: the settings as they were' % n, AFTER[n]['settings'] == BEFORE['settings'],
           sorted(set(AFTER[n]['settings'].items()) ^ set(BEFORE['settings'].items()))[:10])
        for t in ('tokens', 'accounts', 'clients', 'realms', 'directories'):
            if t in BEFORE['counts']:
                ok('node %s: %s %s as before' % (n, BEFORE['counts'][t], t), AFTER[n]['counts'].get(t) == BEFORE['counts'][t],
                   AFTER[n]['counts'].get(t))
        for u, sec in KEYS.items():
            ok('node %s: %s let in by RADIUS' % (n, u), until(lambda: radius(S2, n, u, totp(sec)) == 'accept', 40))
        ok('node %s: the guard of root\'s actions on' % n, json.load(open('%s/%s/config.json' % (S2, n))).get('db_guard') == 1)
    ok('the VIP address put to keepalived on both nodes', until(lambda: all(os.path.exists('%s/%s/keepalived.conf' % (S2, n)) and
                                                                         '10.99.0.200' in open('%s/%s/keepalived.conf' % (S2, n)).read() for n in 'ab'), 90))
    ok('the password policy put in by both nodes', until(lambda: all(nn.get('policy_applied') and (nn.get('policy') or {}).get('managed')
                                                                    and (nn.get('policy') or {}).get('pwquality', {}).get('minlen') == 13
                                                                    for nn in api('a', S2, '/api/osusers', None, Sa)[1].get('nodes') or [{}]), 120))
    v = api('a', S2, '/api/rbackup', None, Sa)[1]
    ok('the destination of the backups there', any(t.get('name') == 'drfolder' for t in v.get('targets') or []), str(v)[:300])
    r = otp_('a', '--rbackup-now', timeout=900)
    ok('...a backup made to it again (its password opened with the key that came back)', r.returncode == 0 and
       len(glob.glob(S1 + '/dest/otp-backup-*.tar.gz.enc')) >= 2, r.stdout[-500:] + r.stderr[-500:])
    c, x = api('a', S2, '/api/osusers', {'action': 'policy', 'policy': dict(PW_POL, managed=False)}, Sa)
    until(lambda: all(nn.get('policy_applied') and not (nn.get('policy') or {}).get('managed')
                      for nn in api('a', S2, '/api/osusers', None, Sa)[1].get('nodes') or [{}]), 90)
finally:
    subprocess.run(['userdel', '-r', 'otpl_dr'], capture_output=True)
    daemons_stop()
    # The restored cluster is a working sandbox: the current one from now on (the one before shares its
    # PostgreSQL's slots, which this run took over).
    open(H + '/current', 'w').write(S2 if os.path.exists(S2 + '/b/config.json') else OLD)
    helpers_restart(os.environ.get('OTP_BACK_VER') or VER)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
