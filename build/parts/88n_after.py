# ---- after the update: what otp cannot do itself (1.0.258) -------------------------------
# A new version may need something only root can do - a step on the command line, what the
# installer had to leave (SELinux, the firewall, a package) - and until 1.0.258 it was said in
# a log line or an error once, when somebody happened to look. Nobody saw it, and the way out
# people found was to switch SELinux off. Now every such thing is an entry of AFTER below:
#
#   {'id', 'since' (the version that brought it), 'level' ('bad' | 'warn' | 'info'),
#    'title', 'why' (English; 'title_cs', 'why_cs' for the mails), 'steps' (each
#    {'where': 'root', 'lead', 'cmd'} or {'where': 'pages', 'pane', 'words'}), 'foot',
#    'check': fn(store, facts) -> 'needed' | 'done' | 'na' or ('needed', {'sig', 'args',
#    'level', 'grows'}), 'ack': 'auto' | 'manual'}
#
# A future version adds an entry and nothing else: each node looks at its own (at the start,
# every 10 min, and when "Look again" is pressed) and writes what it needs into its own row
# 'after:NODE' - one writer a row; Settings → Upgrades draws them, the menu counts them, the
# alerts mail them, otp --after, otp --status, the console and install.sh say them. One whose
# check finds it so goes by itself; a manual one waits for "Done" ('after:ack:ID:NODE', written
# by the pages of any node, as 'host:selinux:want:NODE' is), and an automatic one may be marked
# done by hand too - logged. The daemon reads only what root left readable for it (root-facts.json
# beside the program, written by install.sh; the files there; what the root helper said of
# SELinux) - never a secret; nothing here is on the way of RADIUS.
AFTER = []
AFTER_EVERY = float(os.environ.get('OTP_AFTER_EVERY') or 600)
AFTER_WORK = {'at': 0.0, 'busy': False, 'looked': 0.0, 'look_id': ''}
AFTER_LOCK = threading.Lock()
AFTER_LOG_KEEP = 20
AFTER_LEVELS = ('bad', 'warn', 'info')
AFTER_LIB = UPGRADE_HELPER.parent
# What install.sh found as root and the service cannot see itself (1.0.258): root's own file,
# world-readable, beside the program - which versions put the root parts in, whether nginx took
# the additions, whether SELinux took otp's module, whether a firewall was there to open.
ROOT_FACTS_FILE = Path(os.environ.get('OTP_ROOT_FACTS') or str(AFTER_LIB / 'root-facts.json'))
# Off unless the file is there (1.0.258): what the tests of the pages make needed on a live
# server, by root's hand - {"auto": "needed"|"done", "manual": "needed"|"done"}.
AFTER_TEST_FILE = Path(os.environ.get('OTP_AFTER_TEST') or str(STATE_DIR / 'after-test.json'))
AFTER_SUM_CACHE = {'at': 0.0, 'v': None}


def after_entry(**e):
    """One thing an update cannot do itself, put on the list (its check is asked on every node)."""
    for k in ('id', 'since', 'level', 'title', 'why', 'check', 'ack'):
        if k not in e:
            raise ValueError('an entry of AFTER without %s' % k)
    if e['level'] not in AFTER_LEVELS or e['ack'] not in ('auto', 'manual') or \
            not re.match(r'^[a-z0-9][a-z0-9-]{0,40}\Z', e['id']) or \
            any(x['id'] == e['id'] for x in AFTER):
        raise ValueError('an entry of AFTER is not right: %s' % e.get('id'))
    e.setdefault('steps', [])
    e.setdefault('foot', 'This band goes by itself once it is so.' if e['ack'] == 'auto'
                 else 'Once it is done, press Done.')
    e.setdefault('foot_cs', 'Tento pruh zmizí sám, jakmile to tak bude.' if e['ack'] == 'auto'
                 else 'Až to bude hotové, stiskněte Hotovo.')
    AFTER.append(e)
    return e


class _AfterArgs(dict):
    """The words an entry is written with: a name not given stays as it is."""
    def __missing__(self, k):
        return '{' + k + '}'


def _after_words(text, args):
    try:
        return str(text or '').format_map(args)
    except (ValueError, IndexError, AttributeError):
        return str(text or '')


def root_facts():
    """root-facts.json as root left it: {} when it is not a plain file of JSON, None when it is
    not there at all (installed by an install.sh before 1.0.258)."""
    import stat as _stat
    try:
        st = os.lstat(str(ROOT_FACTS_FILE))
    except OSError:
        return None
    if not _stat.S_ISREG(st.st_mode) or st.st_size > 65536:
        return {}
    try:
        return json_obj(ROOT_FACTS_FILE.read_text(encoding='utf-8', errors='replace')) or {}
    except OSError:
        return {}


def _after_sha(path):
    try:
        with open(str(path), 'rb') as f:
            return hashlib.sha256(f.read(4 * 1024 * 1024)).hexdigest()
    except OSError:
        return None


def after_test_facts():
    try:
        if not AFTER_TEST_FILE.is_file() or AFTER_TEST_FILE.stat().st_size > 4096:
            return {}
        return json_obj(AFTER_TEST_FILE.read_text()) or {}
    except OSError:
        return {}


def after_facts(store):
    """What this node knows of its root side, for the checks: files only - nothing is run but
    php_state (kept an hour), nothing asked of root."""
    me = node_name()
    f = {'node': me, 'version': __version__, 'cluster': bool(in_cluster(store)), 'root': root_facts()}
    # Put in by install.sh (1.0.258): beside its helpers, or with root's facts. A program run
    # from an unpacked folder (a test, a look at a package) has nothing of root to compare.
    f['installed'] = bool((AFTER_LIB / 'otp_web.py').exists() or UPGRADE_HELPER.exists() or
                          f['root'] is not None)
    se = _meta_json(store, 'host:selinux:now:' + me) or {}
    f['selinux'] = odict(se.get('data'))
    f['selinux_at'] = fnum(se.get('at'))
    f['cil'] = _after_sha(AFTER_LIB / 'otp_server.cil')
    f['cil_in'] = _after_sha(AFTER_LIB / 'otp_server.cil.in-policy')
    f['upgrade_helper'] = UPGRADE_HELPER.exists()
    f['upgrade_path'] = Path('/etc/systemd/system/otp-upgrade.path').exists()
    f['php'] = {}
    if f['installed']:
        try:
            f['php'] = dict(php_state() or {})
        except Exception:                               # noqa: BLE001
            f['php'] = {}
    f['test'] = after_test_facts()
    return f


def _after_lead(f, cs=False):
    if f.get('cluster'):
        return ('Jako root na %s:' % f['node']) if cs else ('As root, on %s:' % f['node'])
    return 'Jako root na serveru:' if cs else 'As root, on the server:'


# ---- the checks ----------------------------------------------------------------------------
def _ck_root_parts(store, f):
    """The program newer than what root put in beside it: install.sh of this version did not
    run to its end here (a package copied by hand, an install.sh --upgrade that stopped)."""
    if not f.get('installed'):
        return 'na'
    had = str(odict(f.get('root')).get('installer') or '')
    if re.match(r'^\d+\.\d+\.\d+\Z', had) and _ver_tuple(had) >= _ver_tuple(f['version']):
        return 'done'
    return ('needed', {'sig': had, 'args': {
        'had': ('install.sh %s' % had) if had else 'an install.sh older than 1.0.258',
        'had_cs': ('install.sh %s' % had) if had else 'install.sh starší než 1.0.258'}})


def _ck_upgrade_helper(store, f):
    if not f.get('installed') or (f.get('upgrade_helper') and f.get('upgrade_path')):
        return 'na' if not f.get('installed') else 'done'
    return ('needed', {'sig': ''})


def _ck_nginx(what):
    def check(store, f):
        rf = odict(f.get('root'))
        n = odict(rf.get('nginx'))
        if n.get(what) != 'failed':
            return 'done'
        return ('needed', {'sig': str(n.get('at') or rf.get('at') or ''),
                           'args': {'installer': str(rf.get('installer') or '?')}})
    return check


def _ck_se_module(store, f):
    """otp's module in the policy not the one beside this version (install.sh's semodule -i
    failed, or never ran while SELinux is on)."""
    d = odict(f.get('selinux'))
    mode = d.get('mode')
    if mode not in ('Enforcing', 'Permissive'):
        return 'na'
    off = d.get('module') is False
    old = bool(f.get('cil')) and f.get('cil_in') != f.get('cil')
    if not (off or old):
        return 'done'
    return ('needed', {'sig': str(f.get('cil') or '')[:16], 'level': 'bad' if mode == 'Enforcing' else 'warn',
                       'args': {'mode': mode.lower(), 'mode_cs': mode.lower(),
                                'how': 'is not in its policy' if off else 'in its policy is older than the one of this version',
                                'how_cs': 'v jeho politice není' if off else 'je v jeho politice starší než ten z této verze'}})


def _ck_se_refused(store, f):
    d = odict(f.get('selinux'))
    if d.get('mode') != 'Enforcing':
        return 'na'
    n = int(fnum(odict(d.get('denials')).get('total')))
    if n <= 0:
        return 'done'
    # Marked done by hand, it comes back only when more is refused (grows).
    return ('needed', {'sig': str(n), 'grows': True, 'args': {'n': n}})


def _ck_php(store, f):
    p = odict(f.get('php'))
    if not p.get('version'):
        return 'na'
    if p.get('fixed') is not False:
        return 'done'
    return ('needed', {'sig': str(p['version']), 'args': {'php': str(p['version'])}})


def _ck_firewall(store, f):
    rf = odict(f.get('root'))
    fw = odict(rf.get('firewall'))
    if fw.get('state') != 'none':
        return 'na'
    return ('needed', {'sig': str(fw.get('at') or ''), 'args': {'installer': str(rf.get('installer') or '?')}})


def _ck_test(which):
    def check(store, f):
        said = odict(f.get('test')).get(which)
        if said not in ('needed', 'done'):
            return 'na'
        return said if said == 'done' else ('needed', {'sig': 'test'})
    return check


# ---- the entries (1.0.258) -------------------------------------------------------------------
after_entry(
    id='root-parts', since='1.0.258', level='bad', ack='auto', check=_ck_root_parts,
    title='otp {version} is running, but the parts root installs are from before it',
    title_cs='Běží otp {version}, ale části, které instaluje root, jsou starší',
    why='The program is new, and what install.sh puts in beside it as root is from {had}: the root '
        'helper (certificates, the VIP address, the firewall, SELinux), the upgrade helper, the '
        'additions to nginx and SELinux\'s module. An upgrade from these pages does it all by '
        'itself; a package copied by hand, or an install.sh --upgrade that stopped half way, does '
        'not. Until it is done, what these pages ask of root may fail or be done as the older '
        'version did it.',
    why_cs='Program je nový a to, co vedle něj jako root instaluje install.sh, je z {had}: pomocník '
           'roota (certifikáty, VIP adresa, firewall, SELinux), pomocník upgradu, doplňky nginx a '
           'modul SELinuxu. Upgrade z těchto stránek to udělá sám; balíček zkopírovaný ručně nebo '
           'install.sh --upgrade zastavený v půli ne. Dokud se to neudělá, může to, co tyto stránky '
           'po rootovi chtějí, selhat nebo proběhnout jako ve starší verzi.',
    steps=[{'where': 'root', 'lead': 'As root, in the folder the otp-{version} package was unpacked in{on}:',
            'cmd': './install.sh --upgrade'}],
    foot='This band goes by itself once install.sh of {version} has run to its end here.')

after_entry(
    id='upgrade-helper', since='1.0.258', level='warn', ack='auto', check=_ck_upgrade_helper,
    title='A new version cannot be put in from these pages on this node',
    title_cs='Na tomto uzlu nelze novou verzi nainstalovat z těchto stránek',
    why='otp_upgrade.py or otp-upgrade.path, which root uses to put in a package sent here, is not '
        'installed. Upgrades from the pages wait on this node until install.sh --upgrade has put '
        'them in once.',
    why_cs='Není nainstalovaný otp_upgrade.py nebo otp-upgrade.path, kterými root instaluje sem '
           'poslaný balíček. Upgrady ze stránek na tomto uzlu čekají, dokud je install.sh --upgrade '
           'jednou nenainstaluje.',
    steps=[{'where': 'root', 'lead': 'As root, in the folder the otp-{version} package was unpacked in{on}:',
            'cmd': './install.sh --upgrade'}])

after_entry(
    id='nginx-additions', since='1.0.258', level='warn', ack='auto', check=_ck_nginx('additions'),
    title='nginx did not take the additions of the last upgrade',
    title_cs='nginx nepřijal doplňky posledního upgradu',
    why='install.sh {installer} put what this version needs into /etc/nginx/conf.d/otp.conf, nginx -t '
        'refused the file, and it was put back as it was - so what came with the additions is '
        'missing (the icon of a home-screen shortcut, GET /healthz and /metrics, the limits of '
        'the sign-in). The pages work as before. Usually a change of your own in the file is what '
        'nginx refuses; the copy from before the upgrade is in /etc/nginx/otp-backups.',
    why_cs='install.sh {installer} doplnil do /etc/nginx/conf.d/otp.conf, co tato verze potřebuje, '
           'nginx -t soubor odmítl a ten se vrátil, jak byl – chybí tedy, co s doplňky přišlo (ikona '
           'zástupce na ploše, GET /healthz a /metrics, limity přihlášení). Stránky fungují jako '
           'dřív. Obvykle nginx odmítá vlastní změnu v souboru; kopie z doby před upgradem je '
           'v /etc/nginx/otp-backups.',
    steps=[{'where': 'root', 'lead': 'As root{on}: what nginx says of the file now',
            'cmd': 'nginx -t'},
           {'where': 'root', 'lead': 'Then, once what it refused is put right, in the folder of the package:',
            'cmd': './install.sh --upgrade'}],
    foot='This band goes by itself once an install.sh --upgrade gets the additions in.')

after_entry(
    id='nginx-upload-guard', since='1.0.258', level='warn', ack='auto', check=_ck_nginx('guard'),
    title='nginx did not take the guard for big uploads',
    title_cs='nginx nepřijal ochranu velkých nahrávání',
    why='install.sh {installer} put in the question nginx asks before it takes a database or a new '
        'version sent from these pages (auth_request), nginx -t refused it, and the file was put '
        'back as it was: such a body is taken before the pages can say whether a full '
        'administrator sends it.',
    why_cs='install.sh {installer} vložil otázku, kterou nginx klade, než převezme databázi nebo '
           'novou verzi poslanou z těchto stránek (auth_request), nginx -t ji odmítl a soubor se '
           'vrátil, jak byl: takové tělo se převezme dřív, než stránky řeknou, zda ho posílá plný '
           'správce.',
    steps=[{'where': 'root', 'lead': 'As root{on}: what nginx says of the file now',
            'cmd': 'nginx -t'},
           {'where': 'root', 'lead': 'Then, once what it refused is put right, in the folder of the package:',
            'cmd': './install.sh --upgrade'}],
    foot='This band goes by itself once an install.sh --upgrade gets the guard in.')

after_entry(
    id='selinux-module', since='1.0.258', level='warn', ack='auto', check=_ck_se_module,
    title='SELinux: otp\'s module is not the one this version needs',
    title_cs='SELinux: modul otp není ten, který tato verze potřebuje',
    why='SELinux is {mode} on this node, and otp\'s module (otp_server) {how}: the labels it gives '
        'otp\'s files are missing, and the pages may not read what they need. Do not switch '
        'SELinux off for it - put the module in, as install.sh does.',
    why_cs='SELinux je na tomto uzlu v režimu {mode} a modul otp (otp_server) {how}: chybí '
           'štítky, které dává souborům otp, a stránky nemusí přečíst, co potřebují. Nevypínejte kvůli '
           'tomu SELinux – vložte modul, jak to dělá install.sh.',
    steps=[{'where': 'root', 'lead': '{lead}',
            'cmd': 'semodule -i {lib}/otp_server.cil && install -m 0644 {lib}/otp_server.cil '
                   '{lib}/otp_server.cil.in-policy'},
           {'where': 'root', 'lead': 'Then see that nothing else is missing:', 'cmd': 'otp --selinux-check'},
           {'where': 'pages', 'pane': 'hisec',
            'words': 'Or on Settings → High security → SELinux: Put in what otp needs (while permissive).'}],
    foot='This band goes by itself once the module is in (SELinux of the node is looked at every '
         'half hour; Look again asks sooner).')

after_entry(
    id='selinux-refused', since='1.0.258', level='bad', ack='auto', check=_ck_se_refused,
    title='SELinux refuses otp something on this node',
    title_cs='SELinux na tomto uzlu něco otp odmítá',
    why='SELinux is enforcing and refused {n} thing(s) to otp or to the programs it works with (since '
        'otp\'s needs were last put in, or since the machine started): what was refused does not '
        'work - the pages, the root helper, SSH with a code. Do not switch SELinux off for it: see '
        'what it is, put in what otp needs, or send the report to whoever looks after otp\'s module.',
    why_cs='SELinux vynucuje a odmítl {n} věc(í) otp nebo programům, se kterými pracuje (od '
           'posledního vložení toho, co otp potřebuje, nebo od startu stroje): co bylo odmítnuto, '
           'nefunguje – stránky, pomocník roota, SSH s kódem. Nevypínejte kvůli tomu SELinux: podívejte '
           'se, co to je, vložte, co otp potřebuje, nebo pošlete zprávu tomu, kdo se stará o modul otp.',
    steps=[{'where': 'root', 'lead': '{lead_what}', 'cmd': 'otp --selinux-check'},
           {'where': 'root', 'lead': 'The report, for whoever looks after otp\'s module:',
            'cmd': 'otp --selinux-report'},
           {'where': 'pages', 'pane': 'hisec',
            'words': 'Settings → High security → SELinux says the same, with what otp needs.'}],
    foot='This band goes by itself once nothing is refused any more (put right, or after the next '
         'start of the machine). Done takes it away until something more is refused.')

after_entry(
    id='php2shell', since='1.0.258', level='bad', ack='auto', check=_ck_php,
    title='PHP {php} here does not have the php2shell fix',
    title_cs='PHP {php} zde nemá opravu php2shell',
    why='CVE-2026-109618 and CVE-2026-109619: remote code execution by anybody who can reach the web '
        'server. Update PHP to the fixed release of your distribution and restart php-fpm - '
        'install.sh --upgrade does both.',
    why_cs='CVE-2026-109618 a CVE-2026-109619: vzdálené spuštění kódu kýmkoli, kdo se dostane na '
           'webový server. Aktualizujte PHP na opravené vydání vaší distribuce a restartujte php-fpm '
           '– install.sh --upgrade udělá obojí.',
    steps=[{'where': 'root', 'lead': '{lead}', 'cmd': 'dnf upgrade \'php*\' && systemctl restart php-fpm'},
           {'where': 'root', 'lead': 'Or, in the folder of the package:', 'cmd': './install.sh --upgrade'}],
    foot='This band goes by itself within the hour once PHP is fixed.')

after_entry(
    id='firewall-by-hand', since='1.0.258', level='info', ack='manual', check=_ck_firewall,
    title='Nothing opened the firewall for otp on this node',
    title_cs='Na tomto uzlu firewall pro otp nic neotevřelo',
    why='firewalld was not running when install.sh {installer} ran, so it opened nothing and narrowed '
        'nothing. Whatever filters this machine must let through TCP 443 (and 80) to the pages and '
        'UDP 1812 and 1813 from the VPN concentrators - or let otp look after the machine\'s '
        'firewall on Settings → Firewall and access.',
    why_cs='Když běžel install.sh {installer}, firewalld neběžel, takže nic neotevřel ani nezúžil. '
           'Cokoli tento stroj filtruje, musí propustit TCP 443 (a 80) ke stránkám a UDP 1812 a 1813 '
           'od VPN koncentrátorů – nebo nechte firewall stroje spravovat otp v Nastavení → Firewall '
           'a přístup.',
    steps=[{'where': 'root', 'lead': 'As root{on}, with firewalld:',
            'cmd': 'firewall-cmd --permanent --add-service=https --add-service=http '
                   '--add-port=1812/udp --add-port=1813/udp && firewall-cmd --reload'},
           {'where': 'pages', 'pane': 'fw', 'words': 'Or on Settings → Firewall and access.'}])

# Only while root's test file is there (1.0.258): the tests of the pages on a live server.
after_entry(
    id='test-auto', since='1.0.258', level='warn', ack='auto', check=_ck_test('auto'),
    title='A test: something that goes by itself', title_cs='Zkouška: něco, co zmizí samo',
    why='Made by the tests of the pages ({file}). It goes when the file says "done".',
    why_cs='Udělaly to testy stránek ({file}). Zmizí, až soubor řekne „done“.',
    steps=[{'where': 'root', 'lead': '{lead}', 'cmd': 'rm {file}'}])
after_entry(
    id='test-manual', since='1.0.258', level='bad', ack='manual', check=_ck_test('manual'),
    title='A test: something done by hand', title_cs='Zkouška: něco, co se dělá ručně',
    why='Made by the tests of the pages ({file}). Press Done.',
    why_cs='Udělaly to testy stránek ({file}). Stiskněte Hotovo.',
    steps=[{'where': 'root', 'lead': '{lead}', 'cmd': 'echo done'}])


# ---- each node looks at its own -------------------------------------------------------------
def after_item(e, f, det):
    """What a node says of one thing it needs: the words already filled in, for any node's pages
    (a newer node's entries too) and for the mails."""
    det = odict(det)
    on = (', on %s' % f['node']) if f.get('cluster') else ''
    base = {'version': f.get('version') or __version__, 'node': f.get('node') or node_name(),
            'on': on, 'lib': str(AFTER_LIB), 'file': str(AFTER_TEST_FILE), 'lead': _after_lead(f),
            'lead_what': ('As root, on %s - what is refused, and what otp needs:' % f['node'])
            if f.get('cluster') else 'As root, on the server - what is refused, and what otp needs:'}
    args = odict(det.get('args'))
    plain = {k: v for k, v in args.items() if not k.endswith('_cs')}
    en = _AfterArgs(base, **plain)
    cs = _AfterArgs(base, **plain)
    cs.update(lead=_after_lead(f, True), on=(', na %s' % f['node']) if f.get('cluster') else '')
    cs.update({k[:-3]: v for k, v in args.items() if k.endswith('_cs')})
    steps = []
    for st in e.get('steps') or []:
        one = {'where': st.get('where') or 'root'}
        if st.get('cmd'):
            one['cmd'] = _after_words(st['cmd'], en)
            one['lead'] = _after_words(st.get('lead') or '{lead}', en)
        if st.get('pane'):
            one['pane'] = st['pane']
            one['words'] = _after_words(st.get('words') or '', en)
        steps.append(one)
    level = det.get('level') if det.get('level') in AFTER_LEVELS else e['level']
    return {'id': e['id'], 'since_version': e['since'], 'level': level, 'ack': e['ack'],
            'title': _after_words(e['title'], en)[:300], 'why': _after_words(e['why'], en)[:1500],
            'steps': steps, 'foot': _after_words(e.get('foot'), en)[:400],
            'cs': {'title': _after_words(e.get('title_cs') or e['title'], cs)[:300],
                   'why': _after_words(e.get('why_cs') or e['why'], cs)[:1500]},
            'sig': str(det.get('sig') or '')[:80], 'grows': bool(det.get('grows'))}


def after_acks(store):
    """Every 'Done' pressed: {(id, node): {by, at, sig, title}}."""
    out = {}
    try:
        rows = store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'after:ack:%'")
    except Exception:                                   # noqa: BLE001
        rows = []
    for r in rows:
        bits = str(r['k']).split(':', 3)
        got = json_obj(r['v'])
        if len(bits) == 4 and got is not None:
            out[(bits[2], bits[3])] = got
    return out


def after_acked(ack, it):
    """Whether a 'Done' pressed still holds for what the node says now: for the same thing (its
    sig - more refused is not the same), and for an automatic one not before it came back."""
    if not ack:
        return False
    if str(ack.get('sig') or '') != str(it.get('sig') or ''):
        if not (it.get('grows') and fnum(it.get('sig')) <= fnum(ack.get('sig'))):
            return False
    if it.get('ack') == 'auto' and fnum(ack.get('at')) + 1 < fnum(it.get('since')):
        return False
    return True


def after_evaluate(store, facts=None):
    """This node's turn: every entry's check, written into its own row 'after:NODE' (one writer a
    row), with what went by itself and what came back after a Done."""
    with AFTER_LOCK:
        me = node_name()
        key = 'after:' + me
        was = _meta_json(store, key) or {}
        old = odict(was.get('items'))
        log = [x for x in (was.get('log') or []) if isinstance(x, dict)][:AFTER_LOG_KEEP]
        f = facts if facts is not None else after_facts(store)
        acks = after_acks(store)
        now = time.time()
        items = {}
        for e in AFTER:
            p = odict(old.get(e['id']))
            try:
                got = e['check'](store, f)
                state, det = got if isinstance(got, tuple) else (got, {})
            except Exception as ex:                     # noqa: BLE001
                # One check that breaks keeps what it said before; the others go on.
                log_sparing('after-' + e['id'], 'after the update, %s: %s' % (e['id'], ex), 'warn', every=3600)
                if p:
                    items[e['id']] = p
                continue
            if state != 'needed':
                if p.get('state') == 'needed':
                    log.insert(0, {'id': e['id'], 'title': p.get('title') or e['id'], 'how': 'by itself',
                                   'at': now})
                continue
            it = after_item(e, f, det)
            it['since'] = fnum(p.get('since')) or now
            it['state'] = 'acked' if after_acked(acks.get((e['id'], me)), it) else 'needed'
            if p.get('state') == 'acked' and it['state'] == 'needed':
                log.insert(0, {'id': e['id'], 'title': it['title'], 'how': 'taken back', 'at': now})
            items[e['id']] = it
        row = {'at': now, 'node': me, 'version': __version__, 'items': items,
               'log': log[:AFTER_LOG_KEEP]}
        store.set_meta(key, json.dumps(row))
        AFTER_SUM_CACHE['at'] = 0.0
        return row


def after_tick(daemon):
    """At the start, every 10 min, and soon after "Look again" was asked of this node from
    another's pages - in a thread of its own, never in the way of anything."""
    now = time.time()
    if AFTER_WORK['busy']:
        return
    due = not AFTER_WORK['at'] or now - AFTER_WORK['at'] >= AFTER_EVERY
    if not due and now - AFTER_WORK['looked'] >= 15:
        AFTER_WORK['looked'] = now
        look = _meta_json(daemon.store, 'after:look:' + node_name()) or {}
        if look.get('id') and look.get('id') != AFTER_WORK['look_id']:
            AFTER_WORK['look_id'] = str(look.get('id'))
            due = True
    if not due:
        return
    AFTER_WORK.update(at=now, busy=True)

    def go():
        try:
            after_evaluate(daemon.store)
        except Exception as e:                          # noqa: BLE001
            log_sparing('after', 'after the update: %s' % e, 'warn', every=900)
        finally:
            AFTER_WORK['busy'] = False
    threading.Thread(target=go, name='otp-after', daemon=True).start()


def after_nodes(store):
    me = node_name()
    try:
        return [me] + [n['name'] for n in ha_nodes(store) if n['name'] != me]
    except Exception:                                   # noqa: BLE001
        return [me]


def after_rows(store):
    """{node: its row} of the nodes of the cluster."""
    out = {}
    for n in after_nodes(store):
        row = _meta_json(store, 'after:' + n)
        if row:
            out[n] = row
    return out


def after_needed(store, names=None):
    """What is to be done by hand now, on every node: the items no Done holds for."""
    acks = after_acks(store)
    rows = after_rows(store)
    out = []
    for n in (names or after_nodes(store)):
        for i, it in odict(odict(rows.get(n)).get('items')).items():
            if not isinstance(it, dict) or it.get('level') not in AFTER_LEVELS:
                continue
            if after_acked(acks.get((str(it.get('id') or i), n)), it):
                continue
            out.append(dict(it, id=str(it.get('id') or i), node=n,
                            checked=fnum(odict(rows.get(n)).get('at'))))
    out.sort(key=lambda x: (AFTER_LEVELS.index(x['level']), x['node'], -fnum(x.get('since'))))
    return out


def after_summary(store, fresh=False):
    """The count beside Upgrades in the menu, on the Settings tab, in otp --status and the console:
    {n, level, items: [{id, node, level, title}]} - read at most every 10 s."""
    now = time.time()
    if not fresh and AFTER_SUM_CACHE['v'] is not None and now - AFTER_SUM_CACHE['at'] < 10:
        return AFTER_SUM_CACHE['v']
    try:
        items = after_needed(store)
    except Exception:                                   # noqa: BLE001
        items = []
    v = {'n': len(items), 'level': items[0]['level'] if items else '',
         'items': [{k: x.get(k) for k in ('id', 'node', 'level', 'title')} for x in items[:20]]}
    AFTER_SUM_CACHE.update(at=now, v=v)
    return v


def after_view(store, full=True):
    """Settings → Upgrades → To be done by hand: every node's, with what was done lately."""
    items = after_needed(store)
    worst = items[0]['level'] if items else ''
    if not full:
        return {'count': len(items), 'level': worst,
                'nodes': sorted({x['node'] for x in items})}
    rows = after_rows(store)
    lately = []
    for n, row in rows.items():
        for x in row.get('log') or []:
            if isinstance(x, dict):
                lately.append({'id': x.get('id'), 'node': n, 'title': x.get('title') or x.get('id'),
                               'how': x.get('how') or 'by itself', 'who': '', 'at': fnum(x.get('at'))})
    nodes = set(after_nodes(store))
    for (i, n), a in after_acks(store).items():
        if n in nodes:
            lately.append({'id': i, 'node': n, 'title': a.get('title') or i, 'how': 'done',
                           'who': 'the command line' if a.get('via') == 'cli' else str(a.get('by') or ''),
                           'at': fnum(a.get('at'))})
    lately.sort(key=lambda x: -x['at'])
    return {'items': [{k: x.get(k) for k in ('id', 'node', 'level', 'ack', 'title', 'why', 'steps',
                                             'foot', 'since', 'checked', 'since_version', 'state')}
                      for x in items],
            'count': len(items), 'level': worst, 'lately': lately[:AFTER_LOG_KEEP],
            'nodes': [{'name': n, 'checked': fnum(odict(rows.get(n)).get('at')),
                       'version': odict(rows.get(n)).get('version') or ''} for n in after_nodes(store)],
            'me': node_name(), 'cluster': bool(in_cluster(store))}


def after_look(store, node, by):
    """"Look again": this node now; another node at its next tick (within a quarter of a minute)."""
    me = node_name()
    if node in ('', None, me):
        after_evaluate(store)
        # SELinux looked at again too, where it is what is needed: its answer comes in a minute.
        try:
            if any(x['node'] == me and x['id'].startswith('selinux-') for x in after_needed(store)):
                selinux_ask(store, me, 'check', by)
        except Exception:                               # noqa: BLE001
            pass
        return 'looked again'
    if node not in after_nodes(store):
        raise ValueError('there is no node %s' % node)
    store.set_meta('after:look:' + node, json.dumps({'id': secrets.token_hex(6), 'by': by,
                                                     'at': time.time()}))
    return '%s looks again within a minute' % node


def after_done(store, ident, node, by, via='pages'):
    """"Done": a manual one, or an automatic one marked by hand (logged as such)."""
    node = node or node_name()
    if node not in after_nodes(store):
        raise ValueError('there is no node %s' % node)
    row = _meta_json(store, 'after:' + node) or {}
    it = odict(odict(row.get('items')).get(ident))
    if not it:
        raise ValueError('%s has nothing called %s to be done' % (node, ident))
    store.set_meta('after:ack:%s:%s' % (ident, node), json.dumps({
        'by': by, 'at': time.time(), 'sig': it.get('sig') or '', 'title': it.get('title') or ident,
        'auto': it.get('ack') == 'auto', 'via': via}))
    AFTER_SUM_CACHE['at'] = 0.0
    store.add_event('settings', '%s marked as done on %s: %s%s' % (
        by, node, it.get('title') or ident, ' - although its check still finds it needed'
        if it.get('ack') == 'auto' else ''), 'warn' if it.get('ack') == 'auto' else 'info', who=by)
    return 'marked as done'


# ---- otp --after, otp --after-done (1.0.258) -----------------------------------------------
def cli_after(args, pal, store):
    by = cli_who()
    if args.after_done:
        try:
            print(pal.ok_line(after_done(store, args.after_done, args.node or node_name(), by, 'cli')))
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        return 0
    # This node looked at now: install.sh says them at its end, just after it wrote root's facts.
    try:
        after_evaluate(store)
    except Exception as e:                              # noqa: BLE001
        print(pal.warn_line('this node could not look now: %s' % e))
    v = after_view(store)
    if args.json:
        print(json.dumps(v, indent=2, default=str, ensure_ascii=False))
        return 0
    items = v['items']
    if not items:
        print(pal.ok_line('nothing is to be done by hand'))
    else:
        print(pal.head('to be done by hand: %d' % len(items)))
    for it in items:
        mark = pal.bad_line if it['level'] == 'bad' else pal.warn_line
        print(mark('%s%s' % (it['title'], ('  [%s]' % it['node']) if v['cluster'] else '')))
        print(pal.dim('    ' + it['why']))
        for st in it.get('steps') or []:
            if st.get('cmd'):
                print('    ' + st.get('lead', ''))
                print('      ' + pal.bold(st['cmd']))
            elif st.get('words'):
                print('    ' + st['words'])
        print(pal.dim('    %s  (%s; otp --after-done %s%s)' % (
            it.get('foot') or '', 'first seen %s' % stamp(it['since']) if it.get('since') else 'just seen',
            it['id'], (' --node %s' % it['node']) if it['node'] != node_name() else '')))
    if v['lately'] and not getattr(args, 'after_brief', False):
        print(pal.head('done lately'))
        for x in v['lately'][:10]:
            print('  %s  %-10s %-14s %s%s' % (stamp(x['at']), x['how'], x['who'] or '-', x['title'],
                                             ('  [%s]' % x['node']) if v['cluster'] else ''))
    return 0
