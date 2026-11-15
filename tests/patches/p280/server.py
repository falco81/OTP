# 1.0.280 (hunt rounds 1-3 and the review): python3 server.py PARTS_DIR
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


# A. import: an older file's stored "no password at all" never stops the import half way, nor is it put
#    in effect by the directory alone
edit('90_api.py', [(
"""                if not admin_password_off_now() and any(
                        k in want for k in ('admin_password_off', 'admin_kerberos', 'admin_cert')):""",
"""                if not admin_password_off_now() and any(
                        k in want for k in ('admin_password_off', 'admin_kerberos', 'admin_cert', 'admin_directory')):"""), (
"""                    if _setting_on(after.get('admin_password_off')) and after.get('admin_directory') and (
                            _setting_on(after.get('admin_kerberos')) or _setting_on(after.get('admin_cert'))):
                        for k in ('admin_password_off', 'admin_kerberos', 'admin_cert'):
                            if k in want and str(want[k]) != str(CONFIG.get(k)):
                                want.pop(k)
                                said['%s left as it is (no password at all is switched on only from the pages)' % k] += 1""",
"""                    if _setting_on(after.get('admin_password_off')) and after.get('admin_directory') and (
                            _setting_on(after.get('admin_kerberos')) or _setting_on(after.get('admin_cert'))):
                        for k in ('admin_password_off', 'admin_kerberos', 'admin_cert', 'admin_directory'):
                            if k in want and str(want[k]) != str(CONFIG.get(k)):
                                want.pop(k)
                                said['%s left as it is (no password at all is switched on only from the pages)' % k] += 1
                    if 'admin_password_off' in want and str(want['admin_password_off']) != str(CONFIG.get('admin_password_off')) \\
                            and _setting_on(want['admin_password_off']):
                        # A file of a version before 1.0.278 held it on with no way on (1.0.280): left as it
                        # is here - saved, it stopped the import half way.
                        want.pop('admin_password_off')
                        said['admin_password_off left as it is (no password at all is switched on only from the pages)'] += 1""")])

# B. the certificate's port looked for where its server listens (this node's own addresses)
edit('87c_certlogin.py', [(
"""def cert_listening(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex(('127.0.0.1', int(port))) == 0
    except (OSError, ValueError):
        return False
    finally:
        s.close()""",
"""def cert_listen_hosts(port):
    \"\"\"Where otp's certificate server was told to listen on port (1.0.280): the addresses of its listen
    lines that are this node's own - 127.0.0.1 when it listens on every address, or there is no such file.\"\"\"
    path = os.path.join(os.environ.get('OTP_VIP_NGINX_DIR') or '/etc/nginx/conf.d', 'otp_certlogin.conf')
    try:
        with open(path) as fh:
            text = fh.read()
    except OSError:
        return ['127.0.0.1']
    hosts = []
    for m in re.finditer(r'(?m)^\\s*listen\\s+(?:\\[([^\\]]*)\\]:|([0-9.]+):)?%d\\b' % int(port), text):
        h = m.group(1) if m.group(1) is not None else m.group(2)
        h = {None: '127.0.0.1', '': '127.0.0.1', '0.0.0.0': '127.0.0.1', '::': '::1'}.get(h, h)
        if h not in hosts and _cert_own_address(h):
            hosts.append(h)
    return hosts or ['127.0.0.1']


def _cert_own_address(host):
    \"\"\"Whether an address is this node's own (1.0.280): the VIP's listen line answered from the other
    node, while it holds the VIP, is no answer of this node's nginx.\"\"\"
    s = None
    try:
        s = socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, 0))
        return True
    except (OSError, ValueError):
        return False
    finally:
        if s is not None:
            s.close()


def cert_listening(port):
    \"\"\"Whether nginx answers on the certificate's port - where its server listens (1.0.280): on a node
    whose HTTPS server listens on one address, a look at 127.0.0.1 alone said "not yet" for good.\"\"\"
    try:
        hosts = cert_listen_hosts(int(port))
    except (TypeError, ValueError):
        return False
    for host in hosts:
        s = socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            if s.connect_ex((host, int(port))) == 0:
                return True
        except (OSError, ValueError):
            pass
        finally:
            s.close()
    return False""")])

# D. the person told little when a certificate cannot be checked (the infrastructure's words to the events)
edit('90c_certlogin_api.py', [(
"""    except CertError as e:
        h.failed(key)
        h.store.add_event('sign-ins', 'a sign-in with a certificate from %s was refused: %s'
                          % (h.client_ip(), e), 'warn')
        raise ApiError(401, str(e), extra={'code': 'certificate'})""",
"""    except CertError as e:
        h.failed(key)
        h.store.add_event('sign-ins', 'a sign-in with a certificate from %s was refused: %s'
                          % (h.client_ip(), e), 'warn')
        if isinstance(e, CrlRefused):
            # The person told little (1.0.280): which responder or CRL address of the inside network did
            # not answer, and openssl's words, are for the administrator - in the events.
            raise ApiError(401, 'the certificate cannot be checked for revocation (CRL, OCSP) just now - nobody '
                                'signs in with it until it can; an administrator sees why in the events',
                           extra={'code': 'certificate'})
        raise ApiError(401, str(e), extra={'code': 'certificate'})""")])
print('1.0.280 server patched')

edit('00_head.py', [(
"""DOWNGRADE_FLOOR = '1.0.252'""",
"""# 1.0.280: 1.0.278 - root wrote pg_hba.conf through a link, a CRL's address of anybody's certificate was
# fetched before its chain was checked, any text could be put on the sign-in page as a refusal.
DOWNGRADE_FLOOR = '1.0.278'""")])
edit('90_api.py', [(
"""                try:
                    hisec_guard_settings(store, back)
                except BadSetting as e:
                    raise BadSetting('the settings not in the file were not taken back to their '
                                     'defaults: %s' % e)
                for k in drops:
                    store.drop_setting(k)
                    said['settings back to default'] += 1""",
"""                try:
                    hisec_guard_settings(store, back)
                    # Nobody left without a way in by what is taken back either (1.0.280): Windows
                    # dropped while no password at all is in effect by it.
                    why_in = signin_ways_problem(store, {k: back[k] for k in back if '@' not in k})
                    if why_in:
                        raise BadSetting(why_in)
                except BadSetting as e:
                    raise BadSetting('the settings not in the file were not taken back to their '
                                     'defaults: %s' % e)
                for k in drops:
                    if k.split('@', 1)[0] in KEPT_OFF_KEYS:
                        # Kept as a row of its default (1.0.238's rule, 1.0.280 here too): dropped, root's
                        # helper took "nothing said" for "leave as it is" and nginx kept serving it.
                        store.save_setting(k, back[k], by)
                    else:
                        store.drop_setting(k)
                    said['settings back to default'] += 1""")])
edit('50g_guard.py', [(
"""    # The signed marks of a sign-in's second step ('xm'): a node before 1.0.255 writes none.
    '1.0.255': {}}""",
"""    # The signed marks of a sign-in's second step ('xm'): a node before 1.0.255 writes none.
    '1.0.255': {},
    # Windows tried by itself on the sign-in page, ACME's challenges and certificate before a renewal
    # (1.0.280): written unsigned by the versions before.
    '1.0.280': {'settings': ('admin_kerberos_auto',), 'meta_prefixes': ('acme:chal:', 'acme:before:')}}""")])
s = open(P + '50g_guard.py').read()
old = "'admin_kerberos', 'admin_kerberos_realm',"
assert old in s
if "'admin_kerberos_auto'" not in s.split('DBGUARD_SINCE')[0]:
    s = s.replace(old, "'admin_kerberos', 'admin_kerberos_auto', 'admin_kerberos_realm',", 1)
i = s.index('DBGUARD_META_PREFIXES')
j = s.index('(', i)
s = s[:j + 1] + "'acme:chal:', 'acme:before:', " + s[j + 1:]
open(P + '50g_guard.py', 'w').write(s)
print('round 2 patched')

# RADIUS: the fair queue - a lone line nine tenths at most, the line of the addresses that are no
# client half at all times; such an address never a line of its own
edit('70_radius_server.py', [(
"""            if len(line) >= self.per_key:
                raise queue.Full""",
"""            if len(line) >= (self.per_key if key == '*' or self.n - len(line) > 0 else self.maxsize * 9 // 10):
                # Half the queue at most while others wait (1.0.280); alone, a burst of one VPN (a NAS
                # started again, thousands signing in) may use nine tenths of it - the rest kept for
                # the others, and the line of the addresses that are no client always half at most.
                raise queue.Full"""), (
"""                    self.jobs.put_nowait((kind, via, data, peer, time.time()),
                                         key=radius_fair_key(data, peer[0]))""",
"""                    self.jobs.put_nowait((kind, via, data, peer, time.time()),
                                         key=radius_fair_key(data, peer[0]) if self.fair_known(peer[0]) else '*')""")])
s = open(P + '70_radius_server.py').read()
anchor = "    def work(self, jobs=None, quit=None):"
assert s.count(anchor) == 1
s = s.replace(anchor, '''    def fair_known(self, ip):
        """Whether a packet's address is one of the clients, for its line in the queue (1.0.280): an
        address that is none shares the one line '*' - from addresses no secret was given to, anybody
        took the 256 lines of their own with realm names made up, and a real NAS was left in '*'.
        Only from the clients kept in memory: the reading thread never waits on the database."""
        rows = getattr(self.d.store, '_clients', None)
        if rows is None:
            return True
        try:
            addr = ipaddress.ip_address(ip)
            return any(r.get('_net') is not None and addr.version == r['_net'].version and addr in r['_net']
                       for r in rows)
        except (ValueError, TypeError, KeyError):
            return True

''' + anchor, 1)
open(P + '70_radius_server.py', 'w').write(s)
print('RADIUS patched')

# Tokens: the token's lock let go while the directory is asked whether it is the same person
edit('90_api.py', [(
"""        other = token_same_person(h.store, name, h.d) if s['role'] != 'fulladmin' else ''
        if other:""",
"""        other = ''
        if s['role'] != 'fulladmin':
            # Asked of the directory with the token's lock let go (1.0.280): a RADIUS worker checking
            # a code of this name waited on a directory that hangs - then the token looked at again.
            with token_locks_let_go(h):
                other = token_same_person(h.store, name, h.d)
            had = h.store.token(name)
            if had and had.get('state') != 'pending':
                raise ApiError(403, '%s already has a token in use: only a full administrator '
                                    'replaces it (or the person, on the enrolment pages)' % name)
        if other:""")])
print('tokens patched')

# guard.json says which version wrote it - back on a version after a downgrade, what was signed only
# since a version newer than that one is taken in again (written unsigned meanwhile)
edit('50g_guard.py', [(
"""            DBGUARD['adopted'] = list(got.get('adopted') or []) if isinstance(got, dict) else []
""",
"""            DBGUARD['adopted'] = list(got.get('adopted') or []) if isinstance(got, dict) else []
            by = str(got.get('by') or '1.0.279') if isinstance(got, dict) else '1.0.279'
            if DBGUARD['had_file'] and _dbguard_ver(by) < _dbguard_ver(__version__):
                # Written last by a version before this one (1.0.280): after a downgrade it wrote rows
                # of a version newer than it unsigned - taken in again, as at the upgrade.
                DBGUARD['adopted'] = [v for v in DBGUARD['adopted']
                                      if v == 'tokens' or v not in DBGUARD_SINCE or _dbguard_ver(v) <= _dbguard_ver(by)]
"""), (
"""        data = json.dumps({'seen': DBGUARD['seen'], 'good': DBGUARD['good'],
                           'seen_h': DBGUARD['seen_h'] or {}, 'adopted': DBGUARD.get('adopted') or []})""",
"""        data = json.dumps({'seen': DBGUARD['seen'], 'good': DBGUARD['good'],
                           'seen_h': DBGUARD['seen_h'] or {}, 'adopted': DBGUARD.get('adopted') or [],
                           'by': __version__})""")])

# ACME: a challenge answered on port 80 only while ACME is on (or the reach probe's own)
edit('88a_acme.py', [(
"""    got = _meta_json(store, 'acme:chal:' + token) or {}
    if not got.get('auth') or time.time() - fnum(got.get('at')) > 3600:
        return None
    return got['auth']""",
"""    if not CONFIG.get('acme') and not str(token).startswith('otp-probe-'):
        # Only while ACME is on (1.0.280) - or the reach probe's own answer, asked from here.
        return None
    got = _meta_json(store, 'acme:chal:' + token) or {}
    if not got.get('auth') or time.time() - fnum(got.get('at')) > 3600:
        return None
    if str(token).startswith('otp-probe-') and not got.get('probe'):
        return None
    return got['auth']""")])
print('round 3 patched')

# SSH keys: root's only shown on the pages - none made, put on or taken away from there (1.0.280)
edit('90h_host_api.py', [(
"""    user = str(b.get('user') or 'root')
    try:
        if act == 'refresh':""",
"""    user = str(b.get('user') or 'root')
    if act in ('add', 'drop', 'rk_make', 'rk_given', 'rk_again') and user == 'root':
        # Root's keys are only shown here (1.0.280): a way in as root is put on, or taken away, by
        # root on the node itself - never from the pages.
        raise ApiError(403, 'root\\'s SSH keys are only shown on these pages - put on and taken away by root on '
                            'the node itself (/root/.ssh/authorized_keys)')
    try:
        if act == 'refresh':""")])
print('ssh keys patched')
