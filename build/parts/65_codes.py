# ---------------------------------------------------------------------------
# Codes sent by mail or SMS, and the VPN's second window (1.0.76)
# ---------------------------------------------------------------------------
# A token is one of three kinds:
#   totp  - the authenticator app, as it always was (the kind column empty);
#   mail  - no app: after the directory password a code is mailed;
#   sms   - the same, by SMS through a gateway or a modem.
# A mail or SMS token holds no key anybody scans - only where the codes go
# (`dest`) and its recovery codes. It signs in through RADIUS
# Challenge/Response: the first Access-Request carries the directory
# password; it is checked (and the groups), a code is sent and an
# Access-Challenge goes back with a State; the VPN (Cisco Secure Client and
# others) shows a second window, and the code comes back in a second
# Access-Request with that State.
#
# A challenge is kept in the database (meta 'chal:' + hash of the State), so
# that the answer is taken by either node of a cluster. It holds a hash of
# the code, never the code.

CODE_KINDS = ('totp', 'mail', 'sms')
CODE_KIND_WORDS = {'totp': 'the authenticator app', 'mail': 'a code by mail',
                   'sms': 'a code by SMS'}
CHAL_PREFIX = b'otp1'
# What a code is for, and the words of each (1.0.127): the VPN's sign-in and
# checking an address for it, and the same two for the administration's
# second step - each its own message in Settings → Message texts.
CODE_PURPOSES = {
    'signin': {'p': '', 'subject': 'mail_subject', 'body': 'mail_body', 'sms': 'sms',
               'warn': True, 'note': 'h_warn', 'queue': 'code'},
    'verify': {'p': 'v_', 'subject': 'verify_subject', 'body': 'verify_body', 'sms': 'sms_verify',
               'warn': False, 'note': 'h_v_note', 'queue': 'verify'},
    'admin': {'p': 'a_', 'subject': 'admin_subject', 'body': 'admin_body', 'sms': 'admin_sms',
              'warn': True, 'note': 'h_a_warn', 'queue': 'code'},
    'admin_verify': {'p': 'av_', 'subject': 'admin_verify_subject', 'body': 'admin_verify_body',
                     'sms': 'admin_sms_verify', 'warn': False, 'note': 'h_av_note',
                     'queue': 'verify'},
}


def code_purpose(purpose):
    return CODE_PURPOSES.get(purpose) or CODE_PURPOSES['verify']

CODE_TEXTS = {
    'cs': {
        'mail_subject': 'Kód pro přihlášení: {code}',
        'mail_body': ('Váš kód pro přihlášení je\n\n    {code}\n\nPlatí {minutes} min a jen '
                      'jednou. Pokud jste se právě nepřihlašovali, kód nikomu nesdělujte a '
                      'změňte si heslo - někdo ho zná.\n\n-- \n{site}'),
        'verify_subject': 'Ověření adresy: {code}',
        'verify_body': ('Kód pro ověření této adresy je\n\n    {code}\n\nZadejte ho na stránce, '
                        'kde jste si nastavovali přihlašování. Platí {minutes} min.\n\n'
                        'Pokud jste o nic nežádali, zprávu smažte.\n\n-- \n{site}'),
        'sms': '{code} je váš kód pro přihlášení ({site}). Platí {minutes} min. Nikomu ho '
               'nesdělujte.',
        'sms_verify': '{code} je kód pro ověření tohoto čísla ({site}).',
        'h_hello': 'Dobrý den, {name},',
        'h_hello_anon': 'Dobrý den,',
        'h_lede': 'váš kód pro přihlášení do VPN k účtu <b>{account}</b>:',
        'h_lede_anon': 'váš kód pro přihlášení do VPN:',
        'h_facts': 'Zadejte ho do druhého okna VPN. Platí {minutes} min a jen jednou.',
        'h_warn': 'Pokud jste se právě nepřihlašovali, kód nikomu nesdělujte a změňte si heslo '
                  '– někdo ho zná.',
        'h_v_lede': 'kód pro ověření této adresy pro přihlašování do VPN k účtu <b>{account}</b>:',
        'h_v_lede_anon': 'kód pro ověření této adresy pro přihlašování do VPN:',
        'h_v_hello': 'Dobrý den, {name},',
        'h_v_hello_anon': 'Dobrý den,',
        'h_v_title': 'VPN · Dvoufázové přihlášení',
        'h_v_foot': 'Posláno automaticky z {site}. Na tento e-mail neodpovídejte.',
        'h_v_facts': 'Zadejte ho na stránce, kde si nastavujete přihlašování. Platí {minutes} min.',
        'h_v_note': 'Pokud jste o nic nežádali, e-mail smažte – bez kódu se nic nezmění.',
        'h_foot': 'Posláno automaticky z {site}. Na tento e-mail neodpovídejte.',
        'h_title': 'VPN · Dvoufázové přihlášení',
        # The administration's second step (1.0.127): its own words.
        'admin_subject': 'Kód pro přihlášení do administrace: {code}',
        'admin_body': ('Váš kód pro přihlášení do administrace {site} je\n\n    {code}\n\n'
                       'Platí {minutes} min a jen jednou. Pokud jste se právě nepřihlašovali, '
                       'kód nikomu nesdělujte a změňte si heslo - někdo ho zná.\n\n-- \n{site}'),
        'admin_verify_subject': 'Ověření adresy pro administraci: {code}',
        'admin_verify_body': ('Kód pro ověření této adresy pro přihlašování do administrace '
                              '{site} je\n\n    {code}\n\nZadejte ho na přihlašovací stránce '
                              'administrace. Platí {minutes} min.\n\nPokud jste o nic '
                              'nežádali, zprávu smažte.\n\n-- \n{site}'),
        'admin_sms': '{code} je váš kód pro přihlášení do administrace ({site}). Platí {minutes} '
                     'min. Nikomu ho nesdělujte.',
        'admin_sms_verify': '{code} je kód pro ověření tohoto čísla pro administraci ({site}).',
        'h_a_title': 'Administrace · Druhý krok přihlášení',
        'h_a_hello': 'Dobrý den, {name},', 'h_a_hello_anon': 'Dobrý den,',
        'h_a_lede': 'váš kód pro přihlášení do administrace k účtu <b>{account}</b>:',
        'h_a_lede_anon': 'váš kód pro přihlášení do administrace:',
        'h_a_facts': 'Zadejte ho na přihlašovací stránce administrace. Platí {minutes} min a jen '
                     'jednou.',
        'h_a_warn': 'Pokud jste se právě nepřihlašovali, kód nikomu nesdělujte a změňte si heslo '
                    '– někdo ho zná.',
        'h_a_foot': 'Posláno automaticky z {site}. Na tento e-mail neodpovídejte.',
        'h_av_title': 'Administrace · Druhý krok přihlášení',
        'h_av_hello': 'Dobrý den, {name},', 'h_av_hello_anon': 'Dobrý den,',
        'h_av_lede': 'kód pro ověření této adresy pro přihlašování do administrace k účtu '
                     '<b>{account}</b>:',
        'h_av_lede_anon': 'kód pro ověření této adresy pro přihlašování do administrace:',
        'h_av_facts': 'Zadejte ho na přihlašovací stránce administrace. Platí {minutes} min.',
        'h_av_note': 'Pokud jste o nic nežádali, e-mail smažte – bez kódu se nic nezmění.',
        'h_av_foot': 'Posláno automaticky z {site}. Na tento e-mail neodpovídejte.',
        'ask_mail': 'Zadejte kód, který přišel e-mailem na {dest}',
        'ask_sms': 'Zadejte kód z SMS poslané na {dest}',
        'ask_totp': 'Zadejte kód z aplikace v telefonu',
        'again': 'Kód nebyl správný - zadejte ho znovu',
    },
    'en': {
        'mail_subject': 'Your sign-in code: {code}',
        'mail_body': ('Your sign-in code is\n\n    {code}\n\nIt is good for {minutes} min and '
                      'once. If you are not signing in just now, tell nobody the code and '
                      'change your password - somebody knows it.\n\n-- \n{site}'),
        'verify_subject': 'Checking this address: {code}',
        'verify_body': ('The code to check this address is\n\n    {code}\n\nType it on the page '
                        'where you are setting up your sign-in. It is good for {minutes} min.'
                        '\n\nIf you asked for nothing, delete this mail.\n\n-- \n{site}'),
        'sms': '{code} is your sign-in code ({site}). Good for {minutes} min. Tell nobody.',
        'sms_verify': '{code} is the code to check this number ({site}).',
        'h_hello': 'Hello {name},',
        'h_hello_anon': 'Hello,',
        'h_lede': 'your code to sign in to the VPN as <b>{account}</b>:',
        'h_lede_anon': 'your code to sign in to the VPN:',
        'h_facts': 'Type it into the VPN\'s second window. It is good for {minutes} min and once.',
        'h_warn': 'If you are not signing in just now, tell nobody the code and change your '
                  'password - somebody knows it.',
        'h_v_lede': 'the code to check this address for signing in to the VPN as <b>{account}</b>:',
        'h_v_lede_anon': 'the code to check this address for signing in to the VPN:',
        'h_v_hello': 'Hello {name},',
        'h_v_hello_anon': 'Hello,',
        'h_v_title': 'VPN · Two-step sign-in',
        'h_v_foot': 'Sent automatically by {site}. Do not reply to this mail.',
        'h_v_facts': 'Type it on the page where you are setting up your sign-in. It is good for '
                     '{minutes} min.',
        'h_v_note': 'If you asked for nothing, delete this mail - without the code nothing '
                    'changes.',
        'h_foot': 'Sent automatically by {site}. Do not reply to this mail.',
        'h_title': 'VPN · Two-step sign-in',
        'admin_subject': 'Your code for the administration: {code}',
        'admin_body': ('Your code to sign in to the administration of {site} is\n\n    {code}\n\n'
                       'It is good for {minutes} min and once. If you are not signing in just '
                       'now, tell nobody the code and change your password - somebody knows '
                       'it.\n\n-- \n{site}'),
        'admin_verify_subject': 'Checking this address for the administration: {code}',
        'admin_verify_body': ('The code to check this address for signing in to the '
                              'administration of {site} is\n\n    {code}\n\nType it on the '
                              'administration\'s sign-in page. It is good for {minutes} min.'
                              '\n\nIf you asked for nothing, delete this mail.\n\n-- \n{site}'),
        'admin_sms': '{code} is your code for the administration ({site}). Good for {minutes} '
                     'min. Tell nobody.',
        'admin_sms_verify': '{code} is the code to check this number for the administration '
                            '({site}).',
        'h_a_title': 'Administration · Second step',
        'h_a_hello': 'Hello {name},', 'h_a_hello_anon': 'Hello,',
        'h_a_lede': 'your code to sign in to the administration as <b>{account}</b>:',
        'h_a_lede_anon': 'your code to sign in to the administration:',
        'h_a_facts': 'Type it on the administration\'s sign-in page. It is good for {minutes} min '
                     'and once.',
        'h_a_warn': 'If you are not signing in just now, tell nobody the code and change your '
                    'password - somebody knows it.',
        'h_a_foot': 'Sent automatically by {site}. Do not reply to this mail.',
        'h_av_title': 'Administration · Second step',
        'h_av_hello': 'Hello {name},', 'h_av_hello_anon': 'Hello,',
        'h_av_lede': 'the code to check this address for signing in to the administration as '
                     '<b>{account}</b>:',
        'h_av_lede_anon': 'the code to check this address for signing in to the administration:',
        'h_av_facts': 'Type it on the administration\'s sign-in page. It is good for {minutes} '
                      'min.',
        'h_av_note': 'If you asked for nothing, delete this mail - without the code nothing '
                     'changes.',
        'h_av_foot': 'Sent automatically by {site}. Do not reply to this mail.',
        'ask_mail': 'Type the code mailed to {dest}',
        'ask_sms': 'Type the code sent by SMS to {dest}',
        'ask_totp': 'Type the code from the app on your phone',
        'again': 'That code was not right - type it again',
    },
}


def token_lang(tok):
    """The language a token's codes and questions are in (1.0.82): its own,
    else the setting's."""
    lang = str((tok or {}).get('lang') or '')
    return lang if lang in CODE_TEXTS else code_lang()


def token_mail_fmt(tok):
    fmt = str((tok or {}).get('mail_fmt') or '')
    if fmt in ('html', 'text'):
        return fmt
    return 'text' if CONFIG.get('code_mail_fmt') == 'text' else 'html'


def code_lang():
    lang = str(CONFIG.get('code_lang') or CONFIG.get('mail_lang') or 'cs')
    return lang if lang in CODE_TEXTS else 'cs'


def code_words(key, lang=None, w=None, **kw):
    """One of the texts of codes, as Settings → Message texts has it
    (1.0.103), its {words} filled in."""
    if w is None:
        w = texts_for('code', lang if lang in CODE_TEXTS else code_lang())
    kw.setdefault('site', str(CONFIG.get('site_name') or socket.gethostname()))
    kw.setdefault('minutes', max(1, int(CONFIG.get('code_ttl_s') or 300) // 60))
    return w[key].format(**kw)


def token_kind(tok):
    k = str((tok or {}).get('kind') or '').strip().lower()
    return k if k in ('mail', 'sms') else 'totp'


def mail_checked(dest):
    dest = str(dest or '').strip()
    if not re.match(r'^[^@\s<>,;"]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,}\Z', dest):
        raise ValueError('that is not a mail address')
    return dest


def phone_checked(dest):
    """A number as +CCCNNN…: spaces, dashes and brackets taken out, the
    country code of the settings put before a number written without one."""
    raw = re.sub(r'[\s().\-/]', '', str(dest or ''))
    if raw.startswith('00'):
        raw = '+' + raw[2:]
    if not raw.startswith('+'):
        pre = str(CONFIG.get('sms_prefix') or '').strip()
        if not pre:
            raise ValueError('write the number with its country code: +420 603 123 456')
        digits = raw.lstrip('0')
        # 420603123456 written without its + (1.0.146): not +420420603123456.
        # Not a number dialled at home with its 0 (1.0.147): 0491 12345678
        # in Germany is 491..., and is not +49 1 12345678.
        if not raw.startswith('0') and pre.lstrip('+') and digits.startswith(pre.lstrip('+')) and \
                len(digits) - len(pre.lstrip('+')) >= 8:
            raw = '+' + digits
        else:
            raw = pre + digits
    if not re.match(r'^\+[1-9][0-9]{7,14}\Z', raw):
        raise ValueError('that is not a phone number - write it as +420 603 123 456')
    return raw


def dest_checked(kind, dest):
    if kind == 'mail':
        return mail_checked(dest)
    if kind == 'sms':
        return phone_checked(dest)
    return ''


def dest_masked(kind, dest):
    """What the VPN and the pages may say of where a code went."""
    dest = str(dest or '')
    if kind == 'mail' and '@' in dest:
        who, _, where = dest.partition('@')
        return '%s%s@%s' % (who[:1], '*' * max(2, min(len(who) - 1, 6)), where)
    if kind == 'sms' and len(dest) > 4:
        return '%s%s%s' % (dest[:4], '*' * (len(dest) - 7), dest[-3:])
    return dest


def code_new():
    digits = int(CONFIG.get('code_digits') or 6)
    return '%0*d' % (digits, secrets.randbelow(10 ** digits))


def code_hash(salt, code):
    key = sealing_key() or b''
    return hmac.new(key + b'|code', ('%s|%s' % (salt, code)).encode('utf-8'),
                    hashlib.sha256).hexdigest()


def code_channels():
    """Which ways of sending can be used at all - set up, not switched off."""
    out = []
    if (CONFIG.get('mail_mode') or 'off') != 'off' and CONFIG.get('mail_from'):
        out.append('mail')
    mode = CONFIG.get('sms_mode') or 'off'
    if (mode == 'http' and CONFIG.get('sms_url')) or \
            (mode == 'spool' and CONFIG.get('sms_spool_dir')) or \
            (mode == 'teltonika' and CONFIG.get('sms_tel_host')):
        out.append('sms')
    return out


def realm_methods(realm):
    """The kinds of token a realm offers, in the order given; the app when
    nothing is said (every realm made before 1.0.76)."""
    raw = (realm or {}).get('methods')
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip().startswith('[') else re.split(r'[,\s]+', raw)
        except ValueError:
            raw = []
    got = [str(x).strip().lower() for x in (raw or []) if str(x).strip().lower() in CODE_KINDS]
    seen = []
    for k in got:
        if k not in seen:
            seen.append(k)
    return seen or ['totp']


# ---- how many were sent ------------------------------------------------------------
# Rows counted for a person by every node (1.0.146): each node writes a key of
# its own - 'codesent:NAME@@NODE' - and reads them all. One key for both made
# by both at once (its first INSERT on each node) came over to the other as a
# second row with the same key, and replication stopped for good.
NODE_KEY_SEP = '@@'


def node_key(prefix, name):
    return '%s:%s%s%s' % (prefix, norm_name(name), NODE_KEY_SEP, node_name())


def node_key_rows(store, prefix, name):
    """Every node's row for `name` (and one written before 1.0.146)."""
    n = norm_name(name)
    return store.db.rows("SELECT k, v FROM meta WHERE k = ? OR k LIKE ? ESCAPE '!'",
                         ('%s:%s' % (prefix, n),
                          '%s:%s%s%%' % (prefix, n.replace('!', '!!').replace('%', '!%')
                                         .replace('_', '!_'), NODE_KEY_SEP)))


def node_key_name(prefix, k):
    """The name a key is counted for, its node taken off."""
    return str(k)[len(prefix) + 1:].split(NODE_KEY_SEP, 1)[0]


def node_key_times(store, prefix, name):
    """The times in every node's row for `name`."""
    out = []
    for r in node_key_rows(store, prefix, name):
        try:
            out += [float(x) for x in json.loads(r['v'] or '[]')]
        except (ValueError, TypeError):
            continue
    return sorted(out)


def node_key_add(store, prefix, name, keep, most=None, limit=None):
    """`time.time()` added to this node's own row for `name`, written only over
    what was read; the times older than `keep` seconds dropped. True once
    written. With `limit`: False, nothing written, when every node's rows
    together already hold that many - counted again at each try, so of
    requests at once only as many as the limit get past (1.0.147)."""
    k = node_key(prefix, name)
    for _ in range(8):
        t = time.time()
        raw = store.get_meta(k)
        try:
            times = [float(x) for x in json.loads(raw or '[]')]
        except (ValueError, TypeError):
            times = []
        times = [x for x in times if t - x < keep]
        if limit is not None:
            others = 0
            for r in node_key_rows(store, prefix, name):
                if r['k'] == k:
                    continue
                try:
                    others += len([x for x in json.loads(r['v'] or '[]') if t - float(x) < keep])
                except (ValueError, TypeError):
                    continue
            if others + len(times) >= limit:
                return False
        times.append(t)
        if most:
            times = times[-most:]
        new = json.dumps(times)
        if raw is None:
            try:
                store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, new))
                return True
            except Exception:                           # noqa: BLE001
                continue
        if store.db.run('UPDATE meta SET v = ? WHERE k = ? AND v = ?', (new, k, raw)):
            return True
    return False


def node_key_drop(store, prefix, name):
    n = 0
    for r in node_key_rows(store, prefix, name):
        n += store.db.run('DELETE FROM meta WHERE k = ?', (r['k'],)) or 0
    return n


def code_send_allowed(store, name):
    """Whether one more code may be sent to `name` now; counted in the
    database so both nodes count together - each in a row of its own
    (1.0.146), written only over what was read (1.0.94)."""
    span = 60 * int(CONFIG.get('code_send_window_min') or 15)
    return node_key_add(store, 'codesent', name, span,
                        limit=int(CONFIG.get('code_send_max') or 5))


def code_send_wait_min(store, name):
    """How many minutes until one more code may go to `name` (1.0.116) - not
    the whole window, which the page said even when a minute was left."""
    span = 60 * int(CONFIG.get('code_send_window_min') or 15)
    limit = int(CONFIG.get('code_send_max') or 5)
    try:
        times = node_key_times(store, 'codesent', name)
    except (ValueError, TypeError):
        times = []
    t = time.time()
    times = [x for x in times if t - x < span]
    if len(times) < limit:
        return 1
    return max(1, int(-(-(times[len(times) - limit] + span - t) // 60)))


# ---- sending -------------------------------------------------------------------------
class SmsError(RuntimeError):
    pass


def sms_plain(text):
    """The text without accents (1.0.81): one letter outside the GSM
    alphabet makes the whole SMS the wide one, 70 characters a part."""
    if not CONFIG.get('sms_plain', 1):
        return text
    import unicodedata
    out = unicodedata.normalize('NFKD', str(text))
    out = ''.join(c for c in out if not unicodedata.combining(c))
    return out.replace('–', '-').replace('—', '-').replace('„', '"').replace('“', '"')


# ---- a Teltonika gateway (TRB140, RUT…), as zigmon speaks to it (1.0.81) -----------
TELTONIKA = {'token': None, 'until': 0.0, 'modem': None, 'last': 0.0}
TELTONIKA_LOCK = threading.Lock()


def _tel_url(path, params=None):
    host = str(CONFIG.get('sms_tel_host') or '').strip().rstrip('/')
    if not host:
        raise SmsError('no address of the Teltonika gateway is set - Settings → Codes by e-mail '
                       'and SMS')
    scheme = 'https' if CONFIG.get('sms_tel_https', 1) else 'http'
    if '://' in host:
        scheme, host = host.split('://', 1)
    url = '%s://%s%s' % (scheme, host, path)
    if params:
        url += '?' + urllib.parse.urlencode(params)
    return url


SMS_CA_META = 'sms_ca'          # the gateway's certificates trusted (1.0.89)


def sms_ca_pem(store=None):
    store = store or HA_STORE.get('store')
    if store is None:
        return ''
    try:
        return str(store.get_meta(SMS_CA_META) or '')
    except Exception:                                   # noqa: BLE001
        return ''


def sms_ca_set(store, pem, mode='add', fingerprint=''):
    """The certificates the Teltonika gateway is checked against - each added
    and taken out by itself, as the mail server's."""
    pem = str(pem or '').strip()
    have = split_certificates(sms_ca_pem(store))
    if mode == 'add':
        new = split_certificates(pem)
        if not new or not all(describe_certificate(b) for b in new):
            raise ValueError('that is not a certificate this can read: a PEM certificate '
                             'starts -----BEGIN CERTIFICATE-----')
        seen = {c['fingerprint'] for c in describe_certificates('\n'.join(have))}
        have += [b for b, c in zip(new, describe_certificates('\n'.join(new)))
                 if c['fingerprint'] not in seen]
    elif mode == 'drop':
        keep = [b for b, c in zip(have, describe_certificates('\n'.join(have)))
                if c['fingerprint'] != fingerprint]
        if len(keep) == len(have):
            raise ValueError('that certificate is not among the ones kept')
        have = keep
    elif mode == 'clear':
        have = []
    else:
        raise ValueError('add, drop or clear?')
    store.set_meta(SMS_CA_META, '\n'.join(have))
    return describe_certificates('\n'.join(have))


def _tel_is_name(host):
    host = host.split('://', 1)[-1].split('/')[0]
    if host.startswith('['):
        return False
    host = host.rsplit(':', 1)[0] if host.count(':') == 1 else host
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True


def _tel_ssl():
    if not CONFIG.get('sms_tel_verify'):
        # A TRB makes its own certificate; nothing can check it.
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    pem = sms_ca_pem()
    if not pem.strip():
        return ssl.create_default_context()
    # Only what was imported (1.0.89): the gateway's own certificate, or the
    # authority of your own that signed it. A gateway reached by its address
    # has no name to check against - its certificate is: the chain must end
    # in one of these.
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    try:
        ctx.load_verify_locations(cadata=pem)
    except (ssl.SSLError, ValueError) as e:
        raise SmsError('the certificates kept for the gateway cannot be read: %s' % e)
    # Any certificate imported is an anchor of its own (1.0.92): a TRB sends
    # only its own certificate, signed by a "ca" it never shows, and that
    # certificate alone - read from it - was refused as "unable to get local
    # issuer certificate". The strict checks of 3.13 are left out too: a
    # gateway's own certificate is not a web server's.
    ctx.verify_flags |= getattr(ssl, 'VERIFY_X509_PARTIAL_CHAIN', 0x80000)
    ctx.verify_flags &= ~getattr(ssl, 'VERIFY_X509_STRICT', 0x20)
    ctx.check_hostname = _tel_is_name(str(CONFIG.get('sms_tel_host') or ''))
    return ctx


def tel_peer_chain():
    """The certificates the gateway shows, read without checking them - for
    an administrator to look at and trust (1.0.89)."""
    host = str(CONFIG.get('sms_tel_host') or '').strip().rstrip('/')
    if not host:
        raise SmsError('no address of the Teltonika gateway is set')
    host = host.split('://', 1)[-1].split('/')[0]
    port = 443
    if host.startswith('['):
        name, _, rest = host[1:].partition(']')
        if rest.startswith(':'):
            port = int(rest[1:])
    elif host.count(':') == 1:
        name, port = host.split(':')
        port = int(port)
    else:
        name = host
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((name, port), timeout=10) as raw:
            with ctx.wrap_socket(raw, server_hostname=name if _tel_is_name(name) else None) as tls:
                chain = []
                if hasattr(tls, 'get_unverified_chain'):
                    try:
                        chain = [c if isinstance(c, bytes) else c.public_bytes(1)
                                 for c in tls.get_unverified_chain() or []]
                    except Exception:                   # noqa: BLE001
                        chain = []
                if not chain:
                    chain = [tls.getpeercert(binary_form=True)]
    except (OSError, ssl.SSLError) as e:
        raise SmsError('%s:%d could not be reached over TLS: %s' % (name, port, e))
    pems = [ssl.DER_cert_to_PEM_cert(d).strip() for d in chain if d]
    return '\n'.join(pems)


def _tel_password():
    pw = CONFIG.get('sms_tel_password') or ''
    return (unseal_secret(pw) or '') if pw else ''


class _TelAnswer(object):
    """An answer already read - so that it could be written into the log."""

    def __init__(self, status, body):
        self.status, self._body = status, body

    def read(self, n=-1):
        got = self._body if n is None or n < 0 else self._body[:n]
        self._body = b'' if n is None or n < 0 else self._body[n:]
        return got

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


_TEL_TEXT = threading.local()     # the text being sent, kept out of the debug log


def _tel_hidden(words):
    """A request or an answer as the debug log may hold it: no password,
    no token (1.0.113), and not the text with its live code (1.0.146)."""
    text = getattr(_TEL_TEXT, 'v', '') or ''
    if text:
        for form in {text, urllib.parse.quote(text, safe=''), urllib.parse.quote_plus(text),
                     json.dumps(text)[1:-1], json.dumps(text, ensure_ascii=False)[1:-1]}:
            if form:
                words = words.replace(form, '<the text, %d characters>' % len(text))
    words = re.sub(r'(?i)("(?:password|token)"\s*:\s*")[^"]*', r'\1***', words)
    words = re.sub(r'(?i)((?:password|token)=)[^&\s]*', r'\1***', words)
    return re.sub(r'(?i)(Bearer )\S+', r'\1***', words)


def _tel_open(req, timeout=20.0):
    loud = debugging('codes')
    began = time.time()
    if loud:
        body = req.data.decode('utf-8', 'replace') if isinstance(req.data, bytes) else ''
        log('sms: -> %s %s%s (waits %d s)' % (req.get_method(), _tel_hidden(req.full_url),
                                             (' ' + _tel_hidden(body)[:300]) if body else '',
                                             timeout), 'debug')
    try:
        r = urllib.request.urlopen(req, timeout=timeout, context=_tel_ssl()
                                   if req.full_url.startswith('https') else None)
        if not loud:
            return r
        with r:
            body = r.read(65536)
            status = getattr(r, 'status', 200)
        log('sms: <- HTTP %s in %.2f s: %s' % (status, time.time() - began, _tel_hidden(
            body.decode('utf-8', 'replace'))[:400]), 'debug')
        return _TelAnswer(status, body)
    except urllib.error.URLError as e:
        if loud:
            _tel_said_failed(e, began)
        # The certificate refused (1.0.89): nothing was sent, and the page
        # says what to do about it.
        if isinstance(getattr(e, 'reason', None), ssl.SSLCertVerificationError):
            raise SmsError('the gateway\'s certificate did not pass the check (%s): import its '
                           'certificate or the authority that signed it under Settings → Codes '
                           'by e-mail and SMS, or switch Check its certificate off'
                           % (getattr(e.reason, 'verify_message', '') or e.reason))
        raise
    except Exception as e:                              # noqa: BLE001
        if loud:
            _tel_said_failed(e, began)
        raise


def _tel_said_failed(e, began):
    extra = ''
    if isinstance(e, urllib.error.HTTPError):
        try:
            said = e.read(400)
            extra = ': ' + _tel_hidden(said.decode('utf-8', 'replace'))
            e.read = (lambda b: (lambda n=-1: b))(said)         # the caller reads it too
        except Exception:                               # noqa: BLE001
            pass
    log('sms: <- FAILED after %.2f s: %s %s%s' % (time.time() - began, type(e).__name__,
                                               getattr(e, 'reason', e), extra), 'debug')


def _tel_never_arrived(e):
    """Whether a failed request certainly never reached the gateway - a
    refused or reset connection. A read that timed out did reach it: the box
    took the message and has not answered, and sending it again is a second
    SMS on the person's phone (zigmon's lesson)."""
    if isinstance(e, socket.timeout):
        return False
    reason = getattr(e, 'reason', e)
    if isinstance(reason, socket.timeout):
        return False
    words = str(e).lower()
    if 'timed out' in words or 'timeout' in words:
        return False
    return isinstance(reason, (ConnectionRefusedError, ConnectionResetError,
                               ConnectionAbortedError, socket.gaierror)) or \
        any(w in words for w in ('refused', 'reset by peer', 'not known', 'no route',
                                 'broken pipe'))


def _tel_who():
    """What a login is for: another address, user or password is another
    login - a token kept from before a change is not used after it."""
    return hashlib.sha256(('%s|%s|%s|%s' % (CONFIG.get('sms_tel_host'), CONFIG.get('sms_tel_https'),
                                            CONFIG.get('sms_tel_user'), _tel_password()))
                          .encode('utf-8')).hexdigest()


def _tel_token(fresh=False):
    """A login on RutOS's own API: a token that lasts five minutes, renewed a
    minute before."""
    now = time.time()
    if TELTONIKA.get('who') != _tel_who():
        TELTONIKA.update(token=None, modem=None, who=_tel_who())
    if not fresh and TELTONIKA['token'] and now < TELTONIKA['until']:
        return TELTONIKA['token']
    body = json.dumps({'username': CONFIG.get('sms_tel_user') or 'admin',
                       'password': _tel_password()}).encode()
    tries = 0
    while True:
        tries += 1
        req = urllib.request.Request(_tel_url('/api/login'), data=body, method='POST',
                                     headers={'Content-Type': 'application/json'})
        try:
            with _tel_open(req, 15) as r:
                answer = json.loads(r.read() or b'{}')
            break
        except urllib.error.HTTPError as e:
            raise SmsError('the Teltonika would not let otp in (HTTP %d) - check its user and '
                           'password, and that the user may use the API' % e.code)
        except (urllib.error.URLError, OSError, ValueError) as e:
            # Signing in is asked again once (1.0.113): a box busy with the
            # modem leaves a login unanswered now and then, and asking again
            # sends nothing twice.
            if tries < 2 and not isinstance(e, ValueError):
                log('sms: the Teltonika did not answer the sign-in (%s) - asked again'
                    % getattr(e, 'reason', e), 'warn')
                time.sleep(1)
                continue
            raise SmsError('the Teltonika could not be reached%s: %s' % (
                ' (asked twice)' if tries > 1 else '', getattr(e, 'reason', e)))
    data = answer.get('data') or {}
    token = data.get('token') or answer.get('token') or ''
    if not token:
        raise SmsError('the Teltonika gave no token: %s' % json.dumps(answer)[:150])
    TELTONIKA['token'] = token
    TELTONIKA['until'] = now + max(30.0, float(data.get('expires') or 299) - 60)
    return token


def _tel_rest(path, method='GET', payload=None, timeout=20.0, again=True):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(_tel_url('/api' + path), data=data, method=method,
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': 'Bearer ' + _tel_token()})
    try:
        with _tel_open(req, timeout) as r:
            answer = json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        said = ''
        try:
            said = e.read(300).decode('utf-8', 'replace')
        except Exception:                               # noqa: BLE001
            pass
        if e.code in (401, 403) and again:
            TELTONIKA['token'] = None                   # gone stale
            return _tel_rest(path, method, payload, timeout, again=False)
        raise SmsError('the Teltonika answered %s %s with HTTP %d %s' % (method, path, e.code,
                                                                         said))
    if answer.get('success') is False:
        raise SmsError('the Teltonika refused %s: %s' % (path, json.dumps(
            answer.get('errors') or answer)[:200]))
    return answer.get('data', answer)


def _tel_modem():
    if CONFIG.get('sms_tel_modem'):
        return str(CONFIG['sms_tel_modem']).strip()
    if TELTONIKA.get('who') != _tel_who():
        TELTONIKA.update(token=None, modem=None, who=_tel_who())
    if TELTONIKA['modem']:
        return TELTONIKA['modem']
    rows = _tel_rest('/modems/status') or []
    if isinstance(rows, dict):
        rows = [rows]
    first = next((r for r in rows if isinstance(r, dict) and r.get('id')), None)
    if not first:
        raise SmsError('the Teltonika named no modem')
    TELTONIKA['modem'] = str(first['id'])
    return TELTONIKA['modem']


def tel_send(to, text):
    """One SMS through a Teltonika, one at a time: the box sends one message
    after another, and a second asked for at once is taken and then left
    unanswered for a minute."""
    waited = time.time()
    with TELTONIKA_LOCK:
        gap = 2.0 - (time.time() - TELTONIKA['last'])
        if gap > 0:
            time.sleep(gap)
        loud = debugging('codes')
        if loud:
            log('sms: to %s, %d characters, through the Teltonika %s (%s), after %.1f s in the '
                'queue' % (to[:-3] + '***' if len(to) > 6 else to, len(text),
                           CONFIG.get('sms_tel_host'), CONFIG.get('sms_tel_api') or 'rest',
                           time.time() - waited), 'debug')
        began = time.time()
        _TEL_TEXT.v = text
        try:
            said = _tel_send(to, text)
            if loud:
                log('sms: done in %.1f s - %s' % (time.time() - began, said), 'debug')
            return said
        except Exception as e:
            if loud:
                log('sms: FAILED after %.1f s - %s' % (time.time() - began, e), 'debug')
            raise
        finally:
            _TEL_TEXT.v = ''
            TELTONIKA['last'] = time.time()


def _tel_send(to, text):
    parts = 1 if len(text) <= (160 if all(ord(c) < 128 for c in text) else 70) else 2
    timeout = 20.0 * parts
    if (CONFIG.get('sms_tel_api') or 'rest') == 'cgi':
        number = '00' + to.lstrip('+')                  # Teltonika's CGI wants 00420…
        url = _tel_url('/cgi-bin/sms_send', {'username': CONFIG.get('sms_tel_user') or '',
                                             'password': _tel_password(), 'number': number,
                                             'text': text})
        tries = 0
        while True:
            tries += 1
            try:
                with _tel_open(urllib.request.Request(url), timeout) as r:
                    said = r.read(400).decode('utf-8', 'replace').strip()
                break
            except urllib.error.HTTPError as e:
                raise SmsError('the Teltonika answered HTTP %d: %s' % (
                    e.code, e.read(200).decode('utf-8', 'replace')))
            except (urllib.error.URLError, OSError) as e:
                if tries < 3 and _tel_never_arrived(e):
                    time.sleep(tries)
                    continue
                if not _tel_never_arrived(e):
                    return 'no answer from the Teltonika in %d s - the SMS has most likely gone' \
                        % timeout
                raise SmsError('the Teltonika could not be reached: %s' % getattr(e, 'reason', e))
        if 'error' in said.lower() and not said.lower().startswith('ok'):
            raise SmsError('the Teltonika said: %s' % said[:200])
        return 'the Teltonika said: %s' % (said[:120] or 'OK')
    tries = 0
    while True:
        tries += 1
        try:
            # How long each step took, said with the answer (1.0.109): a
            # test that took long tells whether it was the login, finding
            # the modem or the sending itself - RutOS answers the send only
            # once the modem has given the SMS to the network.
            t0 = time.time()
            _tel_token()
            t1 = time.time()
            modem = _tel_modem()
            t2 = time.time()
            out = _tel_rest('/messages/actions/send', 'POST',
                            {'data': {'number': to, 'message': text, 'modem': modem}},
                            timeout=timeout)
            t3 = time.time()
            steps = []
            if t1 - t0 > 0.05:
                steps.append('signing in %.1f s' % (t1 - t0))
            if t2 - t1 > 0.05:
                steps.append('finding the modem %.1f s' % (t2 - t1))
            steps.append('the modem sending it %.1f s' % (t3 - t2))
            return 'the Teltonika took it (%s; %s)' % (', '.join(steps), json.dumps(out)[:60])
        except SmsError:
            raise
        except (urllib.error.URLError, OSError) as e:
            if tries < 3 and _tel_never_arrived(e):
                TELTONIKA['token'] = None               # a new connection, a new login
                time.sleep(tries)
                continue
            if not _tel_never_arrived(e):
                return 'no answer from the Teltonika in %d s - the SMS has most likely gone' \
                    % timeout
            raise SmsError('the Teltonika could not be reached: %s' % getattr(e, 'reason', e))


def tel_check():
    """Whether the gateway is there and takes the password - nothing sent."""
    if (CONFIG.get('sms_tel_api') or 'rest') == 'cgi':
        url = _tel_url('/cgi-bin/sms_list', {'username': CONFIG.get('sms_tel_user') or '',
                                             'password': _tel_password()})
        try:
            with _tel_open(urllib.request.Request(url), 15) as r:
                said = r.read(300).decode('utf-8', 'replace')
        except (urllib.error.URLError, OSError) as e:
            raise SmsError('the Teltonika could not be reached: %s' % getattr(e, 'reason', e))
        if 'error' in said.lower() and 'no messages' not in said.lower():
            raise SmsError('the Teltonika said: %s' % said.strip()[:150])
        return 'the Teltonika answered and took the password'
    TELTONIKA['token'] = None
    _tel_token(fresh=True)
    TELTONIKA['modem'] = None
    return 'the Teltonika let otp in; its modem is %s' % _tel_modem()


# What a modem's status says, in the order shown (1.0.113). RutOS 7 names
# them so; a field it does not have is left out.
TEL_MODEM_FIELDS = (
    ('name', 'Modem'), ('model', 'Model'), ('operator', 'Operator'),
    ('ntype', 'Network'), ('conntype', 'Connection'), ('band', 'Band'),
    ('state', 'State'), ('operator_state', 'Registered'), ('netstate', 'Network state'),
    ('active_sim', 'SIM in use'), ('simstate', 'SIM'), ('pinstate', 'PIN'),
    ('signal_quality', 'Signal quality (%)'), ('rssi', 'RSSI (dBm)'), ('rsrp', 'RSRP (dBm)'),
    ('rsrq', 'RSRQ (dB)'), ('sinr', 'SINR (dB)'), ('temperature', 'Temperature (C)'),
    ('volte', 'VoLTE'), ('sms_center_address', 'SMS centre'), ('imei', 'IMEI'),
    ('version', 'Modem firmware'))


def tel_modem_words(row):
    out = [('id', str(row.get('id') or ''))]
    for k, words in TEL_MODEM_FIELDS:
        v = row.get(k)
        if v in (None, '', [], {}):
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v)[:80]
        out.append((words, str(v)[:80]))
    if len(out) < 4:
        # Another firmware, other names: what it said, plainly.
        for k, v in list(row.items())[:12]:
            if k != 'id' and isinstance(v, (str, int, float)) and str(v) != '':
                out.append((str(k)[:30], str(v)[:80]))
    return out


def tel_test():
    """The gateway tried, step by step, without sending anything (1.0.113):
    reached, signed in, its modems and what each says about the network."""
    mode = (CONFIG.get('sms_tel_api') or 'rest')
    host = str(CONFIG.get('sms_tel_host') or '').strip()
    out = {'ok': False, 'steps': [], 'modems': [], 'api': mode, 'host': host,
           'https': bool(CONFIG.get('sms_tel_https')),
           'checked': bool(CONFIG.get('sms_tel_https') and CONFIG.get('sms_tel_verify'))}
    if not host:
        out['steps'].append({'what': 'the address', 'ok': False, 'secs': 0,
                             'said': 'no address of the gateway is saved'})
        return out

    def step(what, fn):
        t = time.time()
        try:
            got = fn()
        except SmsError as e:
            out['steps'].append({'what': what, 'ok': False, 'secs': round(time.time() - t, 2),
                                 'said': str(e)})
            return None, False
        out['steps'].append({'what': what, 'ok': True, 'secs': round(time.time() - t, 2),
                             'said': got if isinstance(got, str) else ''})
        return got, True

    with TELTONIKA_LOCK:
        if mode == 'cgi':
            _x, ok = step('signing in (Post/Get)', tel_check)
            out['ok'] = ok
            return out
        TELTONIKA['token'] = None
        TELTONIKA['modem'] = None
        _x, ok = step('signing in', lambda: (_tel_token(fresh=True) and 'let in as %s'
                                            % (CONFIG.get('sms_tel_user') or 'admin')))
        if not ok:
            return out
        rows, ok = step('its modems', lambda: _tel_rest('/modems/status'))
        if not ok:
            return out
        if isinstance(rows, dict):
            rows = [rows]
        rows = [r for r in (rows or []) if isinstance(r, dict)]
        want = str(CONFIG.get('sms_tel_modem') or '').strip()
        chosen = want or (str(rows[0].get('id')) if rows and rows[0].get('id') else '')
        for r in rows[:6]:
            out['modems'].append({'id': str(r.get('id') or ''), 'sends': str(r.get('id')) == chosen,
                                  'fields': tel_modem_words(r)})
        out['steps'][-1]['said'] = '%d modem(s)' % len(rows)
        if want and not any(str(r.get('id')) == want for r in rows):
            out['steps'].append({'what': 'the modem set', 'ok': False, 'secs': 0,
                                 'said': 'the gateway has no modem %s - it has %s' % (
                                     want, ', '.join(str(r.get('id')) for r in rows) or 'none')})
            return out
        if not chosen:
            out['steps'].append({'what': 'the modem', 'ok': False, 'secs': 0,
                                 'said': 'the gateway named no modem'})
            return out
        TELTONIKA['modem'] = chosen
        out['ok'] = True
    return out


def sms_send(to, text):
    """One SMS. Returns what the gateway said; raises SmsError."""
    mode = CONFIG.get('sms_mode') or 'off'
    if mode == 'off':
        raise SmsError('sending SMS is switched off - Settings → Codes by mail and SMS')
    text = sms_plain(text)
    if mode == 'teltonika':
        return tel_send(to, text)
    if mode == 'spool':
        folder = Path(str(CONFIG.get('sms_spool_dir') or '').strip())
        if not folder.is_dir():
            raise SmsError('the spool folder %s is not there' % folder)
        # smstools3: a file "To: 420…", an empty line, the text. Written
        # beside and renamed in, so the daemon never reads half of one.
        body = 'To: %s\nAlphabet: UTF-8\n\n%s\n' % (to.lstrip('+'), text)
        name = 'otp-%d-%s' % (int(time.time()), secrets.token_hex(4))
        tmp = folder / ('.' + name)
        try:
            with open(str(tmp), 'w', encoding='utf-8') as f:
                f.write(body)
            os.chmod(str(tmp), 0o664)
            os.rename(str(tmp), str(folder / name))
        except OSError as e:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise SmsError('it could not be written into %s: %s' % (folder, e))
        return 'written into %s as %s' % (folder, name)
    url = str(CONFIG.get('sms_url') or '').strip()
    if not url:
        raise SmsError('no gateway address is set - Settings → Codes by mail and SMS')
    token = unseal_secret(CONFIG.get('sms_token') or '') or '' if CONFIG.get('sms_token') else ''
    vals = {'to': to, 'to_digits': to.lstrip('+'), 'text': text, 'token': token}

    def fill(tpl, how):
        def one(m):
            k = m.group(1)
            v = vals.get(k)
            if v is None:
                return m.group(0)
            if how == 'url':
                return urllib.parse.quote(v, safe='')
            if how == 'json':
                return json.dumps(v)[1:-1]
            return v
        return re.sub(r'\{(to|to_digits|text|token)\}', one, tpl)
    full = fill(url, 'url')
    method = (CONFIG.get('sms_method') or 'POST').upper()
    tpl = str(CONFIG.get('sms_body') or '')
    data, ctype = None, None
    if method == 'POST':
        if tpl.strip().startswith('{'):
            data, ctype = fill(tpl, 'json').encode('utf-8'), 'application/json'
        elif tpl.strip():
            data, ctype = fill(tpl, 'url').encode('utf-8'), 'application/x-www-form-urlencoded'
        else:
            data = b''
    req = urllib.request.Request(full, data=data, method=method)
    if ctype:
        req.add_header('Content-Type', ctype)
    for line in str(CONFIG.get('sms_headers') or '').splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            if k.strip():
                req.add_header(k.strip(), fill(v.strip(), 'raw'))
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            said = r.read(4000).decode('utf-8', 'replace')
            status = r.status
    except urllib.error.HTTPError as e:
        _TEL_TEXT.v = text
        try:
            body = _tel_hidden(e.read(300).decode('utf-8', 'replace'))
        finally:
            _TEL_TEXT.v = ''
        raise SmsError('the gateway answered %d: %s' % (e.code, body))
    except (urllib.error.URLError, OSError) as e:
        raise SmsError('the gateway could not be reached: %s' % getattr(e, 'reason', e))
    want = str(CONFIG.get('sms_ok_status') or '').strip()
    # A gateway that says back what it was sent (1.0.147): not the code
    # into the events and the log with it.
    _TEL_TEXT.v = text
    try:
        said = _tel_hidden(said)
    finally:
        _TEL_TEXT.v = ''
    if want and want.lower() not in said.lower():
        raise SmsError('the gateway answered %d without "%s": %s' % (status, want, said[:300]))
    return 'the gateway answered %d%s' % (status, (': ' + said[:200]) if said.strip() else '')


def code_mail_html(code, purpose, lang, name='', display='', w=None):
    """The mail of a code in the same shape and colours as a token's mail
    with its QR code (1.0.79): the blue band, the white card, the code in a
    grey box, the warning in orange - tables and styles on each element, as
    every mail program shows them alike. Its words as Settings → Message
    texts has them (1.0.103), or `w` - the editor's, not yet saved."""
    lang = lang if lang in CODE_TEXTS else code_lang()
    if w is None:
        w = texts_for('code', lang)
    h = lambda t: html.escape(str(t or ''), quote=True)
    site = str(CONFIG.get('site_name') or socket.gethostname())
    issuer = str(CONFIG.get('totp_issuer') or '') or site
    minutes = max(1, int(CONFIG.get('code_ttl_s') or 300) // 60)
    # name@domain kept plain text, as in the token's mail.
    acc = ('<span style="white-space:nowrap">%s</span>' % h(name).replace('@', '@&#8205;')
           if name else '')
    font = "font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
    rows = []
    cp = code_purpose(purpose)
    v = cp['p']
    hello = (w['h_%shello' % v].format(name=h(display)) if display
             else w['h_%shello_anon' % v].format())
    if hello.strip():
        rows.append('<p style="margin:0 0 6px;font-size:16px;color:#111827">%s</p>' % hello)
    lede = (w['h_%slede' % v].format(account=acc) if name
            else w['h_%slede_anon' % v].format())
    facts, note, warn = w['h_%sfacts' % v], w[cp['note']], cp['warn']
    if lede.strip():
        rows.append('<p style="margin:0 0 18px;font-size:15px;line-height:1.55;color:#374151">'
                    '%s</p>' % lede)
    spaced = ' '.join(code[i:i + 3] for i in range(0, len(code), 3)) if len(code) == 6 else code
    rows.append('<table role="presentation" width="100%%" cellspacing="0" cellpadding="0" '
                'border="0" style="margin:0 0 10px"><tr><td align="center">'
                '<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>'
                '<td align="center" bgcolor="#f3f4f6" style="padding:16px 30px;background:#f3f4f6;'
                'border:1px solid #e5e7eb;border-radius:12px;font-family:Consolas,Menlo,'
                '\'Courier New\',monospace;font-size:34px;font-weight:700;letter-spacing:6px;'
                'color:#111827;white-space:nowrap">%s</td></tr></table></td></tr></table>' % h(spaced))
    if facts.strip():
        rows.append('<p style="margin:0 0 22px;font-size:13.5px;line-height:1.5;color:#6b7280;'
                    'text-align:center;%s">%s</p>' % (font, facts.format(minutes=minutes)))
    else:
        rows.append('<div style="height:12px;line-height:12px;font-size:1px">&nbsp;</div>')
    note = note.format()
    if not note.strip():
        pass
    elif warn:
        rows.append('<table role="presentation" width="100%%" cellspacing="0" cellpadding="0" '
                    'border="0"><tr><td bgcolor="#fff7ed" style="padding:12px 16px;'
                    'background:#fff7ed;border-left:4px solid #f59e0b;font-size:13px;'
                    'line-height:1.5;color:#7c2d12;%s">%s</td></tr></table>' % (font, note))
    else:
        rows.append('<table role="presentation" width="100%%" cellspacing="0" cellpadding="0" '
                    'border="0"><tr><td bgcolor="#eff6ff" style="padding:12px 16px;'
                    'background:#eff6ff;border-left:4px solid #2563eb;font-size:13px;'
                    'line-height:1.5;color:#1e3a8a;%s">%s</td></tr></table>' % (font, note))
    subject = w[cp['subject']].format(code=code, site=site, minutes=minutes)
    title = w['h_%stitle' % v].format(site=site)
    foot = w['h_%sfoot' % v].format(site=h(site))
    return ('<!doctype html><html lang="%s" xmlns:v="urn:schemas-microsoft-com:vml" '
            'xmlns:o="urn:schemas-microsoft-com:office:office"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title>'
            '<!--[if mso]><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch>'
            '</o:OfficeDocumentSettings></xml><![endif]--></head>'
            '<body style="margin:0;padding:0;background:#f3f4f6;%s">'
            '<table role="presentation" width="100%%" cellspacing="0" cellpadding="0" '
            'border="0" bgcolor="#f3f4f6" style="background:#f3f4f6"><tr><td align="center" '
            'style="padding:28px 12px">'
            '<table role="presentation" width="560" cellspacing="0" cellpadding="0" border="0" '
            'bgcolor="#ffffff" style="max-width:560px;width:100%%;background:#ffffff;'
            'border-radius:14px;overflow:hidden;border:1px solid #e5e7eb">'
            '<tr><td bgcolor="#1e3a8a" style="background:#1e3a8a;padding:20px 28px;'
            'color:#ffffff;%s">'
            '<p style="margin:0;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;'
            'color:#c7d2fe">%s</p><p style="margin:4px 0 0;font-size:20px;font-weight:700;'
            'color:#ffffff">%s</p></td></tr>'
            '<tr><td style="padding:26px 28px;%s">%s</td></tr>'
            '<tr><td style="padding:14px 28px 22px;font-size:12px;color:#9ca3af;%s;'
            'border-top:1px solid #f3f4f6">%s</td></tr></table></td></tr></table></body></html>'
            % (lang, h(subject), font, font, h(issuer), h(title), font, ''.join(rows),
               font, foot))


def code_message(kind, to, code, purpose='signin', lang=None, name='', display='', fmt=None,
                 w=None):
    """The mail or the SMS text of a code. `w`: the words to use instead of
    those saved - the message texts editor's test (1.0.103)."""
    cp = code_purpose(purpose)
    if kind == 'sms':
        return code_words(cp['sms'], lang=lang, w=w, code=code)
    site = str(CONFIG.get('site_name') or socket.gethostname())
    msg = EmailMessage()
    msg['Subject'] = code_words(cp['subject'], lang=lang, w=w, code=code)
    sender = str(CONFIG.get('mail_from') or '').strip()
    if not sender:
        raise MailError('no sender address is set - Settings → Mail → From (address)')
    msg['From'] = formataddr((str(CONFIG.get('mail_from_name') or site), sender))
    msg['To'] = to
    if CONFIG.get('mail_reply_to'):
        msg['Reply-To'] = str(CONFIG.get('mail_reply_to'))
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=sender.rsplit('@', 1)[-1] or None)
    msg['Auto-Submitted'] = 'auto-generated'
    msg.set_content(code_words(cp['body'], lang=lang,
                               w=w, code=code))
    if (fmt or ('text' if CONFIG.get('code_mail_fmt') == 'text' else 'html')) != 'text':
        msg.add_alternative(code_mail_html(code, purpose, lang, name, display, w=w),
                            subtype='html')
    return msg


def code_send(store, kind, to, code, purpose='signin', name='', lang=None, fmt=None,
              display=None):
    """code_send_now, with the code taken out of whatever the server said
    (1.0.136): an SMS gateway that echoes the message put a live code into
    the events and the log."""
    def hide(t):
        return str(t).replace(str(code), '******') if code else str(t)
    try:
        return hide(code_send_now(store, kind, to, code, purpose, name, lang, fmt, display))
    except MailError as e:
        new = MailError(hide(e), steps=e.steps, permanent=e.permanent)
        for k, v in vars(e).items():
            if k not in ('steps', 'permanent'):
                setattr(new, k, v)
        raise new
    except SmsError as e:
        raise SmsError(hide(e))


def code_send_now(store, kind, to, code, purpose='signin', name='', lang=None, fmt=None,
                  display=None):
    """A code sent now; what the server said, or raises MailError/SmsError.
    In the token's own language and mail format unless given (1.0.82).
    `display` given: `name` is an account of the administration, not a
    token's (1.0.127) - no token is looked up for it."""
    tok = None
    if name and display is None:
        try:
            tok = store.token(name)
        except Exception:                               # noqa: BLE001
            tok = None
    lang = lang if lang in CODE_TEXTS else (token_lang(tok) if tok else None)
    if kind == 'mail':
        if display is None:
            display = (tok or {}).get('display') or ''
        msg = code_message('mail', to, code, purpose, lang=lang, name=name, display=display,
                           fmt=fmt or (token_mail_fmt(tok) if tok else None))
        # Through the outgoing mail (1.0.95): greylisted, it is tried again
        # while the code is good - and the person gets it a minute later
        # rather than never.
        try:
            steps = mail_deliver(store, msg, [to], kind=code_purpose(purpose)['queue'],
                                 name=name, purpose=purpose,
                                 expires=time.time() + int(CONFIG.get('code_ttl_s') or 300))
        except MailError as e:
            if e.queued == 'waiting':
                return 'not taken yet (%s) - it waits in the outgoing mail and is tried again' % e
            raise
        last = [s for s in steps if s.get('ok')]
        return (last[-1].get('said') or 'sent') if last else 'sent'
    if kind == 'sms':
        return sms_send(to, code_message('sms', to, code, purpose, lang=lang))
    raise ValueError('%s tokens get no codes sent' % kind)


CODE_LOCK = threading.Lock()
CODE_SENDING = threading.BoundedSemaphore(8)
CODE_WAITING = [0]
CODE_WAITING_MOST = 200


def code_send_later(store, kind, to, code, name, rid=''):
    """Sent by a thread of its own: the VPN gets its Access-Challenge at once
    rather than after a slow mail server. At most 8 at a time, and no more
    than 200 waiting (1.0.136): a mail server that hung kept a thread per
    code for minutes, without end."""
    with CODE_LOCK:
        if CODE_WAITING[0] >= CODE_WAITING_MOST:
            log_sparing('code-send-full', 'codes to send: %d are waiting already - the code '
                        'for %s is not sent' % (CODE_WAITING[0], name), 'warn', every=60)
            return
        CODE_WAITING[0] += 1

    def go():
        try:
            with CODE_SENDING:
                send()
        finally:
            with CODE_LOCK:
                CODE_WAITING[0] -= 1

    def send():
        try:
            said = code_send(store, kind, to, code, name=name)
            store.otp_add({'ts': time.time(), 'name': name, 'ok': 1,
                           'said': 'A code was sent by %s to %s' % (
                               'mail' if kind == 'mail' else 'SMS', dest_masked(kind, to)),
                           'how': 'send-' + kind, 'src': '', 'rid': str(rid)[:120],
                           'step_off': None})
            if debugging('radius'):
                log('a code for %s went by %s: %s' % (name, kind, said), 'debug')
        except Exception as e:                          # noqa: BLE001
            log_sparing('code-send:%s' % kind, 'a code for %s could not be sent by %s: %s'
                        % (name, kind, e), 'warn', every=60)
            try:
                store.add_event('mail' if kind == 'mail' else 'radius',
                                'the code for %s could not be sent by %s to %s: %s'
                                % (name, 'mail' if kind == 'mail' else 'SMS',
                                   dest_masked(kind, to), str(e)[:300]), 'bad', who=name)
                store.otp_add({'ts': time.time(), 'name': name, 'ok': 0,
                               'said': 'The code could not be sent: %s' % str(e)[:200],
                               'how': 'send-' + kind, 'src': '', 'rid': str(rid)[:120],
                               'step_off': None})
            except Exception:                           # noqa: BLE001
                pass
    try:
        threading.Thread(target=go, name='code-send', daemon=True).start()
    except RuntimeError as e:
        with CODE_LOCK:
            CODE_WAITING[0] -= 1
        log_sparing('code-send-thread', 'the code for %s could not be sent: %s' % (name, e),
                    'warn', every=60)


# ---- the challenges ------------------------------------------------------------------
def chal_key(state):
    return 'chal:' + hashlib.sha256(bytes(state)).hexdigest()[:40]


def chal_new(store, data):
    """A challenge kept; returns the State the VPN sends back."""
    state = CHAL_PREFIX + secrets.token_bytes(24)
    data = dict(data, exp=time.time() + int(CONFIG.get('code_ttl_s') or 300), tries=0,
                made=time.time(), node=node_name())
    store.set_meta(chal_key(state), json.dumps(data))
    return state


def chal_get(store, state):
    k = chal_key(state)
    raw = store.get_meta(k)
    if not raw:
        return None, None
    try:
        got = json.loads(raw)
    except ValueError:
        return None, None
    return got, raw


def chal_put(store, state, raw_was, data):
    """Written only if nobody wrote it meanwhile; whether it was."""
    return bool(store.db.run('UPDATE meta SET v = ? WHERE k = ? AND v = ?',
                             (json.dumps(data), chal_key(state), raw_was)))


def chal_take(store, state, raw_was):
    """Used up: of two nodes taking the same answer at once, only one wins."""
    return bool(store.db.run('DELETE FROM meta WHERE k = ? AND v = ?', (chal_key(state), raw_was)))


def chal_drop(store, state):
    """Done with, whatever it holds now: after a code taken once - the token's
    step, a recovery code, once_take - another answer that only counted a try
    meanwhile no longer refuses the right one (1.0.139)."""
    store.db.run('DELETE FROM meta WHERE k = ?', (chal_key(state),))


def chal_tidy(store):
    """Challenges past their time, and the counts of sent codes."""
    t = time.time()
    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'chal:%' OR k LIKE 'codesent:%'"):
        try:
            v = json.loads(r['v'] or 'null')
        except ValueError:
            v = None
        if r['k'].startswith('chal:'):
            gone = not isinstance(v, dict) or float(v.get('exp') or 0) < t - 60
        else:
            span = 60 * int(CONFIG.get('code_send_window_min') or 15)
            gone = not isinstance(v, list) or not any(t - float(x) < span for x in v)
        if gone:
            store.db.run('DELETE FROM meta WHERE k = ? AND v = ?', (r['k'], r['v']))
