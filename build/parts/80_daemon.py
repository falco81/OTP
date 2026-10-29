

# ---------------------------------------------------------------------------
# Bringing an old token server over: totpcgi and its FreeRADIUS
# ---------------------------------------------------------------------------
# The server this replaces kept a file per person (`name@realm.totp`, the
# google-authenticator format: the key, a few `" OPTION` lines, the recovery
# codes), its RADIUS clients in clients.conf, the realm a client's names
# belong to in hints, and the directory and its groups in a YAML file beside
# the Perl handler. All of it is read here so that nobody has to enrol again.

def parse_totp_file(text):
    """(secret, options, recovery codes) out of one google-authenticator file."""
    lines = [l.strip() for l in str(text or '').splitlines() if l.strip()]
    if not lines:
        raise ValueError('the file is empty')
    secret = lines[0]
    # At least 80 bits, as google-authenticator writes them (1.0.36): any
    # word at all was taken for a key, and a file of rubbish made an active
    # token with a 35-bit key.
    if len(b32_clean(secret)) < 10:
        raise ValueError('the first line is not a key of at least 16 base32 characters')
    opts, codes = {}, []
    for line in lines[1:]:
        if line.startswith('"'):
            bits = line[1:].split()
            if bits:
                opts[bits[0].upper()] = bits[1:]
        elif re.match(r'^[0-9]{6,10}\Z', line):
            codes.append(line)
    if 'HOTP_COUNTER' in opts:
        raise ValueError('a counter (HOTP) token, not a time one: it would not give the '
                         'same codes here')
    return re.sub(r'[\s\-=]', '', secret).upper(), opts, codes


TOKEN_WINDOW_MOST = 20     # the most the pages allow (1.0.101)


TOKEN_NAME_RE = re.compile(r'^[^\s@,;=\x00-\x1f\x7f]+(@[A-Za-z0-9.-]+)?\Z')


def token_name_problem(name):
    """Why `name` is not a token's name, or '' - the rule of a new token's and a
    rename's, for the imports too (1.0.146): a file '.totp' made a token with no
    name, which no page could open or take away."""
    if not name or len(name) > 180 or not TOKEN_NAME_RE.match(name):
        return ('%r is not a name: a name, or a name@realm - no spaces, commas, semicolons '
                'or =, 180 characters at most' % str(name)[:60])
    return ''


def import_totp(store, name, text, by='import', replace=False):
    """One person's token, from the old server's file. Returns what happened."""
    secret, opts, codes = parse_totp_file(text)
    name = norm_name(name)
    bad = token_name_problem(name)
    if bad:
        return 'not taken: %s' % bad
    if store.token(name) and not replace:
        return 'kept (there is a token for %s already)' % name
    window = -1
    if 'WINDOW_SIZE' in opts and opts['WINDOW_SIZE']:
        try:
            # As many steps either side as the pages allow, never more
            # (1.0.101): WINDOW_SIZE 200001 took codes from days back.
            window = min(TOKEN_WINDOW_MOST, max(0, (int(opts['WINDOW_SIZE'][0]) - 1) // 2))
        except ValueError:
            window = -1
    store.token_write(name, {
        'secret': seal_secret(secret, token_bind(name)), 'digits': 6, 'period': 30,
        'algorithm': 'SHA1',
        'window_steps': window, 'state': 'active', 'last_step': 0,
        'scratch': json.dumps([scratch_hash(name, c) for c in codes]),
        'scratch_sealed': seal_codes(codes, token_bind(name)),
        'scratch_left': len(codes), 'created': time.time(), 'created_by': by,
        'activated': time.time(), 'failures': 0, 'fail_times': '[]', 'locked_until': None,
        'pending_secret': None, 'pending_scratch': None, 'pending_at': None, 'pending_by': None,
        'issuer': str(CONFIG.get('totp_issuer') or ''), 'label': name,
        # An app's key now (1.0.146): put over a token whose codes came by
        # mail or SMS, it stayed one - sending to the old address.
        'kind': '', 'dest': '',
        'note': 'brought over from totpcgi' + ('' if 'TOTP_AUTH' in opts else
                                               ' (the file was not marked TOTP_AUTH)')})
    try:
        store.db.run('DELETE FROM meta WHERE k = ?', ('staged:' + name,))
    except Exception:                                   # noqa: BLE001
        pass
    return 'imported, %d recovery code(s)' % len(codes)


# ---- a whole backup of tokens, of every kind (1.0.96) -------------------------------
# What a token is - its key, its recovery codes (used and not), how its codes
# come (the app, mail, SMS) and where to, its language, its state - as one
# file, locked with a passphrase if one is given (the same lock as the HA
# bundle: scrypt, then a keyed stream and an HMAC). Read back on this
# server or another otp: all of them, or the ones picked. The keys are in
# it in the clear (inside the lock): the sealing key of this machine is not
# needed on the other.

TOKENS_KIND = 'otp-tokens'


def token_backup_row(tok):
    """One token as the backup keeps it, or None when its key cannot be
    opened here."""
    name = tok['name']
    kind = token_kind(tok)
    out = {'name': name, 'kind': kind, 'state': tok.get('state') or 'active'}
    if kind == 'totp':
        secret = unseal_secret(tok.get('secret') or '', token_bind(name))
        if not secret:
            return None
        out.update(secret=re.sub(r'[\s\-=]', '', str(secret)).upper(),
                   digits=int(tok.get('digits') or 6),
                   period=int(tok.get('period') or 30),
                   algorithm=str(tok.get('algorithm') or 'SHA1').upper())
    else:
        out['dest'] = tok.get('dest') or ''
    codes = open_codes(tok.get('scratch_sealed'), token_bind(name))
    out['codes'] = [{'c': c['c'], 'used': c.get('used')} for c in (codes or [])]
    if codes is None and int(tok.get('scratch_left') or 0):
        out['codes_lost'] = int(tok.get('scratch_left') or 0)
    for k in ('window_steps', 'last_step'):
        if tok.get(k) is not None:
            out[k] = int(tok.get(k))
    for k in ('lang', 'mail_fmt', 'note', 'display', 'issuer', 'label', 'created_by',
              'last_from', 'last_how'):
        if tok.get(k):
            out[k] = str(tok.get(k))
    for k in ('created', 'activated', 'last_used'):
        if tok.get(k):
            out[k] = float(tok.get(k))
    return out


def tokens_backup(store, names, by=''):
    rows, lost = [], []
    for n in names:
        tok = store.token(n)
        if not tok:
            continue
        one = token_backup_row(tok)
        if one is None:
            lost.append(n)
        else:
            rows.append(one)
    return {'kind': TOKENS_KIND, 'format': 1, 'made': time.time(), 'by': by,
            'node': node_name(), 'version': __version__, 'count': len(rows),
            'lost': lost, 'tokens': rows}


def tokens_backup_open(text, passphrase=''):
    """The backup in a file: plain, or locked (then the passphrase opens it).
    None when the file is no backup at all (a .totp file, say)."""
    try:
        got = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(got, dict) or got.get('kind') != TOKENS_KIND:
        return None
    if got.get('locked'):
        if not passphrase:
            raise PermissionError('the backup is locked: its passphrase opens it')
        got = bundle_open(got, passphrase, kinds=(TOKENS_KIND,))
    if not isinstance(got.get('tokens'), list):
        raise ValueError('the backup holds no list of tokens')
    return got


def token_restore(store, t, by='restore', replace=False):
    """One token out of a backup. Returns what happened."""
    if not isinstance(t, dict):
        raise ValueError('not a token')
    name = norm_name(t.get('name'))
    bad = token_name_problem(name)
    if bad:
        raise ValueError(bad)
    kind = str(t.get('kind') or 'totp')
    if kind not in ('totp', 'mail', 'sms'):
        raise ValueError('a kind this version does not know: %s' % kind)
    if store.token(name) and not replace:
        return 'kept (there is a token for %s already)' % name
    state = str(t.get('state') or 'active')
    if state not in ('active', 'pending', 'disabled'):
        state = 'active'
    codes = []
    for c in t.get('codes') or []:
        code = str((c or {}).get('c') if isinstance(c, dict) else c)
        if not re.fullmatch(r'[0-9]{6,10}', code):
            raise ValueError('a recovery code that is not one')
        codes.append({'c': code, 'used': (c or {}).get('used') if isinstance(c, dict) else None})
    left = [c['c'] for c in codes if not c.get('used')]
    row = {'state': state, 'kind': '' if kind == 'totp' else kind, 'dest': '',
           'scratch': json.dumps([scratch_hash(name, c) for c in left]),
           'scratch_sealed': seal_codes(codes, token_bind(name)) if codes else '',
           'scratch_left': len(left), 'failures': 0, 'fail_times': '[]', 'locked_until': None,
           'pending_secret': None, 'pending_scratch': None, 'pending_at': None,
           'pending_by': None, 'created': float(t.get('created') or time.time()),
           'created_by': str(t.get('created_by') or by)[:190],
           'activated': t.get('activated') or (time.time() if state == 'active' else None),
           'last_used': t.get('last_used'), 'last_from': str(t.get('last_from') or '')[:190],
           'last_how': str(t.get('last_how') or '')[:190],
           'note': str(t.get('note') or '')[:2000], 'display': str(t.get('display') or '')[:300],
           'issuer': str(t.get('issuer') or CONFIG.get('totp_issuer') or '')[:190],
           'label': str(t.get('label') or name)[:190],
           'lang': t.get('lang') if t.get('lang') in ('cs', 'en') else '',
           'mail_fmt': t.get('mail_fmt') if t.get('mail_fmt') in ('html', 'text') else ''}
    if kind == 'totp':
        secret = re.sub(r'[\s\-=]', '', str(t.get('secret') or '')).upper()
        try:
            if len(b32_clean(secret)) < 10:
                raise ValueError
        except ValueError:
            raise ValueError('the key is not a key of at least 16 base32 characters')
        digits, period = int(t.get('digits') or 6), int(t.get('period') or 30)
        algo = str(t.get('algorithm') or 'SHA1').upper()
        if digits not in (6, 7, 8) or not 10 <= period <= 300 or \
                algo not in ('SHA1', 'SHA256', 'SHA512'):
            raise ValueError('digits, period or algorithm this version does not take')
        row.update(secret=seal_secret(secret, token_bind(name)), digits=digits, period=period,
                   algorithm=algo, window_steps=max(-1, min(TOKEN_WINDOW_MOST, int(t['window_steps'])))
                   if t.get('window_steps') is not None else -1,
                   last_step=int(t.get('last_step') or 0))
    else:
        row.update(secret='', dest=dest_checked(kind, t.get('dest')), digits=6, period=30,
                   algorithm='SHA1', window_steps=-1, last_step=0)
    store.token_write(name, row)
    try:
        store.db.run('DELETE FROM meta WHERE k = ?', ('staged:' + name,))
    except Exception:                                   # noqa: BLE001
        pass
    return 'restored (%s, %d recovery code(s) left)' % (
        {'totp': 'the app', 'mail': 'codes by mail', 'sms': 'codes by SMS'}[kind], len(left))


def names_letters_kept(daemon):
    """Once, on the first start of a version that checks the letters of names
    (1.0.155): where tokens or accounts with accents or other languages' letters
    are there already and nobody chose either setting, they are switched on as
    those names need - so an upgrade does not shut those people out of the VPN.
    A new server starts with both off. One node of a cluster does it; the other
    gets it by replication."""
    store = daemon.store
    key = 'names:letters:checked'
    if store.get_meta(key) is not None or not ha_lead(store):
        return
    saved = store.settings_saved()
    if 'names_czsk_letters' in saved:
        store.set_meta(key, '1')
        return
    home = other = 0
    for table in ('tokens', 'accounts'):
        for r in store.db.rows('SELECT name FROM %s' % table):
            n = str(r['name'] or '')
            if all(ord(c) < 128 for c in n):
                continue
            if all(ord(c) < 128 or c in NAME_LETTERS_HOME for c in n):
                home += 1
            else:
                other += 1
    want = {}
    if other and 'names_any_letters' not in saved:
        # (1.0.154 took Czech and Slovak letters by itself, and others only
        # when names_any_letters was switched on - a choice made then stays.)
        want['names_any_letters'] = 1
    if home or (other and 'names_any_letters' in saved):
        want['names_czsk_letters'] = 1
    if want:
        daemon.save_settings(want, by='otp (upgrade)')
        store.add_event('settings', 'names with %s are here already (%d token(s) and account(s)): '
                        '%s switched on so that they still sign in - switch it off on Settings - '
                        'The tokens if they should not' % (
                            'letters of other languages' if other else 'Czech or Slovak letters',
                            home + other, ', '.join(sorted(want))), 'warn', who='otp')
    store.set_meta(key, '1')


STALE_WORK = ('otp-rbackup-', 'otp-putback-', 'otp-download-', 'otp-dl-', 'otp-peek-',
              'otp-fetch-')


def stale_work_away(older=6 * 3600):
    """What a backup, a download or a putting back left in the state folder
    when the program stopped in the middle of it (1.0.146) - a copy of the
    database, unlocked, for nobody. Hours old only: the command line may be
    at one just now."""
    try:
        items = list(STATE_DIR.iterdir())
    except OSError:
        return
    for p in items:
        if not p.name.startswith(STALE_WORK):
            continue
        try:
            if time.time() - p.lstat().st_mtime < older:
                continue
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(str(p), ignore_errors=True)
            else:
                p.unlink()
            log('left from before, taken away: %s' % p.name, 'info')
        except OSError:
            pass


def _legacy_root(root):
    root = Path(root)
    for cand in (root, root / 'otp', root / 'otp' / 'otp'):
        if (cand / 'etc' / 'raddb').is_dir() or (cand / 'etc' / 'totpcgi').is_dir():
            return cand
    raise ValueError('%s holds no etc/raddb or etc/totpcgi' % root)


def _conf_no_comments(text):
    """FreeRADIUS text without its # comments - a # inside quotes kept (1.0.146):
    secret = "has#hash" is a secret, not "has"."""
    out, quote = [], ''
    for line in str(text or '').splitlines():
        keep, i = [], 0
        while i < len(line):
            ch = line[i]
            if quote:
                keep.append(ch)
                if ch == '\\' and i + 1 < len(line):
                    keep.append(line[i + 1])
                    i += 1
                elif ch == quote:
                    quote = ''
            elif ch in '"\'':
                quote = ch
                keep.append(ch)
            elif ch == '#':
                break
            else:
                keep.append(ch)
            i += 1
        quote = ''                      # a quote never runs over a line
        out.append(''.join(keep))
    return '\n'.join(out)


def parse_clients_conf(text):
    """FreeRADIUS clients.conf as [{name, address, secret, shortname}]. Only
    what is set at the top of a client block counts: a block inside it
    (limit { ... }) is passed over (1.0.146) - it used to end the client
    there and leave its secret behind."""
    out = []
    body = _conf_no_comments(text)
    for m in re.finditer(r'(?m)^\s*client\s+(\S+)\s*\{', body):
        key, depth, i, top = m.group(1), 1, m.end(), []
        quote = ''
        while i < len(body) and depth:
            ch, was = body[i], depth
            if quote:
                if ch == '\\':
                    if depth == 1:
                        top.append(body[i:i + 2])
                    i += 2
                    continue
                if ch == quote or ch == '\n':
                    quote = ''
            elif ch in '"\'':
                quote = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if not depth:
                    break
            if depth == 1 and was == 1:
                top.append(ch)
            i += 1
        inside = ''.join(top)
        vals = {}
        for a, b in re.findall(r'^\s*([A-Za-z_0-9]+)\s*=\s*(.+?)\s*$', inside, re.M):
            b = b.strip()
            if len(b) >= 2 and b[0] == b[-1] and b[0] in '"\'':
                b = b[1:-1].replace('\\' + b[0], b[0])
            vals[a.strip().lower()] = b
        addr = vals.get('ipaddr') or vals.get('ipv4addr') or vals.get('ipv6addr') or key
        out.append({'name': vals.get('shortname') or key, 'address': addr,
                    'secret': vals.get('secret', ''),
                    'require_ma': 1 if vals.get('require_message_authenticator') == 'yes'
                    else 0})
    return out


def parse_hints(text):
    """The realm FreeRADIUS's hints file adds to names, by NAS address."""
    out = {}
    lines = str(text or '').splitlines()
    for i, line in enumerate(lines):
        m = re.match(r'^\s*DEFAULT\s+NAS-IP-Address\s*==\s*"?([0-9a-fA-F.:]+)"?', line)
        if not m:
            continue
        for nxt in lines[i + 1:i + 4]:
            r = re.search(r'User-Name\s*:?=\s*"%\{User-Name\}@([^"]+)"', nxt)
            if r:
                out[m.group(1)] = r.group(1)
                break
    return out


def parse_handler_yaml(text):
    """What the old Perl handler was told about the directory."""
    got = {'hosts': [], 'groups': []}
    in_list = None
    for raw in str(text or '').splitlines():
        line = _conf_no_comments(raw).rstrip()
        if not line.strip():
            continue
        m = re.match(r'^(\w+)\s*:\s*(.*)\Z', line.strip())
        if m and not line.startswith(' '):
            k, v = m.group(1), m.group(2).strip().strip("'\"")
            in_list = k if not v else None
            got[k] = v
            continue
        m = re.match(r'^\s*-\s*[\'"]?(.*?)[\'"]?\s*\Z', line)
        if m and in_list:
            got.setdefault(in_list + '_list', []).append(m.group(1))
    hosts = got.get('ldaphosts_list') or []
    got['hosts'] = [re.sub(r'^ldaps?://', '', h).rstrip('/') for h in hosts]
    got['tls'] = 'ldaps' if any(h.startswith('ldaps') for h in hosts) else 'none'
    groups = []
    for f in got.get('groupSearch_list') or []:
        m = re.search(r'\(cn=([^)]+)\)', f, re.I)
        if m:
            groups.append(m.group(1))
    got['groups'] = groups
    return got


def bind_tokens(store):
    """Every token's secrets sealed again tied to its name (1.0.33), where
    they were sealed the old way, without it; then the old way is no longer
    taken for a token at all. Run at start and after a restore."""
    cols = ('secret', 'pending_secret', 'scratch_sealed', 'pending_scratch')
    done = left = 0
    try:
        # ...and one never sealed at all (1.0.101): sealed now, so that from
        # here on a value not sealed is taken for no token - a row written
        # into the database (by replication, by a restore) with a key its
        # writer knows no longer opens the door.
        rows = store.db.rows("SELECT id, name, %s FROM tokens WHERE %s"
                             % (', '.join(cols), ' OR '.join(
                                 "%s LIKE 'sealed:1:%%' OR (%s <> '' AND %s NOT LIKE 'sealed:%%')"
                                 % (c, c, c) for c in cols)))
    except Exception as e:                              # noqa: BLE001
        log('the tokens could not be read to seal them again: %s' % e, 'warn')
        return
    for r in rows:
        fields = {}
        for c in cols:
            v = r.get(c)
            if isinstance(v, str) and v.startswith(SEALED):
                plain = unseal_secret(v)
                if plain is None:
                    left += 1
                    continue
                fields[c] = seal_secret(plain, token_bind(r['name']))
            elif isinstance(v, str) and v and not v.startswith('sealed:'):
                fields[c] = seal_secret(v, token_bind(r['name']))
        if fields:
            # Only if still as read: the other node may have done it already.
            sets = ', '.join('%s = ?' % c for c in fields)
            conds = ' AND '.join('%s = ?' % c for c in fields)
            store.db.run('UPDATE tokens SET %s WHERE id = ? AND %s' % (sets, conds),
                         list(fields.values()) + [r['id']] + [r[c] for c in fields])
            done += 1
    if done:
        log('%d token(s) sealed again, tied to their names' % done)
    if not left:
        BIND_STRICT['tokens'] = True
    else:
        log('%d sealed value(s) of tokens do not open with this key and were left as they are'
            % left, 'warn')


def import_legacy(store, root, by='import', replace=False, say=print):
    """Everything the old server held, into this one. Returns counts."""
    base = _legacy_root(root)
    done = collections.Counter()
    raddb = base / 'etc' / 'raddb'
    hints = parse_hints((raddb / 'hints').read_text(errors='replace')) \
        if (raddb / 'hints').exists() else {}
    realms_seen = set(hints.values())
    # ---- the directory and the realm -----------------------------------
    yaml_file = raddb / 'totpcgi-handler.yaml'
    directory = ''
    if yaml_file.exists():
        y = parse_handler_yaml(yaml_file.read_text(errors='replace'))
        if y['hosts'] and y.get('userSearchBase'):
            directory = 'AD'
            if not store.directory(directory) or replace:
                old = store.directory(directory)
                store.directory_save({
                    'id': old['id'] if old else None, 'name': directory,
                    'hosts': ', '.join(y['hosts']), 'tls': y['tls'],
                    'port': 636 if y['tls'] == 'ldaps' else 389, 'verify': 1,
                    'base': y.get('userSearchBase'), 'bind_dn': y.get('bindDN', ''),
                    'bind_pw': y.get('bindPassword', ''), 'user_attr': 'sAMAccountName',
                    'nested': 0,
                    'note': 'brought over from totpcgi-handler.yaml'}, by)
                done['directories'] += 1
                say('directory %s: %s (base %s, signing in as %s). Its certificate is '
                    'checked: import the certificate authority that signed the domain '
                    'controllers’ certificates, or switch the check off.'
                    % (directory, ', '.join(y['hosts']), y.get('userSearchBase'),
                       y.get('bindDN')))
            lookup = 'upn' if 'userPrincipalName' in str(y.get('search') or
                                                          y.get('userAttribute') or '') \
                else 'sam'
            for suffix in sorted(realms_seen) or ['*']:
                if any(str(r.get('suffix')) == suffix for r in store.realms()) and not replace:
                    continue
                old = next((r for r in store.realms() if r.get('suffix') == suffix), None)
                store.realm_save({
                    'id': old['id'] if old else None, 'name': suffix if suffix != '*'
                    else 'default', 'suffix': suffix, 'directory': directory,
                    'lookup': lookup, 'auth_mode': 'otp', 'check_disabled': 1, 'nested': 0,
                    'groups': [{'group': g, 'reply': ''} for g in y['groups']],
                    'token_name': 'whole',
                    'note': 'brought over: the code alone, then the user filter and the '
                            'group filter the old handler applied'}, by)
                done['realms'] += 1
                say('realm %s: %d group(s), looked up by %s' % (suffix, len(y['groups']),
                                                                lookup))
    # ---- the clients ---------------------------------------------------------
    if (raddb / 'clients.conf').exists():
        for c in parse_clients_conf((raddb / 'clients.conf').read_text(errors='replace')):
            try:
                net = address_net(c['address'])
            except ValueError:
                say('client %s: %r is not an address, left out' % (c['name'], c['address']))
                continue
            plain = str(net.network_address) if net.num_addresses == 1 else str(net)
            realm = hints.get(plain, '')
            if plain in ('127.0.0.1', '::1') and not realm:
                realm = hints.get('127.0.0.1', '')
            name = c['name'] if c['name'] != c['address'] else (
                'localhost' if plain == '127.0.0.1' else plain)
            old = next((x for x in store.clients() if x['name'].lower() == name.lower()), None)
            if old and not replace:
                say('client %s: there is one already, left as it is' % name)
                continue
            # Another client at the very same address (1.0.103): two of the
            # same width, the one named first wins - the NAS already here
            # would have been answered with the imported one's secret.
            same = next((x for x in store.clients() if (not old or x['id'] != old['id']) and
                         str(x.get('address') or '').strip().lower() == plain.lower()), None)
            if same:
                say('client %s: %s is the address of the client %s here already, left out'
                    % (name, plain, same['name']))
                continue
            try:
                store.client_save({'id': old['id'] if old else None, 'name': name,
                                   'address': plain, 'secret': c['secret'], 'realm': realm,
                                   'require_ma': c['require_ma'], 'enabled': 1,
                                   'note': 'brought over from clients.conf'}, by)
            except ValueError as e:
                # One client this cannot take (no secret, a name it refuses)
                # leaves the others to come over (1.0.146).
                say('client %s: left out - %s' % (name, e))
                continue
            done['clients'] += 1
            say('client %s: %s%s' % (name, plain, (', names get @' + realm) if realm else ''))
    # ---- the settings ----------------------------------------------------------
    prov = base / 'etc' / 'totpcgi' / 'provisioning.conf'
    if prov.exists():
        text = prov.read_text(errors='replace')
        def ini(key):
            m = re.search(r'^\s*%s\s*=\s*(.+?)\s*$' % key, text, re.M)
            return m.group(1) if m else None
        changes = {}
        if ini('totp_issuer'):
            changes['totp_issuer'] = ini('totp_issuer')
        if ini('window_size'):
            try:
                changes['totp_window'] = max(0, (int(ini('window_size')) - 1) // 2)
            except ValueError:
                pass
        if ini('rate_limit'):
            m = re.match(r'(\d+)\s*,\s*(\d+)', ini('rate_limit'))
            if m:
                changes['rate_limit_tries'] = int(m.group(1))
                changes['rate_limit_s'] = int(m.group(2))
        if ini('scratch_tokens_n'):
            try:
                changes['scratch_count'] = int(ini('scratch_tokens_n'))
            except ValueError:
                pass
        if realms_seen:
            r = sorted(realms_seen)[0]
            changes['portal_realm'] = r
            changes['portal_hint'] = 'login@%s' % r
        # Each one by itself, brought into the range this version takes, and
        # one saved here already kept unless --replace (1.0.103): a window of
        # 25 stopped the import half done, with no token brought over.
        saved = store.settings_saved()
        taken = {}
        for k, v in changes.items():
            if k in saved and not replace:
                say('setting %s: set here already (%s), left as it is' % (k, saved[k]))
                continue
            shape = TUNABLE.get(k)
            if isinstance(shape, tuple) and len(shape) == 2 and all(
                    isinstance(x, int) for x in shape) and isinstance(v, int):
                if not shape[0] <= v <= shape[1]:
                    say('setting %s: %s is more than this version takes - %s'
                        % (k, v, min(max(v, shape[0]), shape[1])))
                    v = min(max(v, shape[0]), shape[1])
            try:
                v = check_setting(k, v)
            except BadSetting as e:
                say('setting %s: left out (%s)' % (k, e))
                continue
            store.save_setting(k, v, by)
            CONFIG[k] = v
            taken[k] = v
            done['settings'] += 1
        if taken:
            say('settings: %s' % ', '.join('%s=%s' % kv for kv in sorted(taken.items())))
    # ---- the tokens -------------------------------------------------------------
    for folder in (base / 'etc' / 'totpcgi' / 'totp',):
        if not folder.is_dir():
            continue
        for f in sorted(folder.glob('*.totp')):
            name = f.name[:-5]
            try:
                said = import_totp(store, name, f.read_text(errors='replace'), by, replace)
                done['tokens' if said.startswith('imported') else 'tokens_kept'] += 1
            except ValueError as e:
                say('%s: %s' % (f.name, e))
                done['tokens_bad'] += 1
    loose = sorted((base / 'etc' / 'totpcgi').glob('*.totp')) \
        if (base / 'etc' / 'totpcgi').is_dir() else []
    if loose:
        say('left alone, outside the totp folder the old server read: %s'
            % ', '.join(f.name for f in loose))
    store.add_event('import', 'brought over from %s: %s' % (
        root, ', '.join('%s %d' % kv for kv in sorted(done.items())) or 'nothing'), who=by)
    return done


# ---------------------------------------------------------------------------
# Copies of the database
# ---------------------------------------------------------------------------
BACKUP_ROOM_MIN = 128 << 20


def backup_room_check(store, folder=None):
    """Room left for a copy without filling the disk (1.0.149): a full disk
    under a SQLite database refused every sign-in until space was freed.
    What the copy may take - the database file itself at most - and 128 MB
    more must stay free."""
    try:
        free = shutil.disk_usage(str(folder or BACKUP_DIR)).free
    except OSError:
        return
    size = 0
    if store.db.engine == 'sqlite':
        try:
            size = os.path.getsize(str(store.db.path))
        except (OSError, TypeError):
            size = 0
    need = size + BACKUP_ROOM_MIN
    if free < need:
        raise ValueError('there is no room for a copy in %s: %d MB free, %d MB needed so that '
                         'the disk is not filled under the database - take old copies away, '
                         'or give the disk more room' % (folder or BACKUP_DIR, free >> 20,
                                                         need >> 20))


def make_backup(store, why='by hand'):
    """A copy of everything into the backups folder - and the key that opens
    the tokens beside it, because one without the other is nothing."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_room_check(store)
    stamp_ = datetime.now().strftime('%Y%m%d-%H%M%S')
    # A name of its own (two in one second overwrote each other) and written
    # under another until it is whole (1.0.59): a half file counted as a
    # kept copy and pushed a good one out.
    # The name taken with O_EXCL (1.0.61): two processes - the daemon's
    # nightly copy and a root --backup - in the same second both saw it free.
    base = stamp_
    for suffix in [''] + ['-' + c for c in 'bcdefghijklmnopqrstuvwxyz']:
        stamp_ = base + suffix
        out = BACKUP_DIR / ('otp-%s.json.gz' % stamp_)
        try:
            os.close(os.open(str(out), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640))
            break
        except FileExistsError:
            continue
    else:
        raise ValueError('no free name for a copy in %s' % BACKUP_DIR)
    # A name nobody can have put there first, opened without following a
    # link, its mode and owner set on the open file (1.0.101): run by root
    # (--ha-resync, --backup) in a folder the service's account can write,
    # the name it wrote to was the service account's to point anywhere.
    part = BACKUP_DIR / ('.otp-%s-%s.json.gz.part' % (stamp_, secrets.token_hex(6)))
    owner = service_ids() if os.geteuid() == 0 else None
    try:
        fd = os.open(str(part), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
        os.fchmod(fd, 0o640)
        if owner:
            os.fchown(fd, owner[0], owner[1])
        with os.fdopen(fd, 'wb') as raw_f:
            dump_tables(store.db, raw_f)
        os.replace(str(part), str(out))
    except BaseException:
        try:
            out.unlink()            # the empty name taken, given back
        except OSError:
            pass
        raise
    finally:
        try:
            part.unlink()
        except OSError:
            pass
    key = sealing_key()
    if key:
        # Made by root on the command line (1.0.59): the service's own, or
        # the pages could neither list, download nor put it back.
        write_replacing(BACKUP_DIR / ('otp-%s.key' % stamp_), key.hex() + '\n', 0o600,
                        owner=owner)
    keep = int(CONFIG.get('backup_keep') or 14)
    copies = sorted(list(BACKUP_DIR.glob('otp-*.json.gz')) + list(BACKUP_DIR.glob('opt-*.json.gz')),
                    key=lambda f: f.stat().st_mtime)
    for old in copies[:-keep] if len(copies) > keep else []:
        for f in (old, old.with_name(old.name.replace('.json.gz', '.key'))):
            try:
                f.unlink()
            except OSError:
                pass
    store.add_event('backups', 'a copy of the database was made (%s): %s' % (why, out.name))
    return out


def backups():
    if not BACKUP_DIR.is_dir():
        return []
    out = []
    for f in sorted(list(BACKUP_DIR.glob('otp-*.json.gz')) + list(BACKUP_DIR.glob('opt-*.json.gz')),
                   key=lambda f: f.stat().st_mtime, reverse=True):
        st = f.stat()
        out.append({'name': f.name, 'size': st.st_size, 'at': st.st_mtime,
                    'key': f.with_name(f.name.replace('.json.gz', '.key')).exists()})
    return out


# ---------------------------------------------------------------------------
# PHP and php2shell, as the daemon can tell from outside it
# ---------------------------------------------------------------------------
# The pages say what version of PHP they run on, and a version below the
# fixed ones (8.2.35, 8.3.36, 8.4.27, 8.5.12) is "may be affected" - because a
# distribution that backported the fix keeps its old number. The packages'
# own changelog says whether the fix is in, and the daemon can read it where
# PHP cannot: so the warning on the pages goes away when the fix is there.
PHP_FIXED = {'8.2': (8, 2, 35), '8.3': (8, 3, 36), '8.4': (8, 4, 27), '8.5': (8, 5, 12)}
_PHP_STATE = {'at': 0, 'state': None}


_SOFTWARE = {'at': 0.0, 'state': None}


def _first_line(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ''
    text = (r.stdout or '') + (r.stderr or '')
    return (text.strip().splitlines() or [''])[0].strip()[:200]


def software_info(store=None):
    """What this node runs on (1.0.99): otp, its Python and the modules it
    uses, the libraries under them, the programs beside it and the system -
    for Settings → About, of every node. Asked at most once an hour."""
    if time.time() - _SOFTWARE['at'] < 3600 and _SOFTWARE['state'] is not None:
        out = dict(_SOFTWARE['state'])
    else:
        import platform
        import sqlite3
        out = {'otp': __version__,
               'python': '%s %s' % (platform.python_implementation(), platform.python_version()),
               'python_path': os.path.realpath(sys.executable),
               'openssl': ssl.OPENSSL_VERSION, 'sqlite': sqlite3.sqlite_version,
               'kernel': '%s %s' % (platform.system(), platform.release()),
               'arch': platform.machine(), 'modules': {}, 'programs': {}}
        try:
            with open('/etc/os-release', encoding='utf-8') as f:
                rel = dict(l.strip().split('=', 1) for l in f if '=' in l)
            out['os'] = rel.get('PRETTY_NAME', '').strip('"')
        except OSError:
            out['os'] = ''
        for mod, attr in (('psycopg2', '__version__'), ('pymysql', '__version__'),
                          ('colorama', '__version__')):
            try:
                m = __import__(mod)
                v = str(getattr(m, attr, '') or '').split(' ')[0]
                if mod == 'psycopg2':
                    lib = getattr(m, '__libpq_version__', 0)
                    if lib:
                        v += ' (libpq %d.%d)' % (lib // 10000, lib % 10000 // 100 if lib < 100000
                                                 else lib % 100)
                out['modules'][mod] = v
            except Exception:                           # noqa: BLE001
                out['modules'][mod] = ''
        progs = (('nginx', ['nginx', '-v']), ('php', ['php', '-v']),
                 ('php-fpm', None), ('keepalived', ['keepalived', '--version']),
                 ('pg_dump', ['pg_dump', '--version']),
                 ('mariadb-dump', ['mariadb-dump', '--version']),
                 ('openssl', ['openssl', 'version']), ('systemd', ['systemctl', '--version']),
                 ('iptables', ['iptables', '--version']),
                 ('firewalld', ['firewall-cmd', '--version']))
        for name, cmd in progs:
            if name == 'php-fpm':
                import glob
                fpm = sorted(glob.glob('/usr/sbin/php-fpm*') + glob.glob('/usr/sbin/php*-fpm*'))
                line = _first_line([fpm[-1], '-v']) if fpm else ''
            else:
                exe = shutil.which(cmd[0]) or next((p for p in ('/usr/sbin/' + cmd[0], '/sbin/' + cmd[0])
                                                    if os.path.exists(p)), None)
                line = _first_line([exe] + cmd[1:]) if exe else ''
            m = re.search(r'(\d+\.\d+(?:\.\d+)?[^\s,()]*)', line or '')
            if m and not re.search(r'(?i)denied|not found|error', line):
                out['programs'][name] = m.group(1)
            elif name == 'systemd':
                m = re.search(r'^systemd\s+(\d+)', line or '')
                if m:
                    out['programs'][name] = m.group(1)
        _SOFTWARE.update(at=time.time(), state=dict(out))
    # What changes without a restart, asked each time it is wanted.
    if store is not None:
        try:
            out['database'] = store.db.version() or ''
        except Exception:                               # noqa: BLE001
            pass
    try:
        out['php_cli'] = (php_state() or {}).get('version') or ''
    except Exception:                                   # noqa: BLE001
        pass
    return out


def php_state():
    if time.time() - _PHP_STATE['at'] < 3600 and _PHP_STATE['state'] is not None:
        return _PHP_STATE['state']
    out = {'version': '', 'fixed': None, 'how': ''}
    php = shutil.which('php') or next((p for p in ('/usr/bin/php', '/usr/local/bin/php')
                                       if os.path.exists(p)), None)
    if php:
        try:
            out['version'] = subprocess.run([php, '-r', 'echo PHP_VERSION;'], capture_output=True,
                                            text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    m = re.match(r'^(\d+)\.(\d+)\.(\d+)', out['version'])
    if m:
        v = tuple(int(x) for x in m.groups())
        want = PHP_FIXED.get('%d.%d' % v[:2])
        if want and v >= want or (not want and v[:2] > (8, 5)):
            out.update(fixed=True, how='version')
    if not out['fixed']:
        said = ''
        rpm = shutil.which('rpm')
        if rpm:
            for pkg in ('php-fpm', 'php-common'):
                try:
                    said += subprocess.run([rpm, '-q', '--changelog', pkg], capture_output=True,
                                           text=True, timeout=20).stdout
                except (OSError, subprocess.SubprocessError):
                    pass
        else:
            import gzip
            import glob
            for f in glob.glob('/usr/share/doc/php*-fpm/changelog.Debian.gz') + glob.glob(
                    '/usr/share/doc/php*-common/changelog.Debian.gz'):
                try:
                    with gzip.open(f, 'rt', errors='replace') as g:
                        said += g.read(200000)
                except OSError:
                    pass
        if 'CVE-2026-109618' in said:
            out.update(fixed=True, how='changelog')
        elif out['version']:
            out['fixed'] = False
    _PHP_STATE.update(at=time.time(), state=out)
    return out


# ---------------------------------------------------------------------------
# The daemon
# ---------------------------------------------------------------------------
class Daemon(object):
    def __init__(self, store, serve=True):
        self.store = store
        # RADIUS on a connection of its own (1.0.136) - the serving daemon
        # only; the command line keeps its one.
        if serve:
            store.db.lanes_on = True
        self._reader = None
        self._reader_lock = threading.Lock()
        self.started = time.time()
        self.stop_flag = threading.Event()
        self.shipper = None
        self.dirs = {}
        self.reload_directories()
        self.tokens = Tokens(store)
        self.auth = Authenticator(store, self.tokens, self.dirs)
        self.radius = None
        self.api = None
        self.serial = 0
        self.conf_serial = store.get_meta('conf_serial', '0')
        self.login_fails = collections.defaultdict(list)
        # What each count is (1.0.112): its limit, how long it lasts, and the
        # names tried from an address / the addresses a name was tried from -
        # for Settings - Accounts - Locked out.
        self.login_info = {}
        if serve:
            self.shipper = Shipper()
            self.tokens.on_check = self.shipper.token_line
            store.on_event = self.shipper.event_line
            self.radius = RadiusServer(self)

    def reload_directories(self):
        self.store._dirs = None
        fresh = {}
        for row in self.store.directories(with_secret=True):
            if row.get('enabled', 1):
                fresh[row['name'].lower()] = Directory(row)
        # Swapped in whole (1.0.44): emptied and filled again, a request in
        # between found no directory at all.
        self.dirs = fresh
        if getattr(self, 'auth', None) is not None:
            self.auth.dirs = fresh

    def fill_names(self, names=None, limit=500, by='', quiet=False):
        """The name a person goes by, from the directory, for the tokens that
        have none - those brought over from totpcgi or made here, which an
        enrolment on the pages would have given one. Each token's own realm
        says which directory to ask and how to look the name up. (1.0.14)"""
        done = {'filled': 0, 'not_found': 0, 'no_directory': 0, 'trouble': 0}
        dead = set()
        if names is None:
            rows = self.store.db.rows("SELECT name FROM tokens WHERE COALESCE(display, '') = '' "
                                      "ORDER BY id LIMIT %d" % int(limit))
            names = [r['name'] for r in rows]
        for name in names:
            realm = self.store.realm_for(name)
            ad = self.dirs.get(str((realm or {}).get('directory') or '').lower())
            if not realm or not ad:
                done['no_directory'] += 1
                continue
            lookup = realm.get('lookup') or ''
            if lookup not in ('upn', 'sam'):
                lookup = 'upn' if '@' in name else 'sam'
            if ad.name in dead:
                done['trouble'] += 1
                continue
            try:
                entry = ad.find_user(name, lookup)
            except Exception:                           # noqa: BLE001
                # Not reached: the rest of its tokens are not asked of it now
                # - every one would wait out the same timeout.
                dead.add(ad.name)
                done['trouble'] += 1
                continue
            if not entry or not entry.get('display'):
                done['not_found'] += 1
                continue
            # Only a token still there (1.0.59): token_write made a deleted
            # one again, empty, when it was taken away meanwhile.
            if self.store.db.run('UPDATE tokens SET display = ? WHERE name = ?',
                                 (str(entry['display'])[:300], name)):
                done['filled'] += 1
        if (done['filled'] or by) and not quiet:
            self.store.add_event('tokens', 'names from the directory: %d token(s) given their '
                                 'owner\'s name, %d not found, %d with no directory, %d could not '
                                 'be asked' % (done['filled'], done['not_found'],
                                               done['no_directory'], done['trouble']),
                                 who=by or None)
        return done

    def fill_names_later(self, names=None, by=''):
        threading.Thread(target=lambda: self.fill_names(names, by=by), name='fill-names',
                         daemon=True).start()

    RELOAD_LOCK = threading.RLock()

    def reload_all(self, why=''):
        """Everything read again from the database: the settings, the
        clients, the realms, the directories. One at a time (1.0.94): a save
        on the pages and the loop's own both opened the RADIUS sockets."""
        with self.RELOAD_LOCK:
            return self._reload_all(why)

    def _reload_all(self, why=''):
        load_config(saved=self.store.settings_saved())
        if not BIND_STRICT.get('tokens'):
            bind_tokens(self.store)
        self.store._clients = None
        self.store._realms = None
        self.reload_directories()
        if self.shipper:
            self.shipper.configure()
        if self.radius:
            self.radius.open_sockets()
        self.conf_serial = self.store.get_meta('conf_serial', '0')
        if why:
            log('read the configuration again (%s)' % why)

    def changed(self, what=''):
        """Something the other processes (the command line) must notice."""
        try:
            # A mark of its own, not a count: two nodes counting up at the
            # same moment would write the same number, and neither would
            # see that the other changed something. (1.0.14)
            mark = '%.6f:%s' % (time.time(), node_name())
            self.store.set_meta('conf_serial', mark)
            self.conf_serial = mark
        except Exception:
            pass
        self.store._clients = None
        self.store._realms = None
        if what in ('directories', 'all'):
            self.reload_directories()

    # ---- settings ---------------------------------------------------------------
    def cluster_nodes(self):
        try:
            return [n['name'] for n in ha_nodes(self.store)]
        except Exception:                               # noqa: BLE001
            return [node_name()]

    def save_settings(self, changes, by='', node=None, drawn_by=None):
        checked = {}
        # The page's boxes were drawn by one node and the save reached
        # another through the web address (1.0.110): otp1 took otp2's name
        # from a page otp2 had drawn. What belongs to one machine is saved
        # only on the machine the page was drawn by.
        drawn_by = str(drawn_by or '').strip()
        if drawn_by and drawn_by != node_name():
            local = sorted(k for k in (changes or {}) if k in FILE_ONLY_KEYS and
                           not (k in SECRET_KEYS and is_masked(changes[k])))
            if local:
                raise NodeMoved('this page was drawn by %s, but %s answers now (the web address '
                                'moved): %s belongs to one machine, so nothing was saved - load '
                                'the page again' % (drawn_by, node_name(), ', '.join(local)))
            if node is None:
                node = drawn_by
        # In a cluster a node's own settings go to that node alone (1.0.37).
        many = bool(CONFIG.get('ha_mode')) or len(self.cluster_nodes()) > 1
        node = str(node or node_name())
        # '*': the cluster's own value of a node's setting (1.0.67) - the one
        # every node takes that has none of its own. It could not be changed
        # from the pages at all in a cluster.
        cluster_wide = node == '*'
        if cluster_wide:
            node = node_name()
        if node not in self.cluster_nodes() + [node_name()]:
            raise BadSetting('there is no node %s' % node)
        for key, value in (changes or {}).items():
            if key in SECRET_KEYS and is_masked(value):
                continue
            checked[key] = check_setting(key, value)
            # A secret kept in the database is sealed with the tokens' key
            # (1.0.20): a copy of the database alone does not give it away.
            if key in SEALED_KEYS and checked[key]:
                checked[key] = seal_secret(checked[key])
        if 'node_name' in checked:
            taken = node_name_taken(self.store, checked['node_name'])
            if taken:
                raise BadSetting('node_name: %s is the name of another node (%s, answering now) - '
                                 'two machines with one name look like one, and the other as '
                                 'gone' % (checked['node_name'], taken.get('address') or '?'))
        file_side = {k: v for k, v in checked.items() if k in FILE_ONLY_KEYS}
        if file_side and node != node_name() and not cluster_wide:
            raise NodeMoved('%s belongs to the machine %s and is saved on it (its own address), '
                            'not from %s' % (', '.join(sorted(file_side)), node, node_name()))
        db_side = {k: v for k, v in checked.items() if k not in FILE_ONLY_KEYS}
        saved_now = self.store.settings_saved()
        for k, v in db_side.items():
            if k in NODE_KEYS and many and not cluster_wide:
                shared = saved_now.get(k, FILE_CONFIG.get(k, DEFAULTS[k]))
                if v == shared:
                    self.store.drop_setting(k + '@' + node)
                else:
                    self.store.save_setting(k + '@' + node, v, by)
                continue
            if v == FILE_CONFIG.get(k, DEFAULTS[k]):
                self.store.drop_setting(k)
            else:
                self.store.save_setting(k, v, by)
        said = []
        if file_side:
            if any(k in DB_KEYS for k in file_side) and (
                    file_side.get('db_engine', CONFIG.get('db_engine')) != 'sqlite' or
                    CONFIG.get('db_engine') != 'sqlite'):
                test = dict(CONFIG)
                test.update(file_side)
                try:
                    probe = open_db(test)
                    probe.make_tables()
                    probe.close()
                except Exception as e:
                    raise BadSetting('the database could not be used, so nothing was '
                                     'changed: %s' % e)
            write_file_settings(file_side)
            said.append('the database settings go into %s and take effect when the service '
                        'is restarted (systemctl restart otp)' % CONFIG_FILE)
        # Who may sign in from the directory changed (1.0.33): everybody
        # signed in from it is signed out, so their role is decided again by
        # the groups as they are now - not kept until their session ends.
        if any(k in checked for k in ('admin_directory', 'admin_group_full',
                                      'admin_group_token', 'admin_group_readonly')):
            try:
                self.store.db.run(
                    "DELETE FROM sessions WHERE kind = 'admin' AND LOWER(name) IN "
                    "(SELECT LOWER(name) FROM accounts WHERE source = 'directory')")
            except Exception as e:                      # noqa: BLE001
                log('the directory sign-ins could not be ended: %s' % e, 'warn')
        if checked:
            self.store.add_event('settings', 'changed: %s' % ', '.join(
                '%s%s=%s' % (k, ('@' + node) if (k in NODE_KEYS and many and not cluster_wide)
                             else '',
                         '***' if k in SECRET_KEYS else json.dumps(v, ensure_ascii=False))
                for k, v in sorted(checked.items())), who=by)
        self.changed('settings')
        self.reload_all()
        return {'message': ' '.join(['%d setting(s) saved.' % len(checked)] + said),
                'saved': sorted(checked)}

    def settings_state(self, may_change=True):
        out = []
        saved = self.store.settings_saved()
        written = self.store.settings_written()
        for key in DEFAULTS:
            if key in ('ha_mode', 'ha_slot', 'ha_peer', 'ha_peer_port', 'ha_address', 'ha_tls',
                       'ha_tls_ca'):
                continue                    # the cluster's own wiring, set by its wizard
            value = CONFIG.get(key)
            shape = TUNABLE.get(key)
            source = 'saved' if key in saved else ('file' if key in FILE_KEYS else 'default')
            one = {'key': key, 'value': value, 'default': DEFAULTS[key],
                   'name': NAMES.get(key, key), 'says': SAYS.get(key, ''),
                   'short': SAYS_SHORT.get(key, ''),
                   'secret': key in SECRET_KEYS, 'source': source,
                   'source_says': {'saved': 'saved on these pages',
                                   'file': 'from config.json',
                                   'default': 'the built-in default'}[source],
                   'in_file': key in FILE_KEYS,
                   'file': FILE_CONFIG.get(key) if key in FILE_KEYS else None,
                   'file_only': key in FILE_ONLY_KEYS,
                   'node_key': key in NODE_KEYS}
            if key in NODE_KEYS:
                one['per_node'] = {k.split('@', 1)[1]: v for k, v in saved.items()
                                   if k.startswith(key + '@')}
                one['shared'] = saved.get(key, FILE_CONFIG.get(key, DEFAULTS[key]))
                if key + '@' + node_name() in saved:
                    one['source'], one['source_says'] = 'node', 'saved for this node'
            if key in written:
                one['saved_at'] = written[key]['at']
                one['saved_by'] = written[key]['by']
            if key in SECRET_KEYS:
                plain = unseal_secret(value) if key in SEALED_KEYS else value
                one['value'] = secret_shown(plain or '') if may_change else ''
                one['set'] = bool(value)
                one['file'] = None
            if isinstance(shape, tuple) and shape and isinstance(shape[0], str):
                one['choices'] = list(shape)
                if key in CHOICE_WORDS:
                    one['choice_words'] = CHOICE_WORDS[key]
            elif isinstance(shape, tuple):
                one['min'], one['max'] = shape
            out.append(one)
        return out

    # ---- what it is doing ------------------------------------------------------
    def status(self):
        c = self.store.token_counts()
        last = self.store.db.row("SELECT ts, result, username FROM radius_log WHERE packet = "
                                 "'Access-Request' ORDER BY ts DESC LIMIT 1")
        day = time.time() - 86400
        acc = int(self.store.db.value("SELECT COUNT(*) AS n FROM radius_log WHERE ts >= ? AND "
                                      "result = 'accept'", (day,), 0) or 0)
        rej = int(self.store.db.value("SELECT COUNT(*) AS n FROM radius_log WHERE ts >= ? AND "
                                      "result IN ('reject', 'drop')", (day,), 0) or 0)
        serial = self.store.db.value('SELECT MAX(id) AS n FROM radius_log', (), 0) or 0
        ev = self.store.db.value('SELECT MAX(id) AS n FROM events', (), 0) or 0
        r = self.radius.state() if self.radius else {}
        problems = []
        if self.radius and self.radius.trouble:
            problems.append(self.radius.trouble)
        if self.radius and not self.radius.bound:
            problems.append('the RADIUS server is not listening')
        sh = self.shipper.state() if self.shipper else {}
        if sh.get('on') and not sh.get('targets'):
            problems.append('sending to isemon is on and nowhere to send to is set')
        if sh.get('trouble'):
            problems.extend('isemon %s: %s' % kv for kv in sorted(sh['trouble'].items()))
        lost = int(self.store.db.value('SELECT COUNT(*) AS n FROM tokens', (), 0) or 0) and \
            not sealing_key()
        if lost:
            problems.append('the key that opens the tokens (%s) is missing: no code can be '
                            'checked' % sealing_key_path())
        if name_clash_words():
            problems.insert(0, name_clash_words())
        try:
            if ntp_problem():
                problems.append(ntp_problem())
        except Exception:                               # noqa: BLE001
            pass
        try:
            trials = trials_view(self.store)
        except Exception:                               # noqa: BLE001
            trials = []
        if not self.store.clients():
            problems.append('there is no RADIUS client yet: nobody can ask this server')
        if not self.store.realms():
            problems.append('there is no realm yet: every request is refused')
        return {
            'ok': True, 'version': __version__, 'site': CONFIG.get('site_name') or short_host(),
            'host': socket.gethostname(), 'started': self.started,
            'uptime': time.time() - self.started, 'now': time.time(),
            'radius': r, 'isemon': sh, 'tokens': c,
            'clients': len(self.store.clients()), 'realms': len(self.store.realms()),
            'directories': len(self.dirs),
            'day': {'accept': acc, 'reject': rej},
            'last': last, 'serial': '%s/%s' % (serial, ev), 'problems': problems,
            'database': {'engine': self.store.db.engine, 'where': self.store.db.where()},
            'lang': CONFIG.get('ui_lang') or 'cs', 'php': php_state(), 'admin_show_key': bool(CONFIG.get('admin_show_key')),
            'default_realm': CONFIG.get('default_realm') or '',
            'node': node_name(),
            'nodes': [{'name': n['name'], 'alive': n['alive'], 'age': n['age'],
                       'version': n.get('version')} for n in ha_nodes(self.store)],
            'realm_suffixes': sorted(set(r['suffix'] for r in self.store.realms()
                                         if r.get('suffix') and r['suffix'] != '*')),
            # The overview's second row of cards (1.0.37): this server, the
            # cluster, the database, maintenance.
            'maintenance': maintenance_now(self.store),
            'maint_nodes': [n['name'] for n in ha_nodes(self.store)
                            if n.get('alive') and maintenance_row(self.store, n['name']).get('on')],
            'replication': self._repl_summary(),
            'db': self._db_summary(),
            'upgrade': self._upgrade_summary(),
            'trials': trials,
        }

    def _repl_summary(self):
        if CONFIG.get('ha_mode') != 'replicated':
            return {'mode': CONFIG.get('ha_mode') or ''}
        try:
            r = ha_repl_state(self.store)
            return {'mode': 'replicated', 'healthy': bool(r.get('healthy')),
                    'lost': bool(r.get('lost')), 'trouble': r.get('trouble') or '',
                    'behind': max([int(x.get('behind') or 0) for x in r.get('outgoing') or []]
                                  or [0])}
        except Exception as e:                          # noqa: BLE001
            return {'mode': 'replicated', 'healthy': False, 'trouble': str(e)[:200]}

    DB_SUMMARY = {'at': 0, 'got': {}}

    def _db_summary(self):
        if time.time() - self.DB_SUMMARY['at'] > 60:
            got = {'engine': self.store.db.engine, 'where': self.store.db.where()}
            try:
                got['size'] = self.store.db.size()
            except Exception:                           # noqa: BLE001
                got['size'] = None
            try:
                kept = backups()
                got['backups'] = len(kept)
                # The nightly dumps count as a copy too (1.0.59): they are
                # kept in their own folder, and only the copies were looked at.
                try:
                    kept = kept + kept_dumps(self.store.db.engine)
                except Exception:                       # noqa: BLE001
                    pass
                got['last_backup'] = max([float(b.get('at') or b.get('mtime') or 0)
                                          for b in kept] or [0]) or None
            except Exception:                           # noqa: BLE001
                pass
            got['key_there'] = bool(sealing_key())
            self.DB_SUMMARY.update(at=time.time(), got=got)
        return self.DB_SUMMARY['got']

    def _upgrade_summary(self):
        try:
            plan = upgrade_plan(self.store)
            pkg = json.loads(self.store.get_meta('upgrade:pkg') or 'null')
        except Exception:                               # noqa: BLE001
            return {}
        return {'plan': {'state': plan['state'], 'version': plan['version']} if plan else None,
                'package': pkg['version'] if pkg else None}

    # ---- running -------------------------------------------------------------------
    def run(self):
        log('otp %s starting: the database is %s' % (__version__, self.store.db.where()))
        try:
            downgrade_floor_note(self.store)        # how far back it may go (1.0.143)
        except Exception as e:                      # noqa: BLE001
            log('the floor for going back could not be written: %s' % e, 'warn')
        stale_work_away()
        try:
            names_letters_kept(self)
        except Exception as e:                      # noqa: BLE001
            log('the letters names take could not be looked at: %s' % e, 'warn')
        if not sealing_key():
            # A database that already holds sealed secrets gets no new key in
            # place of a missing one (1.0.33): the secrets would stay lost, and
            # on two nodes each would seal with a key of its own.
            held = 0
            try:
                held = int(self.store.db.value(
                    "SELECT COUNT(*) FROM tokens WHERE secret LIKE 'sealed:%'", (), 0) or 0)
            except Exception:                           # noqa: BLE001
                pass
            if held:
                log('%s is missing, and the database holds %d token(s) sealed with it: no new '
                    'key is made. Put the key back (it is beside every backup), or the tokens '
                    'cannot be opened.' % (sealing_key_path(), held), 'error')
                self.store.add_event('starting and stopping', 'the key that opens the tokens '
                                     'is missing: %s' % sealing_key_path(), 'bad')
            else:
                sealing_key(make=True)
        else:
            bind_tokens(self.store)
        if CONFIG.get('ha_mode') == 'replicated':
            # The other node's tables given the columns this version adds
            # (1.0.76): logical replication sends every column of a row, and
            # one the other node does not have yet stopped what goes to it
            # until it was upgraded too. Old code there never reads them.
            threading.Thread(target=ha_peer_columns, name='peer-columns', daemon=True).start()
        self.radius.start()
        self.api = ApiServer(self)
        self.api.start()
        HA_STORE['store'] = self.store
        node_name_check(self.store)             # renamed since the last start? (1.0.48)
        self.store.add_event('starting and stopping', 'otp %s started on %s, RADIUS on %s'
                             % (__version__, node_name(),
                                ', '.join(self.radius.bound) or 'nothing'))
        try:
            heartbeat(self.store, self)
        except Exception as e:                          # noqa: BLE001
            log('the heartbeat could not be written: %s' % e, 'warn')
        last_beat = time.monotonic()    # a clock stepped back stops nothing (1.0.94)
        maintenance_ensure(self.store)
        # Tests the other node's pages ask of this one (1.0.45): looked for
        # every half second, only while this node is one of a cluster.
        def tests_for_me():
            while not self.stop_flag.wait(1.5):
                if not CONFIG.get('ha_mode') or HA_REBUILDING.is_set():
                    continue
                try:
                    radtest_serve(self)
                except Exception as e:                  # noqa: BLE001
                    log('a test asked by the other node: %s' % e, 'warn')
                    self.stop_flag.wait(5)
        threading.Thread(target=tests_for_me, name='tests-for-me', daemon=True).start()

        # The outgoing mail (1.0.95): what was not taken yet, tried again.
        def mail_queue():
            while not self.stop_flag.wait(10):
                if HA_REBUILDING.is_set():
                    continue
                try:
                    mailq_tick(self.store)
                except Exception as e:                  # noqa: BLE001
                    log_sparing('mail-queue', 'the outgoing mail: %s' % e, 'warn', every=300)
        threading.Thread(target=mail_queue, name='mail-queue', daemon=True).start()
        # The cluster's web address: whether this node may hold it (1.0.47).
        threading.Thread(target=vip_watch, args=(self,), name='vip-watch', daemon=True).start()
        try:
            upgrade_tick(self)
        except Exception as e:                          # noqa: BLE001
            log_sparing('tick:upgrade:' + str(e)[:80], 'the upgrade: %s' % e, 'warn', 3600)
        signal.signal(signal.SIGTERM, lambda *_: self.stop_flag.set())
        signal.signal(signal.SIGINT, lambda *_: self.stop_flag.set())
        # Only noted in the handler (1.0.94): read again in this loop, not in
        # the middle of whatever the main thread was doing - a log line
        # holding its lock, a query on the connection - every night when
        # logrotate reloads.
        self.hup_asked = threading.Event()
        signal.signal(signal.SIGHUP, lambda *_: self.hup_asked.set())
        last_tidy = time.monotonic() - 3601
        last_backup_day = self.store.get_meta('backup_day', '')
        while not self.stop_flag.wait(5):
            if self.hup_asked.is_set():
                self.hup_asked.clear()
                self._hup()
            if HA_REBUILDING.is_set():
                continue                # nothing of its own written meanwhile (1.0.44)
            try:
                # Each on its own (1.0.136): one of these breaking skipped
                # everything after it - the backups, the time, the tidying -
                # with a traceback every 5 s.
                try:
                    if time.monotonic() - last_beat >= HEARTBEAT_S:
                        last_beat = time.monotonic()
                        heartbeat(self.store, self)
                    elif CONFIG.get('ha_mode'):
                        try:
                            fw_now_publish(self.store)  # asked by the other node (1.0.71)
                        except Exception:               # noqa: BLE001
                            pass
                except DbError:
                    raise
                except Exception as e:                  # noqa: BLE001
                    log_sparing('heartbeat-tick', 'the heartbeat: %s\n%s' % (
                        e, traceback.format_exc()), 'error', every=600)
                try:
                    if self.store.get_meta('conf_serial', '0') != self.conf_serial:
                        self.reload_all('changed elsewhere')
                except DbError:
                    raise
                except Exception as e:                  # noqa: BLE001
                    log_sparing('reload-tick', 'reading the settings again: %s\n%s' % (
                        e, traceback.format_exc()), 'error', every=600)
                try:
                    upgrade_tick(self)
                except Exception as e:                  # noqa: BLE001
                    log_sparing('tick:upgrade:' + str(e)[:80], 'the upgrade: %s' % e, 'warn', 3600)
                try:
                    web_tick(self.store)
                except Exception as e:                  # noqa: BLE001
                    log_sparing('tick:web:' + str(e)[:80], 'TLS and the web address: %s' % e, 'warn', 3600)
                try:
                    rb_tick(self)               # backups to the destinations (1.0.109)
                except Exception as e:          # noqa: BLE001
                    log_sparing('rbackup-tick', 'the scheduled backup: %s' % e, 'warn', every=600)
                if CONFIG.get('ha_mode') == 'replicated':
                    try:
                        hatls_tick(self.store)  # the link between the databases (1.0.104)
                    except Exception as e:      # noqa: BLE001
                        log_sparing('hatls-tick', 'the link between the databases: %s' % e,
                                    'warn', every=600)
                    try:
                        readdress_dropold_tick(self.store)  # a new address kept (1.0.137)
                    except Exception as e:      # noqa: BLE001
                        log_sparing('dropold-tick', 'the other node\'s old address: %s' % e,
                                    'warn', every=600)
                    try:
                        readdress_tick(self.store, self)    # told a new address (1.0.106)
                    except Exception as e:      # noqa: BLE001
                        log_sparing('tick:readdress:' + str(e)[:80], 'a new address of the cluster: %s' % e, 'warn', 3600)
                try:
                    online_tick(self)           # a new version on the web (1.0.123)
                except Exception as e:          # noqa: BLE001
                    log_sparing('online-tick', 'a new version: %s' % e, 'warn', every=3600)
                try:
                    fw_trial_tick(self.store)   # a firewall change not kept (1.0.137)
                except Exception as e:          # noqa: BLE001
                    log_sparing('fw-trial-tick', 'the firewall on trial: %s' % e, 'warn',
                                every=600)
                try:
                    ntp_tick(self)              # the time (1.0.120)
                except Exception as e:          # noqa: BLE001
                    log_sparing('ntp-tick', 'the time: %s' % e, 'warn', every=600)
                try:
                    console_login_tick(self)    # the console at login (1.0.141)
                except Exception as e:          # noqa: BLE001
                    log_sparing('console-tick', 'the console at login: %s' % e, 'warn',
                                every=600)
                try:
                    sshkeys_tick(self)          # root's SSH keys (1.0.158)
                except Exception as e:          # noqa: BLE001
                    log_sparing('sshkeys-tick', 'root\'s SSH keys: %s' % e, 'warn', every=600)
                try:
                    osup_tick(self)             # the updates of the system (1.0.158)
                except Exception as e:          # noqa: BLE001
                    log_sparing('osup-tick', 'the update of the system: %s' % e, 'warn',
                                every=600)
                try:
                    net_tick(self)              # the network, restart, power off (1.0.119)
                except Exception as e:          # noqa: BLE001
                    log_sparing('net-tick', 'the network: %s' % e, 'warn', every=600)
                try:
                    lockouts_tick(self)         # who is locked out, for the pages (1.0.112)
                except Exception as e:          # noqa: BLE001
                    log_sparing('lockouts-tick', 'the list of who is locked out: %s' % e,
                                'warn', every=600)
                try:
                    ha_watch_tick(self.store)
                except Exception as e:                  # noqa: BLE001
                    log_sparing('tick:ha_watch:' + str(e)[:80], 'the cluster\'s history: %s' % e, 'warn', 3600)
                if time.monotonic() - last_tidy > 3600:
                    last_tidy = time.monotonic()
                    # In a thread of its own (1.0.57): long directory lookups
                    # and a big first tidy held the heartbeat back, and the
                    # other node took this one for gone.
                    self.background('tidy', self.hourly)
                if CONFIG.get('backup_daily'):
                    today = datetime.now().strftime('%Y-%m-%d')
                    # 3:30 is 03:30 (1.0.44): compared as numbers, not as text.
                    try:
                        hh, mm = (int(x) for x in str(CONFIG.get('backup_at') or '03:30')
                                  .strip().split(':', 1))
                    except ValueError:
                        hh, mm = 3, 30
                    nw = datetime.now()
                    if today != last_backup_day and (nw.hour, nw.minute) >= (hh, mm):
                        # One node of a cluster makes it: the one whose
                        # conditional UPDATE took the day. (1.0.13) The day
                        # counts as done only once that was asked (1.0.94):
                        # a database away just then lost the day's copy.
                        mine = claim_once(self.store, 'backup_day' + (
                            ':' + node_name() if CONFIG.get('ha_mode') == 'replicated' else ''),
                            today)
                        last_backup_day = today
                    else:
                        mine = False
                    if mine:
                        self.background('dump', self.nightly)
            except DbError as e:
                # The database away is said once in a while, not with a
                # traceback every 5 seconds (1.0.59).
                log_sparing('housekeeping-db', 'housekeeping waits for the database: %s'
                            % str(e).split('\n')[0][:200], 'error', every=60)
            except Exception as e:
                log('housekeeping broke: %s\n%s' % (e, traceback.format_exc()), 'error')
        try:
            self.store.add_event('starting and stopping', 'otp stopped on %s' % node_name())
        except Exception:                               # noqa: BLE001
            pass                # the database away: the rest still stops cleanly (1.0.94)
        self.radius.stop()
        if self.shipper:
            self.shipper.flush()
        if self.api:
            self.api.stop()

    def background(self, name, fn):
        """`fn` in a thread of its own, never two of one name at once."""
        busy = getattr(self, '_bg', None)
        if busy is None:
            busy = self._bg = {}
        t = busy.get(name)
        if t is not None and t.is_alive():
            return
        t = threading.Thread(target=fn, name='otp-' + name, daemon=True)
        busy[name] = t
        t.start()

    def reader(self):
        """The database as the pages' long lists read it (1.0.101): the Log
        searched over months, the suggestions under a search box - on a
        connection of their own, with a limit of 20 s a statement. On the one
        every sign-in shares, four such searches at once held RADIUS for
        seconds and the health check failed."""
        main = self.store.db
        if main.engine == 'sqlite':
            return self.store
        with self._reader_lock:
            r = self._reader
            if r is not None and r.db.where() != main.where():
                try:
                    r.db.close()
                except Exception:                       # noqa: BLE001
                    pass
                r = self._reader = None
            if r is None:
                try:
                    r = self._reader = Storage.view(
                        db_open({k: CONFIG.get(k) for k in DB_KEYS}, statement_s=20))
                except Exception as e:                  # noqa: BLE001
                    log_sparing('reader-db', 'the lists of the pages read through the shared '
                                'connection: their own could not be opened (%s)'
                                % str(e).split('\n')[0][:200], 'warn')
                    return self.store
            return r

    def hourly(self):
        if CONFIG.get('ha_mode') == 'replicated' and self.store.db.engine == 'postgres':
            try:
                ha_sequences_check(self.store.db, int(CONFIG.get('ha_slot') or 1))
            except Exception as e:                      # noqa: BLE001
                log('the numbering of the tables could not be checked: %s' % e, 'warn')
            # The other node's columns again (1.0.94): tried once at start, a
            # peer away just then kept replication to it stalled until its
            # own upgrade. Adding what is there already does nothing.
            ha_peer_columns()
            # A table the other node has and this node's subscription does
            # not take yet - one a later version added, the two nodes
            # upgraded by hand - taken from now on (1.0.101).
            try:
                db = self.store.db
                sub = ha_sub_here(db, 3 - int(CONFIG.get('ha_slot') or 1))
                if sub and int(db.value('SELECT COUNT(*) FROM pg_subscription_rel r JOIN '
                                        'pg_subscription s ON s.oid = r.srsubid WHERE '
                                        's.subname = ?', (sub,)) or 0) < len(TABLES):
                    db.run(RawSql('ALTER SUBSCRIPTION %s REFRESH PUBLICATION WITH '
                                  '(copy_data = false)' % sub))
            except Exception as e:                      # noqa: BLE001
                log('the tables taken from the other node could not be read again: %s'
                    % str(e).split('\n')[0][:200], 'info')
        try:
            chal_tidy(self.store)                       # codes asked for and gone (1.0.76)
        except Exception as e:                          # noqa: BLE001
            log('the old challenges could not be tidied: %s' % e, 'warn')
        try:
            once_tidy(self.store)                       # used once, long ago (1.0.101)
        except Exception as e:                          # noqa: BLE001
            log('the codes used once could not be tidied: %s' % e, 'warn')
        try:
            self.fill_names(limit=100)
        except Exception as e:                          # noqa: BLE001
            log('names from the directory: %s' % e, 'warn')
        try:
            # One node of two deletes the old rows; the deletes go over to the
            # other anyway (1.0.57).
            if CONFIG.get('ha_mode') == 'replicated' and not claim_once(
                    self.store, 'tidy_hour', time.strftime('%Y-%m-%d %H')):
                return
            gone = self.store.tidy()
            if any(gone.values()):
                log('tidied: %s' % gone)
        except Exception as e:                          # noqa: BLE001
            log('tidying broke: %s' % e, 'warn')

    def nightly(self):
        try:
            # As isemon's: the engine's own dump every night, or a portable
            # copy where its program is missing.
            make_dump(self.store, 'daily')
        except Exception as e:                          # noqa: BLE001
            self.store.add_event('backups', 'the daily dump failed: %s' % e, 'bad')
        try:
            note_size(self.store)
        except Exception:                               # noqa: BLE001
            pass

    def _hup(self):
        log_open()
        try:
            self.reload_all('SIGHUP')
        except Exception as e:
            log('reading the configuration again failed: %s' % e, 'error')


# ---------------------------------------------------------------------------
# Moving to another database, looking after the one in use, tuning its
# server - the database page, as isemon has it
# ---------------------------------------------------------------------------
ENGINE_WORDS = {'sqlite': 'the file on this machine (SQLite)', 'mariadb': 'MariaDB',
                'postgres': 'PostgreSQL'}
# DB_KEYS is 00_head's (1.0.94): a second one here, without db_tls and
# db_tls_ca, left the database's TLS out of the test before a save, of the
# cluster's bundle and of the move to another database.
DB_IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,62}\Z')


def file_db_settings():
    """The database settings as config.json has them now - Set it up writes
    the address and the password made there while the old database is
    still the one in use, and the steps after it must find them (1.0.37)."""
    try:
        with open(str(CONFIG_FILE), encoding='utf-8') as f:
            got = json.load(f)
        return {k: got[k] for k in DB_KEYS if k in got} if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def engine_asked(given):
    """The database the page means: what it typed, over what is set."""
    c = {k: CONFIG.get(k) for k in DB_KEYS}
    on_file = file_db_settings()
    for k, v in on_file.items():
        if k != 'db_engine':
            c[k] = v
    for k, v in (given or {}).items():
        if k not in DB_KEYS or v is None:
            continue
        if k == 'db_password' and is_masked(v):
            continue
        c[k] = v
    if c.get('db_engine') not in ('sqlite', 'mariadb', 'postgres'):
        raise ValueError('the engine is sqlite, mariadb or postgres')
    for k in ('db_name', 'db_user'):
        if c['db_engine'] != 'sqlite' and not DB_IDENT.match(str(c.get(k) or '')):
            raise ValueError('%s is letters, digits and _ only, starting with a letter' % k)
    return c


def db_open(c, statement_s=None):
    return Db(c.get('db_engine') or 'sqlite', c.get('db_host') or '', c.get('db_port') or 0,
              c.get('db_name') or 'otp', c.get('db_user') or 'otp', c.get('db_password') or '',
              c.get('db_timeout_s') or 10,
              tls=c.get('db_tls') if 'db_tls' in c else CONFIG.get('db_tls'),
              tls_ca=c.get('db_tls_ca') if 'db_tls_ca' in c else CONFIG.get('db_tls_ca'),
              statement_s=statement_s)


def db_own(store, statement_s=0):
    """A connection of its own to the database in use, for a long job
    (1.0.101): a VACUUM FULL, a check of every table - on the one every
    sign-in shares, each held them all for as long as it took. SQLite has
    one file and one connection: that one. Closed by the caller."""
    if store.db.engine == 'sqlite':
        return None
    return db_open({k: CONFIG.get(k) for k in DB_KEYS}, statement_s=statement_s)


def same_database(c, db):
    """Whether the page's database is the one in use."""
    if c.get('db_engine') != db.engine:
        return False
    if db.engine == 'sqlite':
        return True
    port = int(c.get('db_port') or {'mariadb': 3306, 'postgres': 5432}[db.engine])
    here = {'', 'localhost', '127.0.0.1', '::1'}
    a, b = str(c.get('db_host') or '').lower(), str(db.host or '').lower()
    return ((a == b or (a in here and b in here)) and port == int(db.port or port)
            and str(c.get('db_name')) == str(db.name))


def db_try(c):
    """Reach a database as this program would. Never raises."""
    out = {'reached': False, 'engine': c.get('db_engine'),
           'words': ENGINE_WORDS.get(c.get('db_engine'), c.get('db_engine'))}
    try:
        db = db_open(c)
    except Exception as e:
        out['trouble'] = str(e).split('\n')[0][:300]
        return out
    try:
        out['reached'] = True
        out['where'] = db.where()
        out['version'] = db.version()
        names = db.tables()
        ours = [t for t in TABLES if t in names]
        out['tables'] = ours
        out['rows'] = sum(int(db.value('SELECT COUNT(*) FROM %s' % t) or 0)
                          for t in ours if t not in ('meta',))
        try:
            db.run('CREATE TABLE otp_probe (x INTEGER)')
            db.run('DROP TABLE otp_probe')
            out['writable'] = True
        except Exception as e:
            out['writable'] = False
            out['trouble'] = 'it answers, but this account may not make a table: %s' % (
                str(e).split('\n')[0][:200])
    except Exception as e:
        out['trouble'] = str(e).split('\n')[0][:300]
    finally:
        db.close()
    return out


def db_password_made():
    alphabet = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(24))


def db_make(c, admin_user, admin_password):
    """The database and its account, made by an administrator of that
    server who is used for this one connection and kept nowhere."""
    eng = c['db_engine']
    host = str(c.get('db_host') or '127.0.0.1')
    port = int(c.get('db_port') or {'mariadb': 3306, 'postgres': 5432}[eng])
    name, user, pw = c['db_name'], c['db_user'], c['db_password']
    done = []
    if eng == 'mariadb':
        import pymysql
        conn = pymysql.connect(host=host, port=port, user=admin_user, password=admin_password,
                               connect_timeout=int(c.get('db_timeout_s') or 10), autocommit=True)
        try:
            cur = conn.cursor()
            cur.execute('CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 '
                        'COLLATE utf8mb4_unicode_ci' % name)
            done.append('the database %s' % name)
            local = host in ('localhost', '127.0.0.1', '::1')
            for at in (('localhost', '127.0.0.1') if local else ('%',)):
                cur.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s", (user, at, pw))
                cur.execute("ALTER USER %s@%s IDENTIFIED BY %s", (user, at, pw))
                cur.execute('GRANT ALL PRIVILEGES ON `%s`.* TO %%s@%%s' % name, (user, at))
                done.append("the account '%s'@'%s', with every right on %s and none elsewhere"
                            % (user, at, name))
            cur.execute('FLUSH PRIVILEGES')
        finally:
            conn.close()
        return done
    import psycopg2
    conn = psycopg2.connect(host=host, port=port, user=admin_user, password=admin_password,
                            dbname='postgres', connect_timeout=int(c.get('db_timeout_s') or 10))
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (user,))
        if cur.fetchone():
            cur.execute('ALTER ROLE "%s" WITH LOGIN PASSWORD %%s' % user, (pw,))
            done.append('the account %s was there; its password is new' % user)
        else:
            cur.execute('CREATE ROLE "%s" WITH LOGIN PASSWORD %%s' % user, (pw,))
            done.append('the account %s' % user)
        cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', (name,))
        if cur.fetchone():
            cur.execute('ALTER DATABASE "%s" OWNER TO "%s"' % (name, user))
            done.append('the database %s was there; %s owns it now' % (name, user))
        else:
            cur.execute("CREATE DATABASE \"%s\" OWNER \"%s\" ENCODING 'UTF8' TEMPLATE template0"
                        % (name, user))
            done.append('the database %s, owned by %s' % (name, user))
    finally:
        conn.close()
    conn = psycopg2.connect(host=host, port=port, user=admin_user, password=admin_password,
                            dbname=name, connect_timeout=int(c.get('db_timeout_s') or 10))
    conn.autocommit = True
    try:
        conn.cursor().execute('GRANT ALL ON SCHEMA public TO "%s"' % user)
    except Exception:
        pass
    finally:
        conn.close()
    return done


def db_empty(c):
    db = db_open(c)
    try:
        gone = []
        for t in reversed(TABLES):
            if t in db.tables():
                db.run('DROP TABLE %s' % t)
                gone.append(t)
        return gone
    finally:
        db.close()


# ---- one long job at a time, which the page asks after ---------------------
DB_JOB = {'id': 0, 'what': '', 'running': False, 'done': 0, 'whole': 0, 'says': '',
          'error': '', 'result': None, 'began': 0, 'ended': 0}
DB_JOB_LOCK = threading.Lock()


def db_job(what, work):
    with DB_JOB_LOCK:
        if DB_JOB['running']:
            raise ValueError('%s is going on already' % DB_JOB['what'])
        DB_JOB.update({'id': DB_JOB['id'] + 1, 'what': what, 'running': True, 'done': 0,
                       'whole': 0, 'says': '', 'error': '', 'result': None,
                       'began': time.time(), 'ended': 0})

    def progress(done, whole, says):
        DB_JOB.update({'done': done, 'whole': whole, 'says': says})
        if time.time() - DB_JOB.get('_pub', 0) > 1:
            DB_JOB['_pub'] = time.time()
            job_publish({k: v for k, v in DB_JOB.items() if not k.startswith('_')})

    def run():
        try:
            DB_JOB['result'] = work(progress)
        except Exception as e:
            DB_JOB['error'] = scrub_secret(str(e).split('\n')[0][:400])
            log('%s failed: %s' % (what, scrub_secret(e)), 'error')
        finally:
            DB_JOB.update({'running': False, 'ended': time.time()})
            job_publish({k: v for k, v in DB_JOB.items() if not k.startswith('_')})

    def beat():
        # Said again every half minute, so the other node - or this one,
        # after a restart - can tell a job going on from one that died.
        while DB_JOB.get('running'):
            time.sleep(30)
            if DB_JOB.get('running'):
                job_publish({k: v for k, v in DB_JOB.items() if not k.startswith('_')})

    threading.Thread(target=run, name='db-job', daemon=True).start()
    threading.Thread(target=beat, name='db-job-beat', daemon=True).start()
    return dict(DB_JOB)


def db_move(store, c, by):
    """Everything here into the other database, through a copy."""
    def work(progress):
        progress(0, 0, 'making a copy of what is here')
        before = store.counts()
        copy = make_backup(store, 'before moving, by %s' % by)
        whole = sum(before.values())
        far = db_open(c)
        tally = {}
        try:
            def along(table, done):
                tally[table] = done
                progress(sum(tally.values()), whole, '%s: %s' % (table, done))
            load_tables(far, copy, say=along)
            after = {t: int(far.value('SELECT COUNT(*) FROM %s' % t) or 0)
                     for t in TABLES if t != 'meta'}
        finally:
            far.close()
        short = {t: (before.get(t, 0), after.get(t, 0)) for t in after
                 if after.get(t, 0) < before.get(t, 0) and t not in ('sessions',)}
        store.add_event('settings', 'everything was carried into %s (%s), by %s'
                        % (ENGINE_WORDS.get(c['db_engine']), db_where(c), by), who=by)
        progress(whole, whole, 'done')
        return {'copy': copy.name, 'rows': sum(after.values()), 'short': short,
                'where': db_where(c)}
    return db_job('carrying everything across', work)


def db_where(c):
    if c.get('db_engine') == 'sqlite':
        return str(DB_FILE)
    return '%s@%s:%s/%s' % (c.get('db_user'), c.get('db_host') or 'localhost',
                            c.get('db_port') or {'mariadb': 3306, 'postgres': 5432}
                            [c['db_engine']], c.get('db_name'))


# ---- looking after the one in use --------------------------------------------
def db_table_sizes(db):
    """Rows and bytes of every table, as far as the engine says."""
    out = []
    sizes = {}
    try:
        if db.engine == 'mariadb':
            for r in db.rows('SELECT TABLE_NAME AS t, DATA_LENGTH + INDEX_LENGTH AS b, '
                             'DATA_FREE AS f FROM information_schema.TABLES '
                             'WHERE TABLE_SCHEMA = DATABASE()'):
                sizes[r['t']] = (int(r['b'] or 0), int(r['f'] or 0))
        elif db.engine == 'postgres':
            for t in TABLES:
                sizes[t] = (int(db.value('SELECT pg_total_relation_size(?)', (t,)) or 0), 0)
        else:
            try:
                for r in db.rows('SELECT name AS t, SUM(pgsize) AS b FROM dbstat GROUP BY name'):
                    sizes[r['t']] = (int(r['b'] or 0), 0)
            except Exception:
                pass
    except Exception:
        pass
    for t in TABLES:
        try:
            n = int(db.value('SELECT COUNT(*) FROM %s' % t) or 0)
        except Exception:
            n = 0
        b, free = sizes.get(t, (None, 0))
        out.append({'table': t, 'rows': n, 'bytes': b, 'free': free})
    return out


def db_free_inside(db):
    """Room the engine holds that it would give back to the disk."""
    try:
        if db.engine == 'sqlite':
            pages = int(db.value('PRAGMA freelist_count') or 0)
            return pages * int(db.value('PRAGMA page_size') or 4096)
        if db.engine == 'mariadb':
            return int(db.value('SELECT SUM(DATA_FREE) FROM information_schema.TABLES '
                                'WHERE TABLE_SCHEMA = DATABASE()') or 0)
        return int(db.value('SELECT COALESCE(SUM(n_dead_tup), 0) FROM pg_stat_user_tables') or 0)
    except Exception:
        return 0


def db_check(db):
    """Read the database through and say whether anything is broken."""
    said = []
    if db.engine == 'sqlite':
        got = [r for r in db.rows('PRAGMA integrity_check')]
        words = [list(r.values())[0] for r in got]
        return {'ok': words == ['ok'], 'said': words[:20]}
    if db.engine == 'mariadb':
        ok = True
        for t in TABLES:
            for r in db.rows('CHECK TABLE %s' % t):
                v = {k.lower(): x for k, x in r.items()}
                if str(v.get('msg_type')).lower() in ('error', 'warning') or \
                        str(v.get('msg_text')).lower() not in ('ok', 'table is already up to date'):
                    ok = False
                    said.append('%s: %s' % (t, v.get('msg_text')))
        return {'ok': ok, 'said': said or ['every table: OK']}
    ok = True
    for t in TABLES:
        try:
            n = db.value('SELECT COUNT(*) FROM %s' % t)
            said.append('%s: %s row(s) read' % (t, n))
        except Exception as e:
            ok = False
            said.append('%s: %s' % (t, str(e).split('\n')[0]))
    return {'ok': ok, 'said': said}


def db_statistics(db):
    """Fresh statistics for the planner - quick, nothing is locked."""
    if db.engine == 'sqlite':
        db.run('ANALYZE')
        db.run('PRAGMA optimize')
    elif db.engine == 'mariadb':
        for t in TABLES:
            db.rows('ANALYZE TABLE %s' % t)
    else:
        db.run('ANALYZE')
    return 'the statistics of every table are fresh'


def db_give_back(store, progress):
    """Give the room deleted rows left back to the disk: VACUUM, OPTIMIZE
    TABLE, VACUUM FULL. Each holds a table shut while it works."""
    own = db_own(store)
    # In a cluster this node rests meanwhile (1.0.150): the tables are held
    # shut, and RADIUS waited on them - the other node answers. Alone, the
    # page says first that sign-ins wait for it.
    rest = bool(CONFIG.get('ha_mode')) and any(n.get('alive') and not n.get('me')
                                               for n in ha_nodes(store))
    if rest:
        RESTORE_WHY[0] = 'the database gives its room back'
        RESTORE_RUNNING.set()
    try:
        return _db_give_back(own or store.db, progress)
    finally:
        if rest:
            RESTORE_RUNNING.clear()
        if own:
            own.close()


def _db_give_back(db, progress):
    before = db.size()
    if db.engine == 'sqlite':
        progress(0, 1, 'VACUUM')
        db.run('PRAGMA wal_checkpoint(TRUNCATE)')
        db.run('VACUUM')
        db.run('PRAGMA wal_checkpoint(TRUNCATE)')
    else:
        for i, t in enumerate(TABLES):
            progress(i, len(TABLES), t)
            if db.engine == 'mariadb':
                db.rows('OPTIMIZE TABLE %s' % t)
            else:
                db.run('VACUUM (FULL, ANALYZE) %s' % t)
    after = db.size()
    progress(1, 1, 'done')
    return {'before': before, 'after': after}


def db_prune(store, days):
    """Forget the requests and the checks of a code older than `days`."""
    edge = time.time() - int(days) * 86400 if int(days) > 0 else time.time() + 86400
    gone = {}
    for t in ('radius_log', 'otp_log'):
        # In batches (1.0.57): one DELETE of millions of rows held RADIUS -
        # and the health check the web address follows - for minutes.
        gone[t] = store.delete_older(t, edge)
    return gone


# ---- the server's own settings, for its machine (isemon's DbTune, smaller) --
def tune_machine(c, typed):
    """What the database server's machine has: read here when it is this
    machine, typed on the page when it is not."""
    host = str(c.get('db_host') or '').lower()
    local = host in ('', 'localhost', '127.0.0.1', '::1') or host == socket.gethostname().lower()
    facts = {'local': local, 'ram_gb': None, 'cpus': None, 'disk': None, 'avail': None,
             'ram': None, 'virtual': None, 'rotational': None,
             'source': 'this machine' if local else ''}
    if local:
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        facts['ram'] = int(line.split()[1]) * 1024
                    elif line.startswith('MemAvailable:'):
                        facts['avail'] = int(line.split()[1]) * 1024
            if facts['ram']:
                facts['ram_gb'] = round(facts['ram'] / 1073741824.0, 1)
        except OSError:
            pass
        facts['cpus'] = os.cpu_count()
        try:
            with open('/proc/cpuinfo') as f:
                facts['virtual'] = ' hypervisor' in f.read()
        except OSError:
            pass
        try:
            rot = [open(p).read().strip() for p in
                   [str(x) for x in Path('/sys/block').glob('*/queue/rotational')]
                   if not re.search(r'/(loop|ram|zram|sr|dm-)\d', p)]
            if rot:
                facts['rotational'] = all(r == '1' for r in rot)
        except OSError:
            pass
    for k in ('ram_gb', 'cpus'):
        if typed.get(k) not in (None, ''):
            try:
                v = float(str(typed[k]).replace(',', '.')) if k == 'ram_gb' else int(typed[k])
            except ValueError:
                raise ValueError('the memory is a number of GB, the processors a whole number')
            if k == 'ram_gb' and facts['ram_gb'] and abs(v - facts['ram_gb']) > 0.05 * v:
                facts['source'] = 'typed' if not local else facts['source']
            if k == 'cpus' and v != facts['cpus'] and not local:
                facts['source'] = 'typed'
            facts[k] = v
            if k == 'ram_gb':
                facts['ram'] = int(v * 1073741824)
    return facts


def tune_commit_ms(db):
    """How long the server takes to make one small write safe: the middle of
    twenty, each its own transaction, less a round trip."""
    if db.engine == 'sqlite':
        return None
    took, trip = [], []
    # A row of this node's own (1.0.59): two nodes measuring at once wrote
    # the same key, and replication stopped on the duplicate.
    probe = 'tune_probe:' + node_name()
    try:
        # The row is there to be written (1.0.44): an UPDATE of nothing
        # commits nothing and every disk looked fast.
        db.run('DELETE FROM meta WHERE k = ?', (probe,))
        db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (probe, '0'))
        for _ in range(5):
            t = time.perf_counter()
            db.value('SELECT 1')
            trip.append(time.perf_counter() - t)
        for i in range(20):
            t = time.perf_counter()
            db.run('UPDATE meta SET v = ? WHERE k = ?', (str(i), probe))
            took.append(time.perf_counter() - t)
        db.run('DELETE FROM meta WHERE k = ?', (probe,))
    except Exception:                                   # noqa: BLE001
        return None
    took.sort()
    trip.sort()
    return max(0.0, (took[len(took) // 2] - trip[len(trip) // 2]) * 1000.0)


def tune_disk_guess(facts, commit_ms):
    """As isemon's: what the disk says of itself first - except in a virtual
    machine, where a disk says it spins whatever it is on - then how long a
    small write takes to be made safe."""
    rot = facts.get('rotational')
    if rot is False:
        return 'ssd', 'the disk says it does not spin'
    if rot is True and not facts.get('virtual'):
        return 'hdd', 'the disk says it spins'
    if commit_ms is not None:
        if commit_ms < 2.5:
            return 'ssd', 'a write is made safe in %.1f ms, which is an SSD' % commit_ms
        if commit_ms > 6:
            return 'hdd', 'a write is made safe in %.1f ms, which is a disk that spins' % commit_ms
    return 'ssd', ('not known for certain - most servers are on SSDs now; choose the other if '
                   'this one is not')


def _mb(n):
    n = int(n)
    return '%dGB' % (n // 1024) if n >= 1024 and n % 1024 == 0 else '%dMB' % n


def tune_plan(engine, m):
    """name -> (value, why, needs_restart)"""
    ram = int((m.get('ram_gb') or 4) * 1024)
    cpus = max(1, int(m.get('cpus') or 2))
    ssd = (m.get('disk') or 'ssd') == 'ssd'
    # Shared with otp itself (and nginx, PHP) when it is this machine.
    share = 0.8 if m.get('local') else 1.0
    if engine == 'postgres':
        sb = max(128, min(int(ram * share / 4), 16384))
        return {
            'shared_buffers': (_mb(sb), 'a quarter of the memory: the server’s own cache', True),
            'effective_cache_size': (_mb(int(ram * share * 3 / 4)),
                                     'how much the planner may assume is cached', False),
            'maintenance_work_mem': (_mb(max(64, min(ram // 16, 2048))),
                                     'for VACUUM and building indexes', False),
            'work_mem': (_mb(max(4, min(ram // 256, 64))), 'for each sort and hash', False),
            'wal_buffers': ('16MB', 'the write-ahead log’s buffer', True),
            'max_wal_size': ('4GB' if ssd else '2GB', 'fewer checkpoints under load', False),
            'min_wal_size': ('1GB', 'kept between checkpoints', False),
            'checkpoint_completion_target': ('0.9', 'checkpoints spread out', False),
            'random_page_cost': ('1.1' if ssd else '4', 'an SSD reads anywhere as fast', False),
            'effective_io_concurrency': ('200' if ssd else '2', 'reads the disk takes at once', False),
            'max_worker_processes': (str(max(8, cpus)), 'one per processor', True),
            'max_parallel_workers': (str(cpus), 'parallel queries over every processor', False),
            'max_parallel_workers_per_gather': (str(max(1, min(4, cpus // 2))),
                                                'per query', False),
        }
    pool = max(128, int(ram * share * (0.5 if m.get('local') else 0.7)) // 128 * 128)
    return {
        'innodb_buffer_pool_size': (str(pool * 1048576), 'the server’s own cache: %s'
                                    % _mb(pool), False),
        'innodb_log_file_size': (str(min(pool // 4, 2048) * 1048576),
                                 'a log large enough for a busy hour', True),
        'innodb_flush_method': ('O_DIRECT', 'no second copy in the system’s cache', True),
        'innodb_io_capacity': ('2000' if ssd else '200', 'what the disk takes per second', False),
        'innodb_io_capacity_max': ('4000' if ssd else '400', '...at most', False),
        'innodb_flush_neighbors': ('0' if ssd else '1', 'an SSD has no neighbours', False),
        'tmp_table_size': (str(64 * 1048576), 'in-memory temporary tables', False),
        'max_heap_table_size': (str(64 * 1048576), '...the same', False),
        'table_open_cache': ('2000', 'tables kept open', False),
    }


def tune_current(db, names):
    out = {}
    for n in names:
        try:
            if db.engine == 'postgres':
                out[n] = str(db.value('SHOW %s' % n))
            else:
                r = db.row("SHOW GLOBAL VARIABLES LIKE ?", (n,))
                out[n] = str(list(r.values())[1]) if r else ''
        except Exception:
            out[n] = ''
    return out


def tune_same(engine, a, b):
    def norm(v):
        v = str(v).strip()
        m = re.match(r'^(\d+(?:\.\d+)?)\s*(kB|MB|GB|TB)?\Z', v, re.I)
        if not m:
            return v.lower()
        mult = {'kb': 1, 'mb': 1024, 'gb': 1048576, 'tb': 1073741824}.get(
            (m.group(2) or '').lower(), None)
        return float(m.group(1)) * mult if mult else float(m.group(1))
    try:
        x, y = norm(a), norm(b)
        if isinstance(x, float) and isinstance(y, float) and max(x, y) >= 1024:
            # Memory: within a tenth is the same - what is free moves from one
            # look to the next, and a setting is not changed for that.
            return abs(x - y) <= 0.1 * max(x, y)
        return x == y
    except Exception:
        return str(a) == str(b)


def tune_connect(store, admin_user, admin_password):
    """The server, as an administrator when one is given, else as ourselves."""
    c = {k: CONFIG.get(k) for k in DB_KEYS}
    if admin_user:
        c['db_user'], c['db_password'] = admin_user, admin_password
        if c['db_engine'] == 'postgres':
            pass
    return db_open(c) if admin_user else store.db


def tune_last(store):
    try:
        return json.loads(store.get_meta('tune_last:' + node_name()) or 'null')
    except ValueError:
        return None


def tune_pending(db):
    if db.engine != 'postgres':
        return []
    try:
        return [r['name'] for r in db.rows('SELECT name FROM pg_settings WHERE pending_restart')]
    except Exception:                                   # noqa: BLE001
        return []


def tune_plan_for(store, typed, probe=True):
    db = store.db
    if db.engine == 'sqlite':
        raise ValueError('the file on this machine has no server to tune: this program sets '
                         'it up itself')
    c = {k: CONFIG.get(k) for k in DB_KEYS}
    typed = typed or {}
    m = tune_machine(c, typed)
    commit_ms = tune_commit_ms(db) if probe else None
    disk, why = tune_disk_guess(m, commit_ms)
    if typed.get('disk') in ('ssd', 'hdd') and typed['disk'] != disk:
        disk, why = typed['disk'], 'chosen'
    m['disk'], m['why'], m['commit_ms'] = disk, why, commit_ms
    out = {'engine': db.engine, 'words': ENGINE_WORDS.get(db.engine), 'where': db.where(),
           'version': str(db.version() or '').split(' on ')[0].split(',')[0],
           'size': int(db.size() or 0), 'machine': m, 'facts': m,
           'restart': tune_restart_ready(store), 'last': tune_last(store), 'rows': [],
           'items': []}
    try:
        if db.engine == 'postgres':
            out['connections'] = int(db.value('SHOW max_connections') or 0)
        else:
            r = db.row("SHOW GLOBAL VARIABLES LIKE 'max_connections'")
            out['connections'] = int(list(r.values())[1]) if r else 0
    except Exception:                                   # noqa: BLE001
        pass
    if not m.get('ram_gb') or not m.get('cpus'):
        out['need_facts'] = True
        return out
    plan = tune_plan(db.engine, m)
    now = tune_current(db, plan.keys())
    pending = set(tune_pending(db))
    last = out['last'] or {}
    mine = last.get('engine') == db.engine and not last.get('undone') \
        and last.get('where') == db.where()
    put = (last.get('set') or {}) if mine else {}
    rows = []
    for n, (v, why_, rs) in plan.items():
        same = tune_same(db.engine, now.get(n, ''), v)
        row = {'name': n, 'now': now.get(n, ''), 'want': v, 'why': why_, 'restart': rs,
               'takes': 'at the next start' if rs else 'at once', 'same': same,
               'change': not same, 'pending': n in pending}
        if n in pending and n in put and tune_same(db.engine, put[n], v):
            row.update(change=False, waiting=True)
        rows.append(row)
    out['rows'] = out['items'] = rows
    if db.engine == 'mariadb':
        out['snippet'] = out['cnf'] = (
            '# Written by otp %s for this machine, as zz-otp-tuning.cnf in /etc/my.cnf.d/\n'
            '# (or /etc/mysql/mariadb.conf.d/) so that the settings outlast a restart.\n'
            '[mariadb]\n' % __version__) + ''.join('%s = %s\n' % (r['name'], r['want'])
                                                    for r in rows)
    return out


def tune_apply(store, typed, admin_user, admin_password, by):
    plan = tune_plan_for(store, typed, probe=False)
    if plan.get('need_facts'):
        raise ValueError('say what the machine has first: its memory and its processors')
    db = tune_connect(store, admin_user, admin_password)
    done, later, failed = [], [], []
    before = json.loads(store.get_meta('tune_before:' + node_name()) or '{}')
    try:
        for r in plan['rows']:
            if not r['change']:
                continue
            before.setdefault(r['name'], r['now'])
            try:
                if plan['engine'] == 'postgres':
                    db.run("ALTER SYSTEM SET %s = '%s'" % (r['name'], r['want'].replace("'", '')))
                    (later if r['restart'] else done).append(r['name'])
                else:
                    if r['restart']:
                        later.append(r['name'])
                        continue
                    db.run('SET GLOBAL %s = %s' % (r['name'], r['want'] if r['want'].isdigit()
                                                  else "'%s'" % r['want']))
                    done.append(r['name'])
            except Exception as e:
                failed.append('%s: %s' % (r['name'], str(e).split('\n')[0][:160]))
        if plan['engine'] == 'postgres' and (done or later):
            db.run('SELECT pg_reload_conf()')
    finally:
        if db is not store.db:
            db.close()
    store.set_meta('tune_before:' + node_name(), json.dumps(before))
    if done or later:
        store.set_meta('tune_last:' + node_name(), json.dumps({
            'engine': plan['engine'], 'where': store.db.where(), 'at': time.time(), 'by': by,
            'set': {r['name']: r['want'] for r in plan['rows'] if r['name'] in done + later},
            'undone': 0}))
    store.add_event('settings', 'the database server was tuned for its machine by %s: %s'
                    % (by, ', '.join(done + later) or 'nothing'), 'warn', who=by)
    plan2 = tune_plan_for(store, typed, probe=False)
    plan2.update({'done': done, 'later': later, 'failed': failed})
    return plan2


TUNE_RESTART_MARK = CONFIG_FILE.parent / 'may-restart-database'


def tune_restart_unit():
    """The postgresql service on this machine, as systemd knows it, or ''."""
    try:
        said = subprocess.run(['systemctl', 'list-units', '--type=service', '--all', '--plain',
                               '--no-legend', '--no-pager', 'postgresql*'],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ''
    found = []
    for line in said.stdout.splitlines():
        f = line.split()
        if len(f) >= 3 and f[2] == 'active' and \
                re.match(r'^postgresql(-\d+)?(@[\w.-]+)?\.service\Z', f[0]):
            found.append(f[0])
    return found[0] if len(found) == 1 else ''


def tune_restart_ready(store):
    db = store.db
    if db.engine != 'postgres':
        return {'may': False, 'unit': ''}
    host = str(CONFIG.get('db_host') or '').lower()
    if host not in ('', 'localhost', '127.0.0.1', '::1', socket.gethostname().lower()):
        return {'may': False, 'unit': 'postgresql',
                'why': 'PostgreSQL runs on another machine, which this program cannot restart'}
    unit = tune_restart_unit()
    if not unit:
        return {'may': False, 'unit': 'postgresql',
                'why': 'no single running postgresql service was found on this machine'}
    if not TUNE_RESTART_MARK.exists():
        return {'may': False, 'unit': unit,
                'why': 'install.sh has not let this program restart it (run install.sh --upgrade '
                       'without --no-db-restart)'}
    return {'may': True, 'unit': unit, 'why': ''}


def tune_restart(store, by):
    """PostgreSQL on this machine started again, for the settings that take
    only at a start - through systemd, where install.sh let this account do
    that - and waited for."""
    db = store.db
    ready = tune_restart_ready(store)
    if db.engine != 'postgres' or not ready['unit']:
        raise ValueError('no database server is running as a service on this machine')
    unit = ready['unit']
    if not TUNE_RESTART_MARK.exists():
        raise ValueError('this program may not restart %s: run  systemctl restart %s  as root'
                         % (unit, unit))
    waiting = tune_pending(db)
    if not waiting:
        raise ValueError('nothing waits for a restart')
    try:
        if str(db.value('SHOW huge_pages')).lower() == 'on':
            raise ValueError('huge_pages is on, and a start needs enough of them for the new '
                             'shared_buffers: check vm.nr_hugepages, then run  systemctl '
                             'restart %s  as root' % unit)
    except ValueError:
        raise
    except Exception:                                   # noqa: BLE001
        pass
    if 'shared_buffers' in waiting:
        try:
            want = int(db.value("SELECT pg_size_bytes(setting) FROM pg_file_settings WHERE "
                                "name = 'shared_buffers' AND applied = false ORDER BY seqno "
                                "DESC LIMIT 1") or 0)
        except Exception:                               # noqa: BLE001
            want = 0
        try:
            want = want or 0
            running = int(db.value("SELECT setting::bigint * 8192 FROM pg_settings WHERE "
                                   "name = 'shared_buffers'") or 0)
            avail = tune_machine({}, {}).get('avail') or 0
        except Exception:                               # noqa: BLE001
            running = avail = 0
        if want and avail and want - running > avail - 512 * 1048576:
            raise ValueError('the machine has %d MB free now, too little for shared_buffers of '
                             '%d MB - restarted now, PostgreSQL might not start. Free some '
                             'memory, or put back as it was' % (avail // 1048576,
                                                                 want // 1048576))
    began = time.time()
    try:
        said = subprocess.run(['systemctl', '--no-ask-password', '--no-block', 'restart', unit],
                              capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        raise ValueError('systemctl: %s' % str(e)[:160])
    if said.returncode != 0:
        raise ValueError('%s was not restarted: %s - run  systemctl restart %s  as root'
                         % (unit, (said.stderr or said.stdout).strip()[:160], unit))
    store.add_event('settings', '%s restarted %s for the settings waiting for it: %s'
                    % (by, unit, ', '.join(waiting)), 'warn', who=by)
    time.sleep(2)
    back = False
    while time.time() < began + 62:
        try:
            state = subprocess.run(['systemctl', 'is-failed', unit], capture_output=True,
                                   text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            state = ''
        if state == 'failed':
            raise ValueError('%s did not start again - see  journalctl -u %s ; if it does not '
                             'start: as root, take the shared_buffers line out of '
                             'postgresql.auto.conf and run  systemctl start %s'
                             % (unit, unit, unit))
        try:
            started = float(db.value('SELECT extract(epoch from pg_postmaster_start_time())'))
            if started >= began - 1:
                back = True
                break
        except Exception:                               # noqa: BLE001
            pass
        time.sleep(1)
    if not back:
        raise ValueError('%s was asked to restart and has not answered yet - look again in a '
                         'minute' % unit)
    left = tune_pending(db)
    return {'unit': unit, 'waiting': waiting, 'still': left,
            'message': '%s started again%s' % (unit, '; still waiting: ' + ', '.join(left)
                                                if left else ': every setting is in effect')}


def tune_undo(store, admin_user, admin_password, by):
    before = json.loads(store.get_meta('tune_before:' + node_name()) or '{}')
    if not before:
        raise ValueError('nothing was changed here, so there is nothing to put back')
    db = tune_connect(store, admin_user, admin_password)
    done, failed = [], []
    try:
        for n, v in before.items():
            try:
                if store.db.engine == 'postgres':
                    db.run('ALTER SYSTEM RESET %s' % n)
                else:
                    db.run('SET GLOBAL %s = %s' % (n, v if str(v).isdigit() else "'%s'" % v))
                done.append(n)
            except Exception as e:
                failed.append('%s: %s' % (n, str(e).split('\n')[0][:160]))
        if store.db.engine == 'postgres':
            db.run('SELECT pg_reload_conf()')
    finally:
        if db is not store.db:
            db.close()
    store.set_meta('tune_before:' + node_name(), '')
    last = tune_last(store) or {}
    if last:
        last.update(undone=time.time(), undone_by=by)
        store.set_meta('tune_last:' + node_name(), json.dumps(last))
    store.add_event('settings', 'the database server’s settings were put back by %s: %s'
                    % (by, ', '.join(done)), 'warn', who=by)
    return {'done': done, 'failed': failed}
