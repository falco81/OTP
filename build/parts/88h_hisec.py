

# ---- High security (1.0.168) -------------------------------------------------------------
# Settings → Tokens → High security: every way of doing something less safely
# switched off. It is switched on only once nothing stands against it - what
# does is listed, each with where it is set; while it is on, what would stand
# against it is refused wherever it is changed (the pages, the API, the
# command line) and greyed out on the pages. What is only advised is listed
# beside it and stops nothing.
#
# Each rule of a setting: (what is wrong with the value, or '') for a value
# and the configuration around it; `forbid`/`most`/`least` tell the pages
# which values to grey out.
def _hs_on():
    return bool(CONFIG.get('high_security'))


HISEC_SETTINGS = {
    'radius_reply_ma': {'forbid': [0], 'pane': 'radius',
                        'why': 'RADIUS answers without a Message-Authenticator (BlastRADIUS)'},
    'radius_ma_sticky': {'forbid': [0], 'pane': 'radius',
                         'why': 'a client that sent a Message-Authenticator may leave it out again'},
    'radius_guard': {'forbid': [0], 'pane': 'guard',
                     'why': 'guessing passwords and codes over RADIUS is not held back'},
    'smtp_security': {'forbid': ['none', 'starttls-if'], 'pane': 'mail',
                      'when': lambda c: c.get('mail_mode') == 'smtp',
                      'why': 'mail goes to the mail server unencrypted, or encrypted only if it '
                             'offers to'},
    'smtp_verify': {'forbid': [0], 'pane': 'mail', 'when': lambda c: c.get('mail_mode') != 'off',
                    'why': 'the mail server\'s certificate is not checked'},
    'mail_direct_tls': {'forbid': ['if-offered'], 'pane': 'mail',
                        'when': lambda c: c.get('mail_mode') == 'direct',
                        'why': 'mail is delivered unencrypted where the recipient\'s server '
                               'does not offer TLS'},
    'sms_url': {'pane': 'codes', 'when': lambda c: c.get('sms_mode') == 'http',
                'test': lambda v, c: str(v or '').strip().lower().startswith('http://'),
                'why': 'the SMS gateway is asked over plain http://'},
    'sms_tel_https': {'forbid': [0], 'pane': 'codes',
                      'when': lambda c: c.get('sms_mode') == 'teltonika',
                      'why': 'the telephone gateway is asked over plain HTTP'},
    'sms_tel_verify': {'forbid': [0], 'pane': 'codes',
                       'when': lambda c: c.get('sms_mode') == 'teltonika',
                       'why': 'the telephone gateway\'s certificate is not checked'},
    'siem_verify': {'forbid': [0], 'pane': 'siem', 'when': lambda c: bool(c.get('siem')),
                    'why': 'the syslog server\'s certificate is not checked'},
    'siem_targets': {'pane': 'siem', 'when': lambda c: bool(c.get('siem')),
                     'test': lambda v, c: any(p != 'tls' for _h, _p, p in siem_targets(v)),
                     'why': 'syslog goes over UDP or TCP unencrypted - only tls:// servers'},
    'isemon': {'forbid': [1], 'pane': 'isemon',
               'why': 'isemon is sent plain syslog (UDP/TCP), unencrypted'},
    'debug': {'forbid': [1, True], 'pane': 'about',
              'why': 'debugging writes the details of requests into the log'},
    'totp_window': {'most': 1, 'pane': 'tokens',
                    'why': 'codes are taken more than one step (30 s) either side'},
    'totp_disallow_reuse': {'forbid': [0], 'pane': 'tokens',
                            'why': 'a code may be used again while it is good'},
}

# Advised, never stopping anything.
HISEC_ADVICE = {
    'admin_2fa': {'test': lambda v, c: not v, 'pane': 'people',
                  'why': 'the administration is opened with a password alone - a second step '
                         'from an app is advised'},
    'admin_2fa_mail': {'test': lambda v, c: bool(v) and bool(c.get('admin_2fa')), 'pane': 'people',
                       'why': 'the second step of the administration may come by mail - an app '
                              'is safer'},
    'admin_2fa_sms': {'test': lambda v, c: bool(v) and bool(c.get('admin_2fa')), 'pane': 'people',
                      'why': 'the second step of the administration may come by SMS - an app '
                             'is safer'},
    'admin_show_key': {'test': lambda v, c: bool(v), 'pane': 'tokens',
                       'why': 'administrators may show a token\'s key'},
    'portal_show_secret': {'test': lambda v, c: bool(v), 'pane': 'portal',
                           'why': 'the enrolment page shows the key as text beside the QR code'},
    'scratch_digits': {'test': lambda v, c: int(v or 0) < 10, 'pane': 'tokens',
                       'why': 'recovery codes shorter than 10 digits'},
    'mail_codes': {'test': lambda v, c: bool(v) and c.get('mail_mode') != 'off', 'pane': 'mail',
                   'why': 'codes may come by mail - weaker than an app'},
    'portal_who': {'test': lambda v, c: v == 'anyone' and bool(c.get('portal')), 'pane': 'portal',
                   'why': 'anyone in a directory may enrol on the enrolment page'},
    'session_hours': {'test': lambda v, c: int(v or 0) > 8, 'pane': 'people',
                      'why': 'a sign-in to the administration lasts more than 8 hours'},
    'session_idle_min': {'test': lambda v, c: int(v or 0) > 30, 'pane': 'people',
                         'why': 'a sign-in to the administration stays open idle more than 30 min'},
    'proxy_user': {'test': lambda v, c: bool(c.get('proxy')) and not str(v or '').strip(),
                   'pane': 'proxy', 'why': 'the proxy is used without a user name and password'},
}


def _hs_bad(rule, value, conf):
    if rule.get('when') and not rule['when'](conf):
        return False
    if 'test' in rule:
        try:
            return bool(rule['test'](value, conf))
        except (ValueError, TypeError, BadSetting):
            return True
    if 'forbid' in rule:
        return value in rule['forbid'] or (isinstance(value, bool) and int(value) in rule['forbid'])
    if 'most' in rule:
        try:
            return int(value or 0) > rule['most']
        except (TypeError, ValueError):
            return True
    return False


def hisec_setting_refused(key, value, conf=None):
    """What high security has against this value of a setting, or ''."""
    rule = HISEC_SETTINGS.get(key)
    if not rule:
        return ''
    conf = dict(CONFIG if conf is None else conf)
    conf[key] = value
    return rule['why'] if _hs_bad(rule, value, conf) else ''


def hisec_ui(key):
    """For the pages: what to grey out while it is on."""
    rule = HISEC_SETTINGS.get(key)
    if not rule:
        return None
    out = {'why': rule['why']}
    for k in ('forbid', 'most'):
        if k in rule:
            out[k] = rule[k]
    return out


def _hs_item(kind, what, fix, pane, key=''):
    return {'kind': kind, 'what': what, 'fix': fix, 'pane': pane, 'key': key}


def hisec_findings(store, conf=None):
    """{'block': [...], 'warn': [...]}: what stands against high security now."""
    conf = dict(CONFIG if conf is None else conf)
    block, warn = [], []
    for key, rule in HISEC_SETTINGS.items():
        if _hs_bad(rule, conf.get(key), conf):
            block.append(_hs_item('setting', rule['why'], NAMES.get(key, key), rule['pane'], key))
    for key, rule in HISEC_ADVICE.items():
        if _hs_bad(rule, conf.get(key), conf):
            warn.append(_hs_item('setting', rule['why'], NAMES.get(key, key), rule['pane'], key))
    # Active Directory and the other directories.
    for d in store.directories():
        if not d.get('enabled', 1):
            continue
        if d.get('tls') == 'none':
            block.append(_hs_item('dir', 'the directory %s is reached over plain LDAP - '
                                  'passwords go over the network unencrypted' % d['name'],
                                  'LDAPS or STARTTLS', 'dir'))
        elif not d.get('verify', 1):
            block.append(_hs_item('dir', 'the certificate of the directory %s is not checked'
                                  % d['name'], 'check the certificate (give its CA)', 'dir'))
        if d.get('weak'):
            block.append(_hs_item('dir', 'the directory %s is spoken to with old, weak TLS'
                                  % d['name'], 'switch the old TLS off', 'dir'))
    # RADIUS clients.
    for c in store.clients(with_secret=True):
        if len(str(c.get('secret') or '')) < 16:
            block.append(_hs_item('client', 'the shared secret of the client %s is shorter than '
                                  '16 characters' % c['name'], 'a secret of 16 characters or more',
                                  'clients'))
    # The database and the cluster.
    if conf.get('db_engine') in ('mariadb', 'postgres') and \
            str(conf.get('db_host') or '').strip() and not str(conf['db_host']).startswith('/') and \
            conf.get('db_tls') not in ('verify-ca', 'verify-full'):
        block.append(_hs_item('db', 'the database is reached without TLS that checks its '
                              'certificate', 'TLS: verify-ca or verify-full', 'db'))
    if conf.get('ha_mode') == 'replicated' and ha_link_tls(conf)[0] not in ('verify-ca', 'verify-full'):
        block.append(_hs_item('ha', 'the replication between the nodes goes without TLS that '
                              'checks the certificate', 'TLS for the replication', 'ha'))
    # Backups to other machines.
    try:
        targets = rb_targets(store)
    except Exception:                                   # noqa: BLE001
        targets = []
    for t in targets:
        if not t.get('enabled', 1):
            continue
        if t.get('kind') == 'ftp':
            block.append(_hs_item('backup', 'the backup destination %s is plain FTP - its password '
                                  'goes unencrypted' % t.get('name'), 'SFTP, SCP or FTPS', 'backup'))
        elif t.get('kind') == 'ftps' and t.get('tls_check') == 'none':
            block.append(_hs_item('backup', 'the certificate of the backup destination %s is not '
                                  'checked' % t.get('name'), 'check it: the system, a CA or a pin',
                                  'backup'))
        elif t.get('kind') == 'smb' and not t.get('smb_encrypt', 1):
            block.append(_hs_item('backup', 'the backup destination %s (SMB) is not encrypted'
                                  % t.get('name'), 'SMB encryption on', 'backup'))
    # TLS of the pages: ECDHE and AEAD only, or TLS 1.3 alone.
    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'web:tls:%'"):
        try:
            prof = json.loads(r['v'] or '{}')
        except ValueError:
            continue
        if isinstance(prof, dict) and prof.get('cert') and \
                (prof.get('preset') or 'standard') not in ('standard', 'modern'):
            block.append(_hs_item('web', 'the TLS of %s takes %s ciphers' % (
                r['k'][len('web:tls:'):], prof.get('preset')),
                'standard (ECDHE, AEAD) or modern (TLS 1.3)', 'web'))
    a = (access_conf(store) or {}).get('admin') or {'any': True}
    if a.get('any', True):
        block.append(_hs_item('fw', 'the administration can be reached from anywhere',
                              'only from the networks that need it', 'fw'))
    # SSH, as each node's sshd says it is.
    for n in host_nodes(store):
        v = (sshd_now(store, n) or {}).get('values') or {}
        if not v:
            warn.append(_hs_item('sshd', 'the SSH server of %s has not said yet how it is set' % n,
                                 'look again', 'sshd'))
            continue
        if v.get('passwordauthentication') == 'yes' or v.get('kbdinteractiveauthentication') == 'yes':
            block.append(_hs_item('sshd', 'SSH on %s lets people in with a password' % n,
                                  'keys only', 'sshd'))
        if v.get('permitrootlogin') == 'yes':
            block.append(_hs_item('sshd', 'root may sign in to %s over SSH with a password' % n,
                                  'root: with a key only, or not at all', 'sshd'))
        try:
            if int(v.get('maxauthtries') or 6) > 4:
                block.append(_hs_item('sshd', 'SSH on %s allows more than 4 tries a connection' % n,
                                      '4 tries at most', 'sshd'))
        except ValueError:
            pass
    # The security check (1.0.169): what is not as it should be now - advised,
    # never stopping high security - as the alerts see it, and the rest.
    if not fw_conf(store).get('on'):
        warn.append(_hs_item('check', 'the machine\'s firewall is off - otp\'s own rules are not '
                             'in force', 'the firewall on', 'fw'))
    try:
        targets = [t for t in rb_targets(store) if t.get('enabled')]
    except Exception:                                   # noqa: BLE001
        targets = []
    if not targets:
        warn.append(_hs_item('check', 'no backup goes to another machine', 'a destination for '
                             'the backups', 'backup'))
    elif not rb_verified(store):
        warn.append(_hs_item('check', 'no backup has been tried yet - whether one can be put '
                             'back is not known', 'Try the newest, or try them weekly', 'backup'))
    try:
        seen = alert_problems(store, 'en')
    except Exception:                                   # noqa: BLE001
        seen = {}
    for k, p in sorted(seen.items()):
        if k.split(':', 1)[0] in ('cert', 'sec', 'reboot', 'rbverify', 'rbackup'):
            warn.append(_hs_item('check', p['title'], p['said'], p.get('pane') or ''))
    return {'block': block, 'warn': warn}


class HiSecConflict(BadSetting):
    def __init__(self, findings):
        BadSetting.__init__(self, 'high security cannot be switched on, %d thing(s) stand '
                                  'against it: %s' % (len(findings['block']), '; '.join(
                                      x['what'] for x in findings['block'])))
        self.findings = findings


def hisec_guard_settings(store, checked):
    """Before settings are saved: switching it on only with nothing against
    it; while it is on, no value it stands against."""
    after = dict(CONFIG)
    after.update(checked)
    if checked.get('high_security') and not CONFIG.get('high_security'):
        got = hisec_findings(store, after)
        if got['block']:
            raise HiSecConflict(got)
    if after.get('high_security'):
        for key in HISEC_SETTINGS:
            if key in checked or any(k in checked for k in ('mail_mode', 'sms_mode', 'siem')):
                why = hisec_setting_refused(key, after.get(key), after)
                if why:
                    raise BadSetting('%s: not while high security is on - %s'
                                     % (NAMES.get(key, key), why))


def hisec_refuse(what):
    """A change of a directory, a client, a destination... while it is on."""
    if _hs_on() and what:
        raise ValueError('not while high security is on (Settings - High security): %s' % what)


def hisec_directory(row):
    if row.get('tls') == 'none':
        hisec_refuse('a directory over plain LDAP - LDAPS or STARTTLS')
    if not row.get('verify', 1):
        hisec_refuse('a directory whose certificate is not checked')
    if row.get('weak'):
        hisec_refuse('old, weak TLS to a directory')


def hisec_client_secret(secret):
    if len(str(secret or '')) < 16:
        hisec_refuse('a shared secret shorter than 16 characters')


def hisec_backup_target(t):
    if not t.get('enabled', 1):
        return
    if t.get('kind') == 'ftp':
        hisec_refuse('plain FTP - SFTP, SCP or FTPS')
    if t.get('kind') == 'ftps' and t.get('tls_check') == 'none':
        hisec_refuse('FTPS without checking the certificate')
    if t.get('kind') == 'smb' and not t.get('smb_encrypt', 1):
        hisec_refuse('SMB without encryption')


def hisec_tls(prof):
    if (prof.get('preset') or 'standard') not in ('standard', 'modern'):
        hisec_refuse('TLS other than standard (ECDHE, AEAD) or modern (TLS 1.3)')


def hisec_access(a):
    if ((a or {}).get('admin') or {'any': True}).get('any', True):
        hisec_refuse('the administration reachable from anywhere - list the networks')


def hisec_sshd(c):
    if not c.get('manage'):
        return
    if c.get('password'):
        hisec_refuse('SSH with passwords - keys only')
    if c.get('permit_root') == 'yes':
        hisec_refuse('root over SSH with a password')
    if int(c.get('tries') or 4) > 4:
        hisec_refuse('more than 4 SSH tries a connection')


def hisec_view(store):
    got = hisec_findings(store)
    return dict(got, on=_hs_on())
