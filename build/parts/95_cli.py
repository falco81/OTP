

# ---------------------------------------------------------------------------
# The command line
# ---------------------------------------------------------------------------
# Everything the pages can do, and the accounts and passwords besides - which
# are handled by talking to the database directly, never through the API,
# because the moment the command line is most needed is the moment nobody
# can sign in. In colour on a terminal and plain anywhere else, `[ ok ]` and
# `[fail]` standing in for the colours, exactly as isemon does it.

# ---------------------------------------------------------------------------
# Colour - as isemon does it
# ---------------------------------------------------------------------------
# colorama when it is installed, and the same escape sequences written by hand
# when it is not. A nicety, never a dependency: a server being put right at two
# in the morning is not the one to find that the token server will not start
# because a colour library is missing. colorama adds a Windows console, a
# terminal reset however the program ends, and nothing else on Linux.
try:
    import colorama
    from colorama import Fore as _Fore, Style as _Style
    HAVE_COLORAMA = True
except Exception:                       # not installed, or installed broken
    colorama = None
    HAVE_COLORAMA = False

    class _Fore(object):
        RED = '\033[31m'; GREEN = '\033[32m'; YELLOW = '\033[33m'
        BLUE = '\033[34m'; MAGENTA = '\033[35m'; CYAN = '\033[36m'
        WHITE = '\033[37m'; RESET = '\033[39m'

    class _Style(object):
        BRIGHT = '\033[1m'; DIM = '\033[2m'; NORMAL = '\033[22m'
        RESET_ALL = '\033[0m'

_COLORAMA_READY = False


def write_private(path, text):
    """A file only root reads, so from its first byte (1.0.94)."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(text)


def start_colour():
    global _COLORAMA_READY
    if _COLORAMA_READY or not HAVE_COLORAMA:
        return
    _COLORAMA_READY = True
    try:
        if hasattr(colorama, 'just_fix_windows_console'):
            colorama.just_fix_windows_console()
        else:
            colorama.init()
    except Exception:
        pass


ANSI = re.compile(r'\033\[[0-9;]*m')
TERM_CTL = re.compile(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]')


def term_safe(text):
    """What came from outside, safe on a terminal (1.0.139): a User-Name or a
    reason from a packet carried escapes that cleared the screen, set the
    title or wrote the clipboard. Colours are kept; any other control
    character is shown as \\xNN."""
    t = str(text)
    out, at = [], 0
    for m in ANSI.finditer(t):
        out.append(TERM_CTL.sub(lambda c: '\\x%02x' % ord(c.group(0)), t[at:m.start()]))
        out.append(m.group(0))
        at = m.end()
    out.append(TERM_CTL.sub(lambda c: '\\x%02x' % ord(c.group(0)), t[at:]))
    return ''.join(out)


def plain_len(text):
    """How wide something looks, the colour taken out."""
    return len(ANSI.sub('', str(text)))


def plain_pad(text, width):
    return str(text) + ' ' * max(0, width - plain_len(text))


class Palette(object):
    """Every colour the command line uses, in one place."""

    def __init__(self, on):
        self.on = bool(on)
        if self.on:
            start_colour()

        def code(*parts):
            return ''.join(parts) if self.on else ''

        self.c_ok = code(_Fore.GREEN)
        self.c_warn = code(_Fore.YELLOW)
        self.c_bad = code(_Style.BRIGHT, _Fore.RED)
        self.c_info = code(_Fore.CYAN)
        self.c_head = code(_Style.BRIGHT, _Fore.CYAN)
        self.c_key = code(_Fore.WHITE)
        self.c_addr = code(_Fore.MAGENTA)
        self.c_hi = code(_Style.BRIGHT)
        self.c_dim = code(_Style.DIM)
        self.off = code(_Style.RESET_ALL)
        try:
            self.width = max(60, min(120, shutil.get_terminal_size((100, 24)).columns))
        except Exception:
            self.width = 100

    def paint(self, text, colour):
        if not self.on or not colour:
            return str(text)
        return '%s%s%s' % (colour, text, self.off)

    def good(self, t):
        return self.paint(t, self.c_ok)

    def bad(self, t):
        return self.paint(t, self.c_bad)

    def warn(self, t):
        return self.paint(t, self.c_warn)

    def info(self, t):
        return self.paint(t, self.c_info)

    def dim(self, t):
        return self.paint(t, self.c_dim)

    soft = dim

    def head(self, t):
        return self.paint(t, self.c_head)

    def bold(self, t):
        return self.paint(t, self.c_hi)

    hi = bold

    def addr(self, t):
        return self.paint(t, self.c_addr)

    def ok_line(self, t):
        return (self.good('✔ ') if self.on else '[ ok ] ') + str(t)

    def warn_line(self, t):
        return (self.warn('! ') if self.on else '[warn] ') + str(t)

    def bad_line(self, t):
        return (self.bad('✘ ') if self.on else '[fail] ') + str(t)


def colour_wanted(no_color=False, stream=None):
    """What the person asked for, then NO_COLOR, then FORCE_COLOR, then the
    terminal itself - in that order, as isemon decides it."""
    if no_color or os.environ.get('NO_COLOR') is not None:
        return False
    if os.environ.get('FORCE_COLOR') or os.environ.get('CLICOLOR_FORCE'):
        return True
    if str(os.environ.get('TERM') or '').lower() in ('dumb', '') \
            and not os.environ.get('TERM_PROGRAM'):
        return False
    try:
        return bool((stream or sys.stdout).isatty())
    except Exception:
        return False


# ---- colour in every output (1.0.132) ---------------------------------------------
# With colour on, every table and every line the command line prints is
# coloured the same way - tables by their cells, other lines as they read:
# "key: value", addresses, times, and the words that say how a thing is.
# Whatever already carries its own colour is left as it is.
TABLE_PAL = None
TONE_GOOD = {'on', 'yes', 'active', 'ok', 'accept', 'accepted', 'running', 'answering',
             'in place', 'in service', 'done', 'synchronised', 'healthy', 'up', 'enabled',
             'signed in', 'good', 'valid', 'sent', 'taken', 'checked'}
TONE_BAD = {'off', 'no', 'reject', 'rejected', 'failed', 'fail', 'error', 'gone', 'down',
            'locked', 'locked out', 'expired', 'not answering', 'inactive', 'dead', 'disabled',
            'refused', 'missing', 'broken', 'lost', 'crit'}
TONE_WARN = {'pending', 'waiting', 'maintenance', 'in maintenance', 'paused', 'warn',
             'warning', 'not set up', 'unknown', 'stale', 'not yet'}
TONE_DIM = {'never', '-', '–', '(none)', 'none', 'as they come', 'not set', ''}
RE_ADDR = re.compile(r'(?<![\w.:])(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?(?::\d{1,5})?)(?![\w.])')
RE_TIME = re.compile(r'\b(\d{2}-\d{2}-\d{4}|\d{4}-\d{2}-\d{2})([ T]\d{2}:\d{2}(?::\d{2})?)?\b')


def tone_cell(text, pal):
    """One value coloured by what it says."""
    t = str(text)
    if not pal or not pal.on or ANSI.search(t):
        return t
    low = t.strip().lower()
    if low in TONE_GOOD:
        return pal.good(t)
    if low in TONE_BAD:
        return pal.bad(t)
    if low in TONE_WARN:
        return pal.warn(t)
    if low in TONE_DIM:
        return pal.dim(t)
    if RE_TIME.fullmatch(t.strip()):
        return pal.dim(t)
    return tone_words(t, pal)


def tone_words(t, pal):
    """Addresses and times inside a text."""
    t = RE_ADDR.sub(lambda m: pal.addr(m.group(1)), t)
    return RE_TIME.sub(lambda m: pal.dim(m.group(0)), t)


def _cut(text, width):
    """`text` no wider than `width` on the screen, its colour kept or - when it
    has to be cut - taken off."""
    if plain_len(text) <= width:
        return text
    return ANSI.sub('', text)[:width]


def table(rows, heads, widths=None):
    if not rows:
        return '  (none)'
    pal = TABLE_PAL
    cells = [[tone_cell(term_safe(c), pal) for c in r] for r in rows]
    cols = list(zip(*([heads] + [[str(c) for c in r] for r in cells])))
    w = widths or [min(48, max(plain_len(x) for x in col)) for col in cols]
    head = '  ' + '  '.join(h.upper().ljust(w[i]) for i, h in enumerate(heads))
    out = [pal.head(head) if pal and pal.on else head]
    for r in cells:
        out.append('  ' + '  '.join(plain_pad(_cut(str(c), w[i]), w[i])
                                    for i, c in enumerate(r)))
    return '\n'.join(out)


class ColourOut(object):
    """stdout, every line coloured on its way out unless it is already."""
    LINE_KV = re.compile(r'^(\s*)([A-Za-z][\w .()/\'-]{0,40}?)(:\s+|\s{2,})(\S.*)$')

    def __init__(self, stream, pal):
        self.s, self.pal, self.buf = stream, pal, ''

    def _line(self, ln):
        p = self.pal
        ln = term_safe(ln)
        if not p.on or not ln.strip() or ANSI.search(ln):
            return ln
        m = self.LINE_KV.match(ln)
        if m and not ln.lstrip().startswith(('$', '#')):
            return '%s%s%s%s' % (m.group(1), p.info(m.group(2)), m.group(3),
                                 tone_cell(m.group(4), p))
        return tone_words(ln, p)

    def write(self, text):
        self.buf += str(text)
        if '\n' in self.buf:
            done, self.buf = self.buf.rsplit('\n', 1)
            self.s.write('\n'.join(self._line(x) for x in done.split('\n')) + '\n')
        return len(text)

    def flush(self):
        if self.buf:
            self.s.write(self.buf)
            self.buf = ''
        self.s.flush()

    def __getattr__(self, name):
        return getattr(self.s, name)


def ask_password(prompt='password', twice=True, env='OTP_PASSWORD'):
    # Each secret its own variable (1.0.139): OTP_PASSWORD, set for an
    # account, became a client's shared secret.
    said = os.environ.get(env) if env else None
    if said:
        return said
    first = getpass.getpass('%s: ' % prompt)
    if twice:
        again = getpass.getpass('and again: ')
        if first != again:
            raise SystemExit('those two are not the same')
    return first


class HelpfulParser(argparse.ArgumentParser):
    """An ArgumentParser whose help is isemon's: two columns, in colour.
    Anything going wrong in the drawing falls back to argparse's own."""
    palette = None

    def format_help(self):
        try:
            return help_text(self, self.palette or Palette(False))
        except Exception:
            return super(HelpfulParser, self).format_help()

    def error(self, message):
        pal = self.palette or Palette(False)
        sys.stderr.write('%s\n' % pal.bad_line(message))
        sys.stderr.write(pal.dim('try:  otp --help') + '\n')
        raise SystemExit(2)


def help_option_words(action):
    names = ', '.join(action.option_strings)
    if action.nargs == 0:
        return names, ''
    if action.metavar:
        meta = ' '.join(action.metavar) if isinstance(action.metavar, tuple) else action.metavar
    elif action.choices:
        meta = '{%s}' % ','.join(str(c) for c in action.choices)
    else:
        meta = action.dest.upper()
    if action.nargs in ('+', '*'):
        meta += ' ...'
    return names, meta


def help_text(parser, pal):
    """The whole of --help, in the width of this terminal."""
    import textwrap
    width = pal.width
    out = ['%s %s' % (pal.head('otp'), pal.bold(__version__)),
           pal.dim('a one-time password server: RADIUS, TOTP, the enrolment of tokens and '
                   'Active Directory, in one Python file'),
           '',
           '%s otp %s' % (pal.paint('usage:', pal.c_key), pal.dim('[--json] [--no-color] '
                                                                  '[what to do]')),
           pal.dim('       otp is the same command; with nothing at all it says what it is doing')]
    every = [a for g in parser._action_groups for a in g._group_actions]
    left = min(34, max([len(' '.join(x for x in help_option_words(a) if x))
                        for a in every] or [20]) + 2)
    for group in parser._action_groups:
        actions = [a for a in group._group_actions if a.help != argparse.SUPPRESS]
        if not actions:
            continue
        out.append('')
        out.append(pal.head((group.title or '').upper()))
        if group.description:
            for line in textwrap.wrap(group.description, width - 2):
                out.append('  ' + pal.dim(line))
        for action in actions:
            names, meta = help_option_words(action)
            painted = pal.good(names) + (' ' + pal.warn(meta) if meta else '')
            says = action.help or ''
            if (action.default not in (None, False, '', argparse.SUPPRESS)
                    and action.nargs != 0 and action.default != []
                    and '[%s]' % action.default not in says):
                says += ' [%s]' % action.default
            lines = textwrap.wrap(says, max(24, width - left - 4)) or ['']
            if plain_len(painted) > left:
                out.append('  ' + painted)
                lines_at = 0
            else:
                out.append('  %s  %s' % (plain_pad(painted, left), lines[0]))
                lines_at = 1
            for more in lines[lines_at:]:
                out.append('  %s  %s' % (' ' * left, more))
    out.append('')
    out.append(pal.head('THINGS PEOPLE ACTUALLY TYPE'))
    wide = min(36, max(len(c.split('\n')[0]) for c, _ in HELP_EXAMPLES) + 2)
    for command, says in HELP_EXAMPLES:
        first, *rest = command.split('\n')
        if len(first) + 2 > wide:
            out.append('  ' + pal.info(first) + ('' if rest or not says else ''))
            for r in rest:
                out.append('  ' + pal.info(r))
            if says:
                out.append('  %s  %s' % (' ' * wide, pal.dim(says)))
        else:
            out.append('  %s%s' % (plain_pad(pal.info(first), wide), pal.dim(says)))
            for r in rest:
                out.append('  ' + pal.info(r))
    out.append('')
    for note in ('the pages are at https://<this machine>/ (enrolment) and /admin/ · '
                 'the configuration is %s' % CONFIG_FILE,
                 'typed with nothing at all it is --status; systemd runs the daemon as '
                 '--daemon, and only one runs at a time',
                 'colour is off when this is piped, and with --no-color or NO_COLOR=1'
                 + ('' if HAVE_COLORAMA else ' (colorama is not installed; colour is '
                                             'written by hand)')):
        for line in textwrap.wrap(note, width - 4):
            out.append('  ' + pal.dim(line))
    out.append('')
    return '\n'.join(out)


def build_parser():
    # Options whole, never shortened (1.0.146): --js was taken for --json -
    # and --check --js went round itself until the stack ran out.
    p = HelpfulParser(prog='otp', add_help=False, allow_abbrev=False, usage='otp [--json] [--no-color] [what to do]',
                      description='a one-time password server: RADIUS, TOTP, the enrolment '
                                  'of tokens and Active Directory, in one Python file',
                      formatter_class=lambda prog: argparse.RawDescriptionHelpFormatter(
                          prog, max_help_position=36, width=100))
    g = p.add_argument_group('EVERYWHERE')
    g.add_argument('-h', '--help', action='store_true', help='this, and stop')
    g.add_argument('--version', action='store_true', help='which version this is, and stop')
    g.add_argument('--config', metavar='FILE', help='use this config file')
    g.add_argument('--no-color', '--no-colour', action='store_true', dest='no_color',
                   help='plain text, no colour')
    g.add_argument('--json', action='store_true', help='answer as JSON where it makes sense')
    g.add_argument('--daemon', action='store_true',
                   help='run the daemon in the foreground (what systemd starts); one at a time')
    g.add_argument('--debug', action='store_true', help='say everything, this run only')
    g = p.add_argument_group('LOOKING', 'Reading what it knows. None of these change anything.')
    g.add_argument('--status', action='store_true', help='what it is doing, in one screen')
    g.add_argument('--check', action='store_true', help='a health check, every part of it')
    g.add_argument('--log', action='store_true', help='the RADIUS requests, newest first')
    g.add_argument('--rejects', action='store_true', help='with --log: only the refusals')
    g.add_argument('--request', type=int, metavar='ID',
                   help='one RADIUS request, every attribute and every step of the decision')
    g.add_argument('--otp-log', action='store_true', help='every check of a code')
    g.add_argument('--tokens', action='store_true', help='who has a token')
    g.add_argument('--token', metavar='NAME', help='one token, and what it has been doing')
    g.add_argument('--events', action='store_true', help='this daemon’s own events')
    g.add_argument('--limit', type=int, default=40, metavar='N', help='how many rows [40]')
    g.add_argument('--hours', type=float, default=24, metavar='N', help='the last N hours [24]')
    g.add_argument('--search', metavar='TEXT', default='', help='only rows holding this')
    g = p.add_argument_group('TOKENS')
    g.add_argument('--enroll', metavar='NAME', help='make a token for NAME (replacing any) and '
                   'show its QR code in the terminal')
    g.add_argument('--pending', action='store_true', help='with --enroll: not in use until a '
                   'code from it is confirmed (--confirm)')
    g.add_argument('--no-qr', action='store_true', help='with --enroll: no QR code, the key only')
    g.add_argument('--by', choices=('app', 'mail', 'sms'), help='with --enroll: the codes come '
                   'from the app [app], or are sent by mail or SMS to --to')
    g.add_argument('--to', metavar='ADDRESS|NUMBER', help='with --enroll --by mail|sms: where the '
                   'codes go')
    g.add_argument('--invert', action='store_true', help='the QR code for a light terminal')
    g.add_argument('--confirm', nargs=2, metavar=('NAME', 'CODE'), help='confirm a waiting token')
    g.add_argument('--verify', nargs=2, metavar=('NAME', 'CODE'),
                   help='is CODE right for NAME now? (uses nothing up)')
    g.add_argument('--disable-token', metavar='NAME', help='switch a token off, keeping it')
    g.add_argument('--enable-token', metavar='NAME', help='switch it on again')
    g.add_argument('--delete-token', metavar='NAME', help='take a token away for good')
    g.add_argument('--scratch', metavar='NAME', help='new recovery codes for NAME')
    g.add_argument('--unlock', metavar='NAME', help='forget the wrong codes, so NAME may try '
                   'again at once')
    g.add_argument('--import-totpcgi', metavar='DIR', help='bring the *.totp files of a totpcgi '
                   'server over')
    g.add_argument('--import-legacy', metavar='ROOT', help='bring a whole totpcgi + FreeRADIUS '
                   'server over: its clients, realms, directory, groups, settings and tokens '
                   '(ROOT holds etc/raddb and etc/totpcgi)')
    g.add_argument('--replace', action='store_true', help='with the imports: replace what is '
                   'here already')
    g = p.add_argument_group('RADIUS')
    g.add_argument('--radtest', nargs='+', metavar='ARG', help='USER CODE [SERVER [PORT '
                   '[SECRET]]] - ask the way radtest does; the server is this one, the secret '
                   'that of the client for 127.0.0.1, unless given. CODE or SECRET as - is '
                   'asked for (or OTP_RADTEST_PASSWORD, OTP_SECRET)')
    g.add_argument('--clients', action='store_true', help='the RADIUS clients')
    g.add_argument('--add-client', metavar='NAME', help='add (or change) a client: with '
                   '--address and --secret, and --realm for names that come without one')
    g.add_argument('--address', metavar='ADDR', help='an address or a range (10.0.0.0/24)')
    g.add_argument('--secret', metavar='TEXT', help='the shared secret (-: from OTP_SECRET, '
                   'or asked - not on the command line)')
    g.add_argument('--realm', metavar='REALM', help='the realm added to names without one')
    g.add_argument('--del-client', metavar='NAME', help='take a client away')
    g.add_argument('--realms', action='store_true', help='the realms')
    g.add_argument('--add-realm', metavar='NAME', help='add (or change) a realm: --suffix, '
                   '--directory, --lookup, --groups, --mode')
    g.add_argument('--suffix', metavar='TEXT', default=None, help='what follows the @ '
                   '(example.cz), * for every name, "" for names without one')
    g.add_argument('--directory', metavar='NAME', help='the directory to look people up in')
    g.add_argument('--lookup', choices=('upn', 'sam', 'none'), help='how names are looked up')
    g.add_argument('--groups', metavar='G1;G2', help='the groups, any one of which lets in')
    g.add_argument('--mode', choices=('otp', 'password_otp', 'password', 'challenge'),
                   help='what the password is: the code, the directory password followed by '
                        'the code, the directory password alone, or the directory password '
                        'and then the code in a second window')
    g.add_argument('--methods', metavar='totp,mail,sms', help='what people may choose on the '
                   'enrolment pages: the app, a code by mail, a code by SMS')
    g.add_argument('--aliases', metavar='a.local,b.cz', help='with --add-realm: other suffixes '
                   'the realm takes too - novak@a.local is the token novak@REALM-SUFFIX; '
                   '"" takes them away')
    g.add_argument('--del-realm', metavar='NAME', help='take a realm away')
    g = p.add_argument_group('ACTIVE DIRECTORY')
    g.add_argument('--directories', action='store_true', help='the directories')
    g.add_argument('--add-directory', metavar='NAME', help='add (or change) one: --hosts, '
                   '--base, --bind-dn, --bind-pw, --tls, --port, --no-verify')
    g.add_argument('--hosts', metavar='H1,H2', help='its servers, in order')
    g.add_argument('--base', metavar='DN', help='where to look: DC=example,DC=local')
    g.add_argument('--bind-dn', metavar='WHO', help='the account it reads with')
    g.add_argument('--bind-pw', metavar='PASS', help='its password: - asks for it (or '
                   'OTP_BIND_PW) - not on the command line, where ps shows it')
    g.add_argument('--tls', choices=('ldaps', 'starttls', 'none'), help='how it is reached')
    g.add_argument('--port', type=int, metavar='N', help='its port')
    g.add_argument('--no-verify', action='store_true', help='do not check its certificate')
    g.add_argument('--weak-certs', choices=('on', 'off'), help='take old, weak certificates '
                   '(a 1024-bit key, SHA-1, TLS 1.0) - still checked against the authority')
    g.add_argument('--ca', metavar='FILE', help='the certificate authority (PEM) that signed it')
    g.add_argument('--del-directory', metavar='NAME', help='take one away')
    g.add_argument('--directory-test', metavar='NAME', help='reach every server of it, step by '
                   'step')
    g.add_argument('--directory-user', nargs=2, metavar=('NAME', 'USER'),
                   help='what the directory says about one person, groups and all')
    g = p.add_argument_group('THE SETTINGS AND THE ACCOUNTS')
    g.add_argument('--settings', action='store_true', help='every setting, as it stands')
    g.add_argument('--set', action='append', metavar='KEY=VALUE', help='change one (again for '
                   'more)')
    g.add_argument('--users', action='store_true', help='who may open the administration pages')
    g.add_argument('--add-user', metavar='NAME', help='make an account (--role)')
    g.add_argument('--role', choices=ROLES_ALL, default=None, help='its role (with --add-user read-only when not given)')
    g.add_argument('--passwd', metavar='NAME', help='set or reset a password (OTP_PASSWORD '
                   'in the environment for a script)')
    g.add_argument('--set-role', metavar='NAME', help='change what an account may do (--role)')
    g.add_argument('--del-user', metavar='NAME', help='remove an account')
    g.add_argument('--disable-user', metavar='NAME', help='stop an account signing in')
    g.add_argument('--enable-user', metavar='NAME', help='let it sign in again')
    g.add_argument('--console', action='store_true',
                   help='the otp console: the whole of otp by its menus, the live log and the '
                        'live RADIUS requests (q leaves it)')
    g.add_argument('--console-at-login', choices=('on', 'off', 'status'), metavar='on|off|status',
                   help='open the console when root signs in at the console or over SSH')
    g.add_argument('--admin-2fa', choices=('on', 'off', 'status'), metavar='on|off|status',
                   help='the second step of signing in to these pages, for every account: '
                        'switch it on or off, or say how it stands')
    g.add_argument('--reset-2fa', metavar='NAME', help='take away the second step an account set '
                   'up for these pages: it sets it up again at its next sign-in')
    g.add_argument('--note', metavar='TEXT', default='', help='a note beside what is made')
    g = p.add_argument_group('THE DATABASE AND ISEMON')
    g.add_argument('--fill-names', action='store_true', help='every token without its owner\'s '
                   'name given it from the directory of its realm')
    g.add_argument('--export-config', metavar='FILE', help='the whole configuration into a JSON '
                   'file - settings, clients, realms, directories, accounts, certificates, the web '
                   'address, the firewall (1.0.62); the tokens are in --backup')
    g.add_argument('--with-secrets', action='store_true', help='--export-config: with the '
                   'secrets in the clear (client secrets, passwords, private keys)')
    g.add_argument('--import-config', metavar='FILE', help='a file of --export-config (or of the '
                   'pages\' export) put in (--yes); with --replace, what is not in the file '
                   'is taken away and settings not in it go back to their defaults')
    g.add_argument('--backup', action='store_true', help='a copy of the database, now')
    # The daemon's copies made by a process of their own (1.0.150), not shown.
    g.add_argument('--dump-copy', action='store_true', help=argparse.SUPPRESS)
    g.add_argument('--restore', metavar='FILE', help='put a copy back (--yes); without --yes, '
                   'what is in it and where it was made')
    g.add_argument('--restore-bundle', metavar='FILE', help='put back a backup sent to a '
                   'destination (otp-backup-....tar.gz.enc): everything - the database, the key '
                   'of the tokens, the node\'s name; without --yes, what is in it')
    g.add_argument('--passphrase-file', metavar='FILE', help='with --restore-bundle: the '
                   'password of the backups, one line (else OTP_BACKUP_PASSWORD, else asked)')
    g.add_argument('--keep-node-name', action='store_true', help='with --restore-bundle: this '
                   'machine keeps its node name')
    g.add_argument('--rbackup-now', action='store_true', help='a backup to every destination '
                   'switched on (Settings → Backups), now')
    g.add_argument('--rbackup-status', action='store_true', help='the backup destinations and '
                   'the last backups sent')
    g.add_argument('--backup-info', metavar='FILE', help='what a copy holds and the machine it '
                   'was made on, its config.json among it')
    g.add_argument('--tidy', action='store_true', help='delete what has been kept long enough')
    g.add_argument('--isemon-test', action='store_true', help='send one line to isemon’s '
                   'receivers and say what happened')
    g = p.add_argument_group('MAINTENANCE AND UPGRADES')
    g.add_argument('--maintenance', choices=('on', 'off', 'status'), help='this node out of '
                   'service (RADIUS not answered, /healthz 503) or back; status says which')
    g.add_argument('--node', metavar='NAME', help='with --maintenance: another node of the '
                   'cluster rather than this one')
    g.add_argument('--why', metavar='TEXT', help='with --maintenance on: why, for the events')
    g.add_argument('--upgrade-status', action='store_true', help='the package sent on the pages '
                   'and how an upgrade started there is going')
    g.add_argument('--upgrade-check', action='store_true', help='look at upgrade_url now for a '
                   'newer otp (as Settings → Upgrades → Look now)')
    g.add_argument('--upgrade-online', nargs='?', const='newest', metavar='VERSION',
                   help='fetch the newest otp (or VERSION) from upgrade_url, check its '
                        'signature, and upgrade every node one at a time - followed here with '
                        'its progress (--yes: without asking)')
    g.add_argument('--upgrade-follow', action='store_true', help='follow an upgrade going on, '
                   'with its progress, until it ends')
    g.add_argument('--downgrade-check', action='store_true', help='the versions at upgrade_url '
                   'older than this one, and whether each may be gone back to')
    g.add_argument('--downgrade', metavar='VERSION|FILE', help='go back to an older otp - VERSION '
                   'from upgrade_url, or an otp-X.Y.Z.tar.gz - only when it is safe: checked '
                   'against how far back the versions that ran here allow, and against the '
                   'database\'s tables; the database itself is not touched. Every node, one at '
                   'a time (--yes: without asking)')
    g.add_argument('--rename-from-opt', action='store_true', help=argparse.SUPPRESS)
    g.add_argument('--change-keep', metavar='net|fw', choices=('net', 'fw'),
                   help='keep a change on trial: a node\'s new network (with --node) or the '
                        'firewall - not kept, it goes back by itself')
    g.add_argument('--change-back', metavar='net|fw', choices=('net', 'fw'),
                   help='put back now what was there before a change on trial')
    g.add_argument('--upgrade-cancel', action='store_true', help='stop an upgrade started on '
                   'the pages: the nodes not yet begun stay as they are')
    g = p.add_argument_group('HIGH AVAILABILITY (TWO NODES, ONE POSTGRESQL)')
    g.add_argument('--ha-status', action='store_true', help='the nodes of the cluster and how '
                   'long since each was heard from')
    g.add_argument('--ha-setup', action='store_true', help='the wizard, on the first node (as '
                   'root): checks, opens PostgreSQL to the second node, writes the bundle')
    g.add_argument('--ha-bundle', metavar='FILE', help='only the bundle for the second node, '
                   'locked with a passphrase that is printed once')
    g.add_argument('--ha-join', metavar='FILE', help='on the second node (as root): join the '
                   'cluster the bundle came from')
    g.add_argument('--ha-peer', metavar='ADDRESS', help='the other node\'s address (for '
                   '--ha-setup)')
    g.add_argument('--ha-peer-port', type=int, metavar='N', default=None,
                   help='the other node\'s PostgreSQL port (5432)')
    g.add_argument('--ha-address', metavar='ADDRESS', help='this node\'s address as the other '
                   'reaches it (default: the one it uses to reach the outside)')
    g.add_argument('--ha-shared', action='store_true', help='with --ha-setup: both nodes open '
                   'one PostgreSQL elsewhere, instead of each its own, replicated')
    g.add_argument('--ha-pause', nargs='?', const='both', choices=('both', 'in', 'out'),
                   help='stop replicating for now (in: what this node takes, out: what the '
                   'other takes from it); it waits in the slot, up to %s' % HA_SLOT_KEEP)
    g.add_argument('--ha-resume', nargs='?', const='both', choices=('both', 'in', 'out'),
                   help='replicate again, from where it stopped')
    g.add_argument('--ha-stop', action='store_true', help='replication off for good: each node '
                   'goes on alone (--yes)')
    g.add_argument('--ha-resync', action='store_true', help='rebuild this node from the other: '
                   'its tables emptied and every row copied over')
    g.add_argument('--ha-compare', action='store_true', help='the rows of every table here and '
                   'on the other node, side by side: are they the same?')
    g.add_argument('--ha-readdress', action='store_true', help='a node\'s address changed '
                   '(as root): --ha-address NEW for this node\'s own, --ha-peer NEW for the '
                   'other\'s - this node put right and the other told (docs/renaming-and-'
                   'readdressing.md)')
    g.add_argument('--ha-tls', action='store_true', help='the link between the two databases: '
                   'how it is protected, each node\'s step and certificate')
    g.add_argument('--ha-tls-repair', action='store_true', help='encrypt and check the link '
                   'between the databases (verify-full) on both nodes - or start the steps again')
    g.add_argument('--ha-tls-off', action='store_true', help='TLS between the databases off '
                   'again on both nodes (the steps the other way round; --yes)')
    g.add_argument('--ha-renamed', metavar='OLD', help='this node was called OLD: what was '
                   'kept under that name (its own settings, maintenance, certificate, place in '
                   'the VIP address) carried to its name now, and OLD off the list')
    g.add_argument('--ha-forget', metavar='NAME', help='take a node off the list for good (one '
                   'that was removed or reinstalled under another name)')
    g.add_argument('--ha-standalone', action='store_true', help='leave the cluster and go on '
                   'alone, keeping everything: replication off, the other node forgotten, '
                   'config.json one server\'s again (--yes)')
    g.add_argument('--ha-db-host', metavar='HOST', help='the database\'s address as the other '
                   'node reaches it (default: this machine\'s)')
    g.add_argument('--node-name', metavar='NAME', help='this node\'s name (--ha-join, '
                   '--ha-setup)')
    g.add_argument('--trusted-proxy', action='append', metavar='CIDR', help='the load '
                   'balancer\'s address: nginx takes the client\'s from X-Forwarded-For when '
                   'it comes from there (again for more)')
    g = p.add_argument_group('TLS AND THE VIP ADDRESS')
    g.add_argument('--web-status', action='store_true', help='the certificates of the nodes and '
                   'of the VIP address, their TLS settings, and where the address is')
    g.add_argument('--tls-for', metavar='TARGET', help='which: a node\'s name, or vip (the web '
                   'address) [this node]')
    g.add_argument('--tls-import', nargs='+', metavar='FILE', help='a certificate in: PEM '
                   'files (certificate, key, chain, root - in any order, or all in one) or a '
                   '.pfx / .p12; its password in OTP_TLS_PASSWORD')
    g.add_argument('--tls-preset', choices=['standard', 'intermediate', 'modern'],
                   help='the protocols and ciphers: standard (TLS 1.2+1.3, ECDHE), intermediate '
                   '(Mozilla, with DHE), modern (TLS 1.3 only)')
    g.add_argument('--tls-dh', choices=sorted(DH_WORDS), help='the DH parameters')
    g.add_argument('--tls-hsts', type=int, metavar='SECONDS', help='Strict-Transport-Security '
                   '(0 = none)')
    g.add_argument('--vip-set', metavar='ADDRESS/PREFIX', help='the VIP address (192.0.2.10/24), '
                   'with --vip-fqdn, --vip-vrid, --vip-iface')
    g.add_argument('--vip-fqdn', metavar='NAME', help='its host name')
    g.add_argument('--vip-vrid', type=int, metavar='N', help='its VRRP id, 1-255 [51]')
    g.add_argument('--vip-iface', action='append', metavar='NODE=IFACE', help='the interface '
                   'it goes on, on that node (again for the other; default: the one with the '
                   'node\'s address)')
    g.add_argument('--vip', choices=['on', 'off'], help='the VIP address on or off')
    g.add_argument('--vip-move', metavar='NODE', help='the VIP address to that node')
    g.add_argument('--vip-return', metavar='NODE|stay', help='where the VIP address goes back '
                   'to when it is well: a node (always back to it), or "stay" (it stays where it '
                   'is until that node fails or it is moved by hand)')
    g.add_argument('--web-retry', action='store_true', help='this node asks root again for what '
                   'failed')
    g.add_argument('--yes', action='store_true', help='do not ask')
    g.add_argument('--discard-local', action='store_true',
                   help='--ha-join: go on even though this node holds tokens of its own, which '
                        'joining throws away (1.0.59: --yes alone no longer means that)')
    return p


HELP_EXAMPLES = [
    ('otp', 'what it is doing (the same as --status)'),
    ('otp --check', 'every part of it: the key, the copies, PHP, clients, realms, directories'),
    ('otp --enroll novak@example.cz', 'a token, with the QR code to scan off the terminal'),
    ('otp --radtest novak 123456', 'what radtest asks, from this machine'),
    ('otp --log --rejects', 'who was refused, and why'),
    ('otp --request 42', 'every step of one decision'),
    ('otp --add-client ASA --address 192.0.2.1 --secret - --realm example.cz',
     'the secret asked for (or OTP_SECRET)'),
    ("otp --add-directory AD --hosts dc1.example.local,dc2.example.local \\\n"
     "    --base DC=example,DC=local --bind-dn otp@example.local --bind-pw -", ''),
    ("otp --add-realm example.cz --suffix example.cz --directory AD --lookup upn \\\n"
     "    --groups 'VPN_USERS;VPN_ADMINS'", ''),
    ('otp --import-legacy /root/old-otp', 'everything from a totpcgi + FreeRADIUS server'),
    ('otp --set isemon=1 --set isemon_targets=isemon.example.local:514/tcp', ''),
    ('otp --ha-setup --ha-peer 192.0.2.12', 'make this the first node of two; then copy the '
     'bundle over'),
    ('otp --ha-join /root/otp-join-otp1.json', 'on the second node: join'),
]



def become_service_user():
    """Run as the daemon's own account when started as root, so that nothing
    the command line writes - the database file and its journal, a copy, the
    key of the tokens - ends up root's and out of the daemon's reach."""
    if os.geteuid() != 0 or os.environ.get('OTP_STAY_ROOT'):
        return
    try:
        import pwd
        import grp
        pw = pwd.getpwnam(SERVICE_USER)
    except (KeyError, ImportError):
        return
    try:
        groups = [g.gr_gid for g in grp.getgrall() if SERVICE_USER in g.gr_mem]
        os.setgroups(sorted(set(groups + [pw.pw_gid])))
        os.setgid(pw.pw_gid)
        os.setuid(pw.pw_uid)
    except OSError as e:
        sys.stderr.write('otp: could not become %s (%s); going on as root\n' % (SERVICE_USER, e))


def chown_to_service(path, mode=None):
    """A file root just wrote, given to the daemon's account - opened without
    following a link, and changed as the open file (1.0.101): by its name,
    a link put in its place meanwhile handed the service any file."""
    if os.geteuid() != 0:
        return
    ids = service_ids()
    if not ids:
        return
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    except OSError:
        return
    try:
        if (os.fstat(fd).st_mode & 0o170000) != 0o100000:    # not a plain file
            return
        os.fchown(fd, ids[0], ids[1])
        if mode is not None:
            os.fchmod(fd, mode)
    except OSError:
        pass
    finally:
        os.close(fd)


NGINX_CONF_PATHS = ('/etc/nginx/conf.d/otp.conf', '/etc/nginx/sites-enabled/otp.conf',
                    '/etc/nginx/sites-available/otp.conf')


def nginx_trusted_proxies(cidrs, pal):
    """The load balancer's addresses into nginx: the client's own address is
    then taken from X-Forwarded-For when a request comes from one of them -
    for the allow lists, the sign-in throttle and every log."""
    conf = next((p for p in NGINX_CONF_PATHS if os.path.exists(p)), None)
    if not conf:
        print(pal.bad_line('no nginx configuration of otp was found (%s)'
                           % ', '.join(NGINX_CONF_PATHS)))
        return False
    for c in cidrs:
        address_net(c)
    text = Path(conf).read_text()
    block = ('    # REALIP-BEGIN - the load balancer(s), written by otp --trusted-proxy\n'
             + ''.join('    set_real_ip_from %s;\n' % c for c in cidrs)
             + ('    real_ip_header X-Forwarded-For;\n    real_ip_recursive on;\n' if cidrs else '')
             + '    # REALIP-END\n')
    if '# REALIP-BEGIN' in text:
        text = re.sub(r'    # REALIP-BEGIN.*?# REALIP-END\n', lambda m: block, text, flags=re.S)
    else:
        # ...in the HTTPS server, which is the one with the pages - not the
        # first block in the file, which is the port-80 redirect. The block
        # whose `listen` names 443 is the one; failing that, the last one.
        heads = list(re.finditer(r'server\s*\{[^\n]*\n', text))
        if not heads:
            print(pal.bad_line('no server block was found in %s' % conf))
            return False
        chosen = heads[-1]
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            if re.search(r'^\s*listen\s[^;]*\b443\b', text[h.end():end], re.M):
                chosen = h
                break
        text = text[:chosen.end()] + block + text[chosen.end():]
    Path(conf + '.before-realip').write_text(Path(conf).read_text())
    Path(conf).write_text(text)
    got = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    if got.returncode != 0:
        Path(conf).write_text(Path(conf + '.before-realip').read_text())
        print(pal.bad_line('nginx did not take it, so it was put back: %s'
                           % (got.stderr.strip().split('\n')[-1])))
        return False
    subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True)
    print(pal.ok_line('nginx takes the client\'s address from X-Forwarded-For when it comes '
                      'from %s' % ', '.join(cidrs) if cidrs else 'nginx trusts no proxy'))
    return True


def cli_ha(args, pal):
    """The high-availability wizard and its parts, as root."""
    def ask(prompt, default=''):
        if args.yes or not sys.stdin.isatty():
            return default
        got = input('%s%s: ' % (prompt, ' [%s]' % default if default else '')).strip()
        return got or default

    if os.geteuid() != 0 and (args.ha_setup or args.ha_join or args.trusted_proxy):
        raise SystemExit('otp: run this as root - it changes PostgreSQL, nginx and the key '
                         'of the tokens')
    os.environ['OTP_STAY_ROOT'] = '1'
    load_config(saved=None)
    if args.trusted_proxy and not (args.ha_setup or args.ha_join):
        return 0 if nginx_trusted_proxies(args.trusted_proxy, pal) else 1

    if args.ha_join:
        try:
            bundle = Path(args.ha_join).read_text()
        except OSError as e:
            raise SystemExit('otp: %s' % e)
        phrase = os.environ.get('OTP_HA_PASSPHRASE') or getpass.getpass(
            'The passphrase printed with the bundle: ')
        try:
            data = bundle_open(bundle, phrase)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        peer = data.get('peer') or {}
        if data.get('mode') == 'replicated':
            return cli_ha_join_replicated(args, pal, data, ask)
        print(pal.head('joining the cluster of %s' % (peer.get('name') or '?'))
              + pal.dim('  (%s)' % db_where(data['db'])))
        name = args.node_name or ask('This node\'s name', socket.gethostname().split('.')[0])
        try:
            store0 = Storage(open_db())
            HA_STORE['store'] = store0
        except Exception:                               # noqa: BLE001
            pass
        try:
            got = ha_join(data, name, even_if_data=args.discard_local)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        chown_to_service(sealing_key_path(), 0o600)
        chown_to_service(CONFIG_FILE, 0o640)
        print(pal.ok_line('the database: %s (%s record(s) in it)' % (got['where'], got['rows'])))
        print(pal.ok_line('the key that opens the tokens is the cluster\'s'))
        if args.trusted_proxy:
            nginx_trusted_proxies(args.trusted_proxy, pal)
        if not os.environ.get('OTP_HA_NO_RESTART'):
            subprocess.run(['systemctl', 'restart', 'otp'], capture_output=True)
            print(pal.ok_line('otp started again on it as %s' % name))
        print(pal.dim('  Both nodes are in the list:  otp --ha-status'))
        print(pal.dim('  Sign in with the accounts of the cluster - the ones of this node were '
                      'in its own database, which is no longer used.'))
        return 0

    if args.ha_resync:
        return cli_ha_resync(args, pal)
    if args.ha_standalone:
        return cli_ha_standalone(args, pal)
    # --ha-setup and --ha-bundle: the first node.
    store = Storage(open_db())
    load_config(saved=store.settings_saved())
    HA_STORE['store'] = store
    host0 = str(CONFIG.get('db_host') or '')
    if store.db.engine == 'postgres' and host0 in ('', 'localhost', '127.0.0.1', '::1') \
            and not args.ha_shared and (args.ha_setup or CONFIG.get('ha_mode') == 'replicated'):
        return cli_ha_setup_replicated(args, pal, store, ask)
    print(pal.head('high availability - the first node') + pal.dim('  (%s)' % node_name()))
    bad = False
    for c in ha_checks(store):
        if c['ok'] and not c.get('warn'):
            print(pal.ok_line(c['says']))
        elif c.get('warn'):
            print(pal.warn_line(c['says']))
        else:
            print(pal.bad_line(c['says']))
            bad = True
    if bad:
        return 1
    host = str(CONFIG.get('db_host') or '')
    local = host in ('', 'localhost', '127.0.0.1', '::1')
    db_host = args.ha_db_host or (node_address() if local else host)
    if args.ha_setup:
        peer = args.ha_peer or ask('The other node\'s address')
        if local:
            if not peer:
                raise SystemExit('otp: the other node\'s address is needed: --ha-peer ADDRESS')
            try:
                peer_address(peer)
            except ValueError as e:
                raise SystemExit('otp: %s' % e)
            try:
                for line in pg_open_to(peer, CONFIG.get('db_name'), CONFIG.get('db_user')):
                    print(pal.ok_line('PostgreSQL: %s' % line))
            except ValueError as e:
                raise SystemExit('otp: PostgreSQL could not be opened to %s: %s' % (peer, e))
            if True:
                listen = pg_local_admin('SELECT pending_restart FROM pg_settings WHERE '
                                        "name = 'listen_addresses'")
                if listen == 't':
                    unit = tune_restart_unit() or 'postgresql'
                    if args.yes or ask('PostgreSQL has to start again to listen on the network '
                                       '- restart %s now? (yes/no)' % unit, 'yes') == 'yes':
                        subprocess.run(['systemctl', 'restart', unit], capture_output=True)
                        print(pal.ok_line('%s started again' % unit))
                    else:
                        print(pal.bad_line('restart %s before the other node joins' % unit))
            firewall_peer(peer, pal, 5432)
        if args.trusted_proxy:
            nginx_trusted_proxies(args.trusted_proxy, pal)
        name = args.node_name
        if name and name != node_name():
            write_file_settings({'node_name': name})
            chown_to_service(CONFIG_FILE, 0o640)
    data = ha_bundle_data(store, db_host)
    phrase = ha_passphrase()
    target = Path(args.ha_bundle or '/root/otp-join-%s.json' % node_name())
    write_private(target, json.dumps(bundle_lock(data, phrase), indent=1) + '\n')
    store.add_event('settings', 'a bundle for a second node was made on the command line '
                    '(the database at %s)' % db_host, 'warn', who='command line')
    print('')
    print(pal.ok_line('the bundle for the second node: %s' % target))
    print('  ' + pal.bold('its passphrase, shown only now: ') + pal.info(phrase))
    print('')
    print(pal.head('on the second node'))
    print('  1. install the same version:   ./install.sh --with-db postgres --yes')
    print('  2. copy the bundle over:       scp %s root@SECOND:/root/' % target)
    print('  3. join:                       otp --ha-join /root/%s' % target.name)
    print('')
    print(pal.head('in front of both'))
    print('  HTTPS: round robin, no stickiness needed; health check  GET /healthz  (200 = up).')
    print('  RADIUS: give the VPN both nodes as servers (or balance UDP 1812/1813 to both).')
    print('  The load balancer\'s address on both nodes:  otp --trusted-proxy CIDR')
    return 0


def firewall_peer(peer, pal, port=5432):
    """firewalld letting the other node - one address - reach PostgreSQL."""
    if shutil.which('firewall-cmd'):
        a = peer_address(peer)
        rule = ('rule family="%s" source address="%s/%d" port port="%d" protocol="tcp" accept'
                % ('ipv4' if a.version == 4 else 'ipv6', a, 32 if a.version == 4 else 128,
                   port))
        subprocess.run(['firewall-cmd', '--permanent', '--add-rich-rule=' + rule],
                       capture_output=True)
        subprocess.run(['firewall-cmd', '--reload'], capture_output=True)
        print(pal.ok_line('firewalld lets %s reach PostgreSQL (TCP %d)' % (peer, port)))


def cli_ha_setup_replicated(args, pal, store, ask):
    """The first node of two, each with its own PostgreSQL, replicating."""
    say = lambda t: print(pal.ok_line(t))
    print(pal.head('high availability - the first node, replicated') + pal.dim(
        '  (%s: a PostgreSQL on each node, replicating both ways)' % node_name()))
    peer = args.ha_peer or CONFIG.get('ha_peer') or ask('The other node\'s address')
    if not peer:
        raise SystemExit('otp: the other node\'s address is needed: --ha-peer ADDRESS')
    try:
        peer_address(peer)
    except ValueError as e:
        raise SystemExit('otp: %s' % e)
    port = int(CONFIG.get('db_port') or 5432)
    name, user, pw = CONFIG.get('db_name'), CONFIG.get('db_user'), CONFIG.get('db_password')
    try:
        restart, major = pg_prepare_local(port, peer, name, user, pw, say)
        if restart:
            if args.yes or ask('PostgreSQL has to start again for this (wal_level = logical, '
                               'listening on the network) - restart it now? (yes/no)',
                               'yes') == 'yes':
                pg_restart_local(port)
                say('PostgreSQL started again')
                store.db.close()
                store.db.connect()
            else:
                raise SystemExit('otp: restart PostgreSQL, then run this again')
        pg_publication(port, name)
        say('PostgreSQL publishes every table of %s (inserts, updates, deletes)' % name)
        ha_sequences(store.db, 1)
        say('this node numbers its rows odd, the other even - they never collide')
    except ValueError as e:
        raise SystemExit('otp: %s' % e)
    firewall_peer(peer, pal, port)
    if args.trusted_proxy:
        nginx_trusted_proxies(args.trusted_proxy, pal)
    me = args.ha_address or CONFIG.get('ha_address') or node_address()
    changes = {'ha_mode': 'replicated', 'ha_slot': 1, 'ha_peer': peer,
               'ha_peer_port': int(args.ha_peer_port or 5432), 'ha_address': me}
    if args.node_name:
        changes['node_name'] = args.node_name
    write_file_settings(changes)
    chown_to_service(CONFIG_FILE, 0o640)
    load_config(saved=store.settings_saved())
    # Made here if the daemon never ran yet (1.0.140): the bundle held an empty
    # key, and the second node wrote an empty secrets.key and could not start.
    data = {'mode': 'replicated', 'key': sealing_key(make=True).hex(), 'pg_major': major,
            'slot': 2,
            'db': {'db_name': name, 'db_user': user, 'db_password': pw},
            'peer': {'name': node_name(), 'address': me, 'port': port, 'slot': 1},
            'cluster': CONFIG.get('site_name') or 'otp'}
    phrase = ha_passphrase()
    target = Path(args.ha_bundle or '/root/otp-join-%s.json' % node_name())
    write_private(target, json.dumps(bundle_lock(data, phrase), indent=1) + '\n')
    store.add_event('settings', 'this node became the first of two, replicating with %s; a '
                    'bundle for the second was made on the command line' % peer, 'warn',
                    who='command line')
    if not os.environ.get('OTP_HA_NO_RESTART'):
        subprocess.run(['systemctl', 'restart', 'otp'], capture_output=True)
    print('')
    say('the bundle for the second node: %s' % target)
    print('  ' + pal.bold('its passphrase, shown only now: ') + pal.info(phrase))
    print('')
    print(pal.head('on the second node (%s)' % peer))
    print('  1. install the same version:   ./install.sh --with-db postgres --yes')
    print('  2. copy the bundle over:       scp %s root@%s:/root/' % (target, peer))
    print('  3. join:                       otp --ha-join /root/%s --node-name NAME' % target.name)
    print('     It installs PostgreSQL %d there if it is missing, copies every row from this '
          'node' % major)
    print('     and sets both directions of the replication up. The same command rebuilds it '
          'after a reinstall.')
    return 0


def cli_ha_join_replicated(args, pal, data, ask):
    say = lambda t: print(pal.ok_line(t))
    peer = data.get('peer') or {}
    db = data.get('db') or {}
    name, user, pw = db.get('db_name'), db.get('db_user'), db.get('db_password')
    if not re.match(r'^[0-9a-f]{64}\Z', str(data.get('key') or '')):
        raise SystemExit('otp: the bundle holds no key - make it again on the first node '
                         '(otp --ha-bundle), with this version')
    print(pal.head('joining %s - a PostgreSQL on each node, replicating both ways'
                   % (peer.get('name') or '?')))
    node = args.node_name or ask('This node\'s name', socket.gethostname().split('.')[0])
    port = int(FILE_CONFIG.get('db_port') or 5432) if FILE_CONFIG.get('db_engine') == 'postgres' \
        else 5432
    try:
        if not pg_local_running(port):
            pg_install_local(int(data.get('pg_major') or 16), say)
        restart, major = pg_prepare_local(port, peer['address'], name, user, pw, say)
        if restart:
            pg_restart_local(port)
            say('PostgreSQL started again')
        firewall_peer(peer['address'], pal, port)
        local = db_open({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': port,
                         'db_name': name, 'db_user': user, 'db_password': pw})
        local.make_tables()
        local.add_missing_columns()
        pg_publication(port, name)
        remote = db_open({'db_engine': 'postgres', 'db_host': peer['address'],
                          'db_port': int(peer.get('port') or 5432), 'db_name': name,
                          'db_user': user, 'db_password': pw})
        me = args.ha_address or node_address()
        # The daemon stopped while the rows come over, as --ha-resync does
        # (1.0.59): its heartbeat written into the tables being copied
        # stopped the copy on a duplicate key. Started again at the end.
        if os.geteuid() == 0 and not os.environ.get('OTP_HA_NO_RESTART') and \
                subprocess.run(['systemctl', 'is-active', '--quiet', 'otp']).returncode == 0:
            subprocess.run(['systemctl', 'stop', 'otp'], capture_output=True)
            say('otp is stopped on this node while the rows come over')
        got = ha_rebuild(local, remote, int(data.get('slot') or 2), int(peer.get('slot') or 1),
                         me, port, peer['address'], int(peer.get('port') or 5432),
                         name, user, pw, lambda t: print(pal.dim('  ' + t)))
        remote.close()
        local.close()
    except (ValueError, DbError) as e:
        if os.geteuid() == 0 and not os.environ.get('OTP_HA_NO_RESTART'):
            subprocess.run(['systemctl', 'start', 'otp'], capture_output=True)
        raise SystemExit('otp: %s' % e)
    now = sealing_key()
    if now and now.hex() != data['key']:
        write_replacing(sealing_key_path().with_name('secrets.key.before-join'), now.hex() + '\n',
                        0o600)
    write_replacing(sealing_key_path(), data['key'] + '\n', 0o600)
    chown_to_service(sealing_key_path(), 0o600)
    write_file_settings({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': port,
                         'db_name': name, 'db_user': user, 'db_password': pw,
                         'node_name': node, 'ha_mode': 'replicated',
                         'ha_slot': int(data.get('slot') or 2), 'ha_peer': peer['address'],
                         'ha_peer_port': int(peer.get('port') or 5432), 'ha_address': me})
    chown_to_service(CONFIG_FILE, 0o640)
    say('every row of %s is here: %d' % (peer.get('name') or 'the other node', got['rows']))
    say('both directions replicate: this node -> %s and %s -> this node'
        % (peer.get('name'), peer.get('name')))
    if args.trusted_proxy:
        nginx_trusted_proxies(args.trusted_proxy, pal)
    if not os.environ.get('OTP_HA_NO_RESTART'):
        subprocess.run(['systemctl', 'restart', 'otp'], capture_output=True)
        say('otp started again as %s, on its own PostgreSQL' % node)
    print(pal.dim('  otp --ha-status shows both nodes and both directions.'))
    return 0


def cli_sure(args, what):
    """A destructive step asked about once (1.0.59): --yes says it ahead,
    a terminal is asked, anything else is refused."""
    if getattr(args, 'yes', False):
        return
    if sys.stdin.isatty():
        try:
            said = input('otp: %s. Type yes to go on: ' % what)
        except EOFError:
            said = ''
        if said.strip().lower() == 'yes':
            return
        raise SystemExit('otp: nothing was changed')
    raise SystemExit('otp: %s - again with --yes' % what)


def cli_ha_resync(args, pal):
    load_config(saved=None)
    if CONFIG.get('ha_mode') != 'replicated':
        raise SystemExit('otp: this node does not replicate (ha_mode is not "replicated")')
    # Root only (1.0.59): anybody else could not stop the daemon, and the
    # copy went on with it writing - the very thing that stops it for good.
    if os.geteuid() != 0:
        raise SystemExit('otp: --ha-resync is run as root (sudo otp --ha-resync --yes)')
    if not args.yes:
        raise SystemExit('otp: this empties this node\'s tables and copies every row from '
                         '%s - again with --yes' % CONFIG.get('ha_peer'))
    # The daemon stopped while the rows come over (1.0.47): it is another
    # process, and its heartbeat written meanwhile met the same row coming
    # from the other node - the copy stopped there for good.
    stopped = False
    if os.geteuid() == 0 and not os.environ.get('OTP_HA_NO_RESTART') and \
            subprocess.run(['systemctl', 'is-active', '--quiet', 'otp']).returncode == 0:
        subprocess.run(['systemctl', 'stop', 'otp'], capture_output=True)
        stopped = True
        print(pal.dim('  otp is stopped on this node while it is rebuilt (the other node answers)'))
    try:
        local = open_db()
        # What is here kept first, as the pages do (1.0.47): a rebuild
        # replaces all of it.
        try:
            kept = make_backup(Storage(local), 'before this node was rebuilt from the other, '
                               'on the command line')
            print(pal.ok_line('a copy of what was here: %s' % kept))
        except Exception as e:                          # noqa: BLE001
            raise SystemExit('otp: no copy of what is here could be made, so nothing was '
                             'changed: %s' % e)
        remote = ha_peer_db()
        got = ha_rebuild(local, remote, int(CONFIG.get('ha_slot') or 2),
                         3 - int(CONFIG.get('ha_slot') or 2),
                         CONFIG.get('ha_address') or node_address(),
                         int(CONFIG.get('db_port') or 5432), CONFIG.get('ha_peer'),
                         int(CONFIG.get('ha_peer_port') or 5432), CONFIG.get('db_name'),
                         CONFIG.get('db_user'), CONFIG.get('db_password'),
                         lambda t: print(pal.dim('  ' + t)))
    except (ValueError, DbError) as e:
        raise SystemExit('otp: %s' % e)
    finally:
        if stopped:
            subprocess.run(['systemctl', 'start', 'otp'], capture_output=True)
            print(pal.dim('  otp is started again on this node'))
    print(pal.ok_line('rebuilt from %s: %d row(s)' % (CONFIG.get('ha_peer'), got['rows'])))
    return 0


def cli_ha_standalone(args, pal):
    """This node out of the cluster, on its own, with everything it has
    (1.0.47): the replication taken away (as --ha-stop), what is left of it
    in this PostgreSQL removed, the other nodes forgotten, and config.json
    a single server's again. The database, the key, the settings, the
    tokens and the accounts stay as they are."""
    if os.geteuid() != 0:
        raise SystemExit('otp: run this as root - it writes config.json and restarts otp')
    if not CONFIG.get('ha_mode') and not args.yes:
        raise SystemExit('otp: this node is not one of a cluster (ha_mode is empty)')
    if not args.yes:
        raise SystemExit('otp: this takes this node out of the cluster for good: the replication '
                         'goes, the other node is forgotten, and it answers alone with what it '
                         'has - again with --yes')
    say = lambda t: print(pal.ok_line(t))
    try:
        store = Storage(open_db())
    except DbError as e:
        raise SystemExit('otp: %s' % e)
    load_config(saved=store.settings_saved())
    HA_STORE['store'] = store
    mode = CONFIG.get('ha_mode') or ''
    if mode == 'replicated' and store.db.engine == 'postgres':
        try:
            say(ha_control(store, 'stop', by='command line')['message'])
        except Exception as e:                          # noqa: BLE001
            print(pal.warn_line('the replication: %s' % str(e).split('\n')[0][:200]))
        # Whatever is left of it here - the other node gone for good, or
        # names from before - taken away too.
        for r in store.db.rows("SELECT subname FROM pg_subscription WHERE subdbid = (SELECT oid "
                               "FROM pg_database WHERE datname = current_database()) AND subname "
                               "LIKE 'o__!_from!_%' ESCAPE '!'"):
            ha_drop_sub(store.db, r['subname'])
            say('the subscription %s is gone' % r['subname'])
        for r in store.db.rows("SELECT slot_name FROM pg_replication_slots WHERE slot_name "
                               "LIKE 'o__!_from!_%' ESCAPE '!' AND database = current_database()"):
            try:
                _ha_drop_slot(store.db, r['slot_name'])
                say('the replication slot %s is gone (nothing is kept for the other node '
                    'any more)' % r['slot_name'])
            except Exception as e:                      # noqa: BLE001
                print(pal.warn_line('the slot %s: %s' % (r['slot_name'], e)))
    for n in ha_nodes(store):
        if n['me']:
            continue
        ha_forget(store, n['name'])
        store.db.run('DELETE FROM meta WHERE k IN (?, ?)',
                     ('maint:' + n['name'], 'upgrade:node:' + n['name']))
        say('%s is off the list of nodes' % n['name'])
    write_file_settings({'ha_mode': '', 'ha_slot': 0, 'ha_peer': '', 'ha_address': '',
                         'ha_peer_port': DEFAULTS.get('ha_peer_port')})
    chown_to_service(CONFIG_FILE, 0o640)
    say('%s: a single server again (the database, the key and the node\'s name are kept)'
        % CONFIG_FILE)
    store.add_event('settings', '%s left the cluster on the command line and answers alone'
                    % node_name(), 'warn', who='command line')
    store.db.close()
    if not os.environ.get('OTP_HA_NO_RESTART'):
        subprocess.run(['systemctl', 'restart', 'otp'], capture_output=True)
        say('otp started again, alone')
    if mode == 'shared':
        print(pal.warn_line('the other node still opens the same database: stop it or '
                            'uninstall it there, or it goes on answering from it'))
    print(pal.dim('  The other node, if it still runs: otp --ha-standalone --yes there too, '
                  'or uninstall it.'))
    return 0


def cli_ha_compare(store, pal, as_json=False):
    """Every table counted here and on the other node (1.0.47)."""
    if CONFIG.get('ha_mode') != 'replicated':
        raise SystemExit('otp: this node does not replicate (ha_mode is %r) - with one shared '
                         'database there is nothing to compare' % (CONFIG.get('ha_mode') or ''))
    try:
        far = ha_peer_db()
    except Exception as e:                              # noqa: BLE001
        raise SystemExit('otp: the other node\'s PostgreSQL cannot be reached: %s'
                         % str(e).split('\n')[0][:200])
    rows, same = [], True
    try:
        for t in TABLES:
            if t == 'meta':
                q = ("SELECT COUNT(*) FROM meta WHERE " + ' AND '.join(
                    "k NOT LIKE '%s%%'" % p for p in META_TRANSIENT))
                here_n, there_n = store.db.value(q), far.value(q)
                here_m = there_m = None
            else:
                here_n = store.db.value('SELECT COUNT(*) FROM %s' % t)
                there_n = far.value('SELECT COUNT(*) FROM %s' % t)
                if 'id' in [c.lower() for c in store.db.columns(t)]:
                    here_m = store.db.value('SELECT MAX(id) FROM %s' % t)
                    there_m = far.value('SELECT MAX(id) FROM %s' % t)
                else:
                    here_m = there_m = None
            ok = int(here_n or 0) == int(there_n or 0) and here_m == there_m
            same = same and ok
            rows.append((t, here_n, there_n, here_m, there_m, ok))
    finally:
        far.close()
    if as_json:
        print(json.dumps({'same': same, 'tables': [dict(zip(
            ('table', 'here', 'there', 'max_id_here', 'max_id_there', 'same'), r))
            for r in rows]}, default=str))
        return 0 if same else 4
    print(table([(t, str(a), str(b), str(c if c is not None else '-'),
                  str(d if d is not None else '-'), 'same' if ok else 'DIFFERENT')
                 for t, a, b, c, d, ok in rows],
                ['table', 'rows here (%s)' % node_name(), 'rows there', 'last id here',
                 'last id there', '']))
    if same:
        print(pal.ok_line('both nodes hold the same rows'))
    else:
        print(pal.warn_line('they differ. A moment after a change that is normal (the logs '
                            'grow on both): ask again in a few seconds. If it stays so, see '
                            'otp --ha-status; the node that was away is rebuilt with '
                            'otp --ha-resync --yes ON THAT NODE.'))
    return 0 if same else 4


def cli_web(args, pal, store):
    """TLS and the VIP address on the command line (1.0.47)."""
    who = 'command line'
    me = node_name()
    target = args.tls_for or me
    if (args.tls_import or args.tls_preset or args.tls_dh or args.tls_hsts is not None) and \
            target not in tls_targets(store):
        raise ValueError('there is no node or address called %s (a node\'s name, or vip)'
                         % target)
    said = []
    if args.tls_import:
        pem, pfx = '', b''
        for raw in args.tls_files:
            if b'-----BEGIN' in raw:
                pem += raw.decode('utf-8', 'replace') + '\n'
            else:
                if pfx:
                    raise ValueError('one .pfx / .p12 at a time')
                pfx = raw
        prof = tls_profile(store, target) or {}
        pending = unseal_secret(prof['pending_key'], 'web:tls') if prof.get('pending_key') else ''
        got = cert_bundle(cert=pem, pfx=pfx, password=os.environ.get('OTP_TLS_PASSWORD', ''),
                          pending_key=pending)
        prof.update(cert=got['cert'], chain=got['chain'], root=got['root'],
                    key=seal_secret(got['key'], 'web:tls'), info=got['info'],
                    chain_info=got['chain_info'], root_info=got['root_info'],
                    verify=got['verify'], how='imported on the command line')
        prof.pop('pending_key', None)
        prof.pop('csr', None)
        prof.setdefault('preset', 'standard')
        prof.setdefault('dh', 'none')
        tls_save(store, target, prof, who)
        i = got['info']
        said.append('%s: %s, until %s, %d in the chain, root %s%s' % (
            target, i.get('subject'), stamp(i.get('not_after')), len(got['chain_info']),
            'given' if got['root'] else 'not given',
            ', chain checked' if got['verify'] == 'ok' else
            (' - the chain does not check: %s' % got['verify'] if got['verify'] else '')))
        store.add_event('settings', 'a certificate was put in for %s on the command line: %s'
                        % (target, i.get('subject')), 'warn', who=who)
    if args.tls_preset or args.tls_dh or args.tls_hsts is not None:
        prof = tls_profile(store, target) or {}
        pol = tls_policy_checked({'preset': args.tls_preset or prof.get('preset') or 'standard',
                                  'protocols': prof.get('protocols'),
                                  'ciphers': prof.get('ciphers'),
                                  'dh': args.tls_dh or prof.get('dh') or 'none',
                                  'prefer': prof.get('prefer'),
                                  'hsts': args.tls_hsts if args.tls_hsts is not None
                                  else prof.get('hsts') or 0})
        prof.update(pol)
        tls_save(store, target, prof, who)
        said.append('%s: %s, DH %s, HSTS %s' % (target, pol['preset'], pol['dh'],
                                               pol['hsts'] or 'off'))
    if args.vip_set or args.vip or args.vip_move or args.vip_return:
        if not CONFIG.get('ha_mode'):
            raise ValueError('the VIP address is for a cluster: otp --ha-setup first')
    if args.vip_set:
        v = vip_conf(store)
        ifaces = dict(v.get('ifaces') or {})
        for one in args.vip_iface or []:
            if '=' not in one:
                raise ValueError('--vip-iface NODE=IFACE')
            k, val = one.split('=', 1)
            ifaces[k.strip()] = val.strip()
        got = vip_checked({'address': args.vip_set, 'fqdn': args.vip_fqdn
                           if args.vip_fqdn is not None else v.get('fqdn'),
                           'vrid': args.vip_vrid or v.get('vrid') or 51, 'ifaces': ifaces},
                          store)
        vip_set(store, who, **got)
        said.append('the VIP address: %s%s, VRRP id %d' % (
            got['address'], ' (%s)' % got['fqdn'] if got['fqdn'] else '', got['vrid']))
    if args.vip:
        v = vip_conf(store)
        if args.vip == 'on' and not v.get('address'):
            raise ValueError('give the address first: --vip-set 192.0.2.10/24')
        vip_set(store, who, on=args.vip == 'on')
        store.add_event('settings', 'the VIP address was turned %s on the command line'
                        % args.vip, 'warn', who=who)
        said.append('the VIP address is %s' % args.vip)
    if args.vip_return:
        if args.vip_return == 'stay':
            vip_set(store, who, mode='stays')
            said.append('the VIP address stays where it is: it moves only when that node fails '
                        'or by hand')
        else:
            if args.vip_return not in {n['name'] for n in ha_nodes(store)}:
                raise ValueError('there is no node called %s' % args.vip_return)
            vip_set(store, who, mode='back', prefer=args.vip_return)
            said.append('the VIP address always goes back to %s' % args.vip_return)
        store.add_event('settings', 'the VIP address: %s, on the command line' % said[-1],
                        'warn', who=who)
    if args.vip_move:
        names = {n['name']: n for n in ha_nodes(store)}
        if args.vip_move not in names:
            raise ValueError('there is no node called %s' % args.vip_move)
        if vip_conf(store).get('mode') == 'stays':
            vip_set(store, who, move_to=args.vip_move, move_at=time.time())
        else:
            vip_set(store, who, prefer=args.vip_move)
        store.add_event('settings', 'the VIP address was moved to %s on the command line'
                        % args.vip_move, 'warn', who=who)
        said.append('the VIP address goes to %s (when it is healthy)' % args.vip_move)
    if args.web_retry:
        store.set_meta('web:retry:' + me, str(time.time()))
        said.append('%s asks root again' % me)
    for w in said:
        print(pal.ok_line(w))
    if said:
        print(pal.dim('  each node puts it in within a few seconds: otp --web-status'))
        return 0
    # --web-status
    v = vip_conf(store)
    beats = {n['name']: n for n in ha_nodes(store)}
    if args.json:
        print(json.dumps({'vip': v, 'nodes': {k: (b.get('web') if not b['me'] else web_state(store))
                                               for k, b in beats.items()},
                          'tls': {t: tls_view(tls_profile(store, t)) for t in tls_targets(store)}},
                         default=str))
        return 0
    print(pal.head('the VIP address'))
    if not CONFIG.get('ha_mode'):
        print(pal.dim('  one server: no VIP address (it is for a cluster)'))
    elif not v.get('address'):
        print(pal.dim('  not set: otp --vip-set 192.0.2.10/24 --vip-fqdn otp.example.cz'))
    else:
        print('  %s%s, VRRP id %s, %s, meant to be on %s' % (
            v['address'], ' (%s)' % v['fqdn'] if v.get('fqdn') else '', v.get('vrid') or 51,
            pal.good('ON') if v.get('on') else pal.dim('off'), vip_prefer(store, v)))
    for name, b in sorted(beats.items()):
        # What the daemons said in their heartbeats - not this command's own
        # look, which knows nothing of the daemon's health checks.
        w = b.get('web') or {}
        line = '%-16s %s' % (name, 'HOLDS THE ADDRESS' if w.get('vip_here') else
                             (w.get('role') or '-'))
        hl = w.get('health') or {}
        if v.get('on'):
            line += '  health: %s' % ('ok' if hl.get('ok') else 'NOT OK - %s' % (hl.get('why') or '?'))
        line += '  root: %s%s' % (w.get('state') or 'nothing asked yet',
                                  '' if w.get('current') or not w.get('state') else ' (not current)')
        print(('  ' + line) if b.get('alive') else pal.bad_line(line + ' (not answering)'))
        for s in (w.get('said') or [])[-3:]:
            print(pal.dim('      ' + s))
    print(pal.head('TLS'))
    for t in tls_targets(store):
        prof = tls_profile(store, t)
        b = beats.get(t, {})
        now = (b.get('web') or {}).get('cert_now') if t != 'vip' else None
        if t == me:
            now = web_state(store).get('cert_now')
        i = (prof or {}).get('info') or now or {}
        left = (float(i['not_after']) - time.time()) / 86400 if i.get('not_after') else None
        print('  %-16s %s%s' % (t, i.get('subject') or pal.dim('no certificate of its own'),
                                ', until %s (%d days)' % (stamp(i['not_after']), left)
                                if left is not None else ''))
        if prof:
            print(pal.dim('                   %s, DH %s%s%s' % (
                prof.get('preset') or 'standard', prof.get('dh') or 'none',
                ', HSTS %s s' % prof['hsts'] if prof.get('hsts') else '',
                ', a request waits for its certificate' if prof.get('pending_key') else '')))
        elif t != 'vip':
            print(pal.dim('                   as install.sh made it (otp does not look after it)'))
    return 0


def cli_stage_files(args):
    """The files named on the command line, opened as whoever typed it - root
    - before the service's account takes over (1.0.103): a backup, a
    configuration or an old server's tree in /root were not the otp account's
    to read, and the documented recovery failed with "Permission denied".
    Copied into a folder of the service's own, taken away at the end; a file
    to write is opened now and written to later."""
    if os.geteuid() != 0 or os.environ.get('OTP_STAY_ROOT'):
        return
    ids = service_ids()
    if not ids:
        return
    import atexit
    import stat

    def reachable(path):
        """A file the otp account can get at by itself (1.0.149): any step of
        its path that account's, or under its own folders. Not copied by
        root - the otp account opens it, and a link it planted there leads
        only where it may go anyway (/etc/shadow was copied to it)."""
        p = os.path.abspath(str(path))
        try:
            real = os.path.realpath(p)
        except OSError:
            real = p
        for own in (STATE_DIR, LOG_DIR, RUN_DIR, CONFIG_FILE.parent):
            o = os.path.realpath(str(own))
            if real == o or real.startswith(o + os.sep) or p.startswith(o + os.sep):
                return True
        cur = p
        while True:
            try:
                if os.lstat(cur).st_uid == ids[0]:
                    return True
            except OSError:
                pass
            up = os.path.dirname(cur)
            if up == cur:
                return False
            cur = up

    def copy_in(src, dst):
        """One file copied by its descriptors, never by name: not through a
        link at either end, into a new file only."""
        fi = os.open(str(src), os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
        try:
            if not stat.S_ISREG(os.fstat(fi).st_mode):
                raise OSError('%s is not a plain file' % src)
            fo = os.open(str(dst), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                while True:
                    chunk = os.read(fi, 1 << 20)
                    if not chunk:
                        break
                    view = memoryview(chunk)
                    while view:
                        view = view[os.write(fo, view):]
                os.fchown(fo, ids[0], ids[1])
            finally:
                os.close(fo)
        finally:
            os.close(fi)

    def stage(path, with_key=False):
        src = Path(path)
        if not src.exists() or reachable(src):
            return path             # said by the command itself / its own to open
        if src.is_symlink():
            src = Path(os.path.realpath(str(src)))   # a link of root's own, followed
        # A folder of root's for each file, 0700 while it is filled, the otp
        # account's only once it is (1.0.149): handed over before the copy,
        # a link put in it in between had root write wherever it led.
        d = tempfile.mkdtemp(prefix='.otp-cli-', dir=str(STATE_DIR))
        atexit.register(shutil.rmtree, d, True)
        dst = Path(d) / src.name
        if src.is_dir():
            shutil.copytree(str(src), str(dst), symlinks=False)
            for root, dirs, files in os.walk(str(dst)):
                for n in dirs + files:
                    os.lchown(os.path.join(root, n), ids[0], ids[1])
            os.lchown(str(dst), ids[0], ids[1])
        else:
            copy_in(src, dst)
            if with_key:
                k = _key_beside(src)
                if k is not None and Path(k).is_file():
                    copy_in(k, Path(d) / Path(k).name)
        os.chown(d, ids[0], ids[1])
        return str(dst)
    try:
        if getattr(args, 'restore', None):
            args.restore = stage(args.restore, with_key=True)
        if getattr(args, 'restore_bundle', None):
            args.restore_bundle = stage(args.restore_bundle)
        if getattr(args, 'passphrase_file', None):
            args.passphrase_file = stage(args.passphrase_file)
        if getattr(args, 'backup_info', None):
            args.backup_info = stage(args.backup_info, with_key=True)
        if getattr(args, 'import_config', None):
            args.import_config = stage(args.import_config)
        if getattr(args, 'import_legacy', None):
            args.import_legacy = stage(args.import_legacy)
        if getattr(args, 'import_totpcgi', None):
            args.import_totpcgi = stage(args.import_totpcgi)
        # A package to go back to and a directory's authority (1.0.146): in
        # /root, where the docs put them, the otp account could not read them.
        if getattr(args, 'downgrade', None) and (
                args.downgrade.endswith(('.tar.gz', '.tgz')) or os.path.sep in args.downgrade):
            args.downgrade = stage(args.downgrade)
        if getattr(args, 'ca', None):
            args.ca = stage(args.ca)
        if getattr(args, 'export_config', None) and args.export_config != '-':
            mode = 0o600 if getattr(args, 'with_secrets', False) else 0o640
            fd = os.open(args.export_config, os.O_WRONLY | os.O_CREAT | os.O_TRUNC |
                         os.O_NOFOLLOW, mode)
            os.fchmod(fd, mode)
            args.export_fd = fd
    except OSError as e:
        raise SystemExit('otp: %s' % e)


def cli_store():
    become_service_user()
    load_config(saved=None)
    try:
        db = open_db()
    except DbError as e:
        raise SystemExit('otp: %s' % e)
    store = Storage(db, quick=True)
    load_config(saved=store.settings_saved())
    return store


def bump(store):
    store.set_meta('conf_serial', '%.6f:%s' % (time.time(), node_name()))


def upgrade_percent(st, plan):
    """How far one node is, as the pages draw it."""
    now = time.time()
    since = now - float(st.get('at') or now)
    state = st.get('state')
    if state in ('done', 'failed'):
        return 100
    if state == 'draining':
        return round(3 + 17 * min(1, since / max(1, float(plan.get('drain_s') or 20))))
    if state == 'installing':
        asked = now - float(st.get('asked') or st.get('at') or now)
        return round(min(82, 20 + 60 * min(0.95, float(st.get('part') or 0) / 6)
                         + min(6, asked / 15)))
    if state == 'checking':
        return round(85 + min(10, since / 3))
    return 0


def cli_upgrade_follow(store, pal):
    """An upgrade followed on the terminal: a bar for the whole and one for each
    node, drawn again in place every second, until it ends. Ctrl+C stops the
    following, not the upgrade."""
    tty = sys.stdout.isatty()
    drawn = 0
    last = None
    try:
        while True:
            try:
                plan = upgrade_plan(store)
            except Exception as e:                      # noqa: BLE001 - a node restarting
                plan = last
                if plan is None:
                    raise SystemExit('otp: %s' % e)
            if not plan:
                print('no upgrade going on')
                return 0
            last = plan
            steps = plan.get('steps') or []
            whole = round(sum(upgrade_percent(x, plan) for x in steps) / len(steps)) if steps else 0
            try:
                width = max(20, min(50, shutil.get_terminal_size((100, 24)).columns - 60))
            except Exception:                           # noqa: BLE001
                width = 30

            def bar(pc, bad=False, good=False):
                n = int(round(width * pc / 100.0))
                fill = '█' * n + '░' * (width - n)
                paint = pal.bad if bad else (pal.good if good else pal.info)
                return paint(fill) + ' %3d %%' % pc
            lines = [pal.head(('going back to %s' if plan.get('downgrade') else 'upgrade to %s')
                              % plan.get('version')) + pal.dim(
                '  started by %s · %s' % (plan.get('by') or '?', plan.get('state')))]
            lines.append('  %-16s %s  %d of %d node(s) done' % (
                'all', bar(whole, plan.get('state') == 'failed', plan.get('state') == 'done'),
                sum(1 for x in steps if x.get('state') == 'done'), len(steps)))
            for x in steps:
                pc = upgrade_percent(x, plan)
                words = x.get('said') or x.get('state') or 'waiting'
                if x.get('state') == 'installing' and x.get('part_words'):
                    words = x['part_words']
                lines.append('  %-16s %s  %s' % (x['name'][:16], bar(
                    pc, x.get('state') == 'failed', x.get('state') == 'done'),
                    str(words)[:60]))
            # Past ColourOut (1.0.146): it shows any escape that is not a
            # colour as text - the frame was drawn again below, never over.
            sys.stdout.flush()
            raw = getattr(sys.stdout, 's', sys.stdout)
            if tty and drawn:
                raw.write('\x1b[%dA' % drawn)
            for ln in lines:
                raw.write(('\x1b[2K' if tty else '') + term_safe(ln) + '\n')
            raw.flush()
            drawn = len(lines)
            if plan.get('state') != 'running':
                ok = plan.get('state') == 'done'
                print((pal.ok_line if ok else pal.bad_line)(
                    '%s %s' % ('going back' if plan.get('downgrade') else 'the upgrade',
                               'is done - every node runs %s' % plan.get('version')
                               if ok else 'ended: %s' % plan.get('state'))))
                return 0 if ok else 1
            if not tty:
                drawn = 0
            time.sleep(1 if tty else 5)
    except KeyboardInterrupt:
        print('\n' + pal.dim('no longer followed here - it goes on; otp --upgrade-follow '
                             'follows it again'))
        return 0


def cli_main(argv=None):
    global _LOG_TO_STDERR
    said = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    pal = Palette(colour_wanted(any(x in ('--no-color', '--no-colour') for x in said))
                  and '--json' not in said)
    parser.palette = pal
    global TABLE_PAL
    TABLE_PAL = pal
    args = parser.parse_args(argv)
    # Every line coloured (1.0.132) - not the console's own screen, nor JSON.
    # On a terminal always: what is printed is made safe there (1.0.139).
    if (pal.on or sys.stdout.isatty()) and not args.console and not args.json and \
            not args.daemon and not isinstance(sys.stdout, ColourOut):
        sys.stdout = ColourOut(sys.stdout, pal)
    if args.help:
        sys.stdout.write(parser.format_help())
        return 0
    if args.version:
        print('%s %s%s' % (pal.head('otp'), pal.bold(__version__), '' if HAVE_COLORAMA
                           else pal.dim('  (colorama is not installed; colour is written by '
                                        'hand)')))
        return 0
    global CONFIG_FILE
    if args.config:
        CONFIG_FILE = Path(args.config)
    if args.debug:
        FROM_ARGV['debug'] = True
    # 0 is an answer (1.0.94): --tls-hsts 0 is "none", and 0 == False made it
    # "nothing asked" - the daemon started in the foreground from a script.
    acted = any(v is not None and v is not False and v != [] and v != ''
                for k, v in vars(args).items()
                if k not in ('no_color', 'json', 'debug', 'config', 'limit', 'hours', 'search',
                             'role', 'note', 'yes', 'replace', 'invert', 'pending', 'no_qr',
                             'suffix'))
    if args.daemon:
        return run_daemon()
    if args.dump_copy:
        return cli_dump_copy()
    if not acted and args.json:
        # --json alone (1.0.103): the state as JSON, asked by a script - never
        # the daemon in the foreground because stdin is not a terminal.
        args.status = True
        acted = True
    if not acted:
        # Nothing asked for. Under systemd (or anything else that is not a
        # person at a terminal) that is the daemon, as it always was; typed by
        # somebody, it is the question they meant - what is it doing - and
        # never a second daemon beside the one that is running.
        if os.environ.get('INVOCATION_ID') or not sys.stdin.isatty():
            return run_daemon()
        args.status = True
        acted = True
        if not args.json:
            print(pal.dim('(otp --help for everything it does; the daemon itself is '
                          'systemctl status otp)'))
    _LOG_TO_STDERR = False
    if args.rename_from_opt:
        return rename_from_opt(lambda words: print(pal.ok_line(words)))
    if args.ha_setup or args.ha_join or args.ha_bundle or args.trusted_proxy or args.ha_resync \
            or args.ha_standalone:
        return cli_ha(args, pal)
    # Read as whoever typed it, before the service's account takes over
    # (1.0.47): a certificate in root's folder is not the otp account's to read.
    args.tls_files = []
    for f in args.tls_import or []:
        try:
            args.tls_files.append(Path(f).read_bytes())
        except OSError as e:
            raise SystemExit('otp: %s' % e)
    if args.console_at_login:
        if args.console_at_login != 'status':
            print(pal.ok_line(console_at_login_set(args.console_at_login == 'on')))
        else:
            print(pal.ok_line('the console at login is %s' % ('ON' if console_at_login()
                                                                else 'off')))
        if not CONSOLE_PROFILE.exists():
            print(pal.warn_line('%s is not there - install.sh puts it in' % CONSOLE_PROFILE))
        return 0

    if args.console:
        return console_main(pal)

    cli_stage_files(args)
    store = cli_store()
    if args.ha_compare:
        return cli_ha_compare(store, pal, args.json)
    if args.web_status or args.tls_import or args.tls_preset or args.tls_dh or \
            args.tls_hsts is not None or args.vip_set or args.vip or args.vip_move or args.vip_return or \
            args.web_retry:
        try:
            return cli_web(args, pal, store)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
    if args.ha_tls or args.ha_tls_repair or args.ha_tls_off:
        if args.ha_tls_off:
            if not args.yes:
                raise SystemExit('otp: --ha-tls-off switches off what stops somebody between the '
                                 'nodes from reading and writing the rows going over: add --yes')
            got = hatls_off(store, 'command line', here=False)
            print(pal.warn_line(got['message']))
            print('the daemons of both nodes go through the steps; follow them with  otp --ha-tls')
        if args.ha_tls_repair:
            try:
                got = hatls_start(store, 'command line', here=False)
            except ValueError as e:
                raise SystemExit('otp: %s' % e)
            print(pal.ok_line(got['message']))
            print('the daemons of both nodes go through the steps; follow them with  otp --ha-tls')
        v = hatls_view(store)
        print('the link between the databases: %s%s' % (v['mode'] or 'not encrypted',
                                                       ' (its own setting, ha_tls)' if v['own'] else ''))
        for n in v['nodes']:
            end = n.get('cert_end')
            print('  %-14s %-8s %s%s' % (n['name'], n.get('step') or '?',
                                        (n.get('error') or n.get('said') or '')[:160],
                                        ('  - certificate ends %s' % datetime.fromtimestamp(
                                            float(end)).strftime('%Y-%m-%d')) if end else ''))
        if v['authority_end']:
            print('  the authority ends %s' % datetime.fromtimestamp(
                v['authority_end'][0]).strftime('%Y-%m-%d'))
        return 0
    if args.change_keep or args.change_back:
        kind = args.change_keep or args.change_back
        act = 'keep' if args.change_keep else 'back'
        trials = trials_view(store)
        if kind == 'net':
            node = args.node or (next((x['node'] for x in trials if x['kind'] == 'net'), None)
                                 or node_name())
            try:
                said = net_trial_answer(store, node, act, 'command line')
            except ValueError as e:
                raise SystemExit('otp: %s' % e)
        else:
            try:
                said = fw_trial_answer(store, act, 'command line')
            except ValueError as e:
                raise SystemExit('otp: %s' % e)
        print(pal.ok_line(said))
        return 0

    if args.ha_readdress:
        if not args.ha_address and not args.ha_peer:
            v = readdress_view(store)
            print('this node (%s) is reached at  %s%s' % (node_name(), v['mine'] or '(not set: %s)'
                                                         % v['detected'],
                                                         '' if v['mine_here'] else
                                                         '  - NOT an address of this machine'))
            print('the other node is at          %s' % (v['peer'] or '?'))
            print('this machine has              %s' % (', '.join(v['addresses']) or '?'))
            print('change with  otp --ha-readdress --ha-address NEW  and/or  --ha-peer NEW')
            return 0
        try:
            # pg_hba.conf by the root helper (otp-web.path), as for the pages.
            got = ha_readdress(store, args.ha_address or '', args.ha_peer or '', by='command line')
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        for x in got['done']:
            print(pal.ok_line(x))
        for x in got['left']:
            print(pal.warn_line(x))
        if not got['done'] and not got['left']:
            print(got['message'])
        # The daemon reads config.json again (SIGHUP, as systemctl reload).
        try:
            pid = int((STATE_DIR / 'otp.lock').read_text().strip() or 0)
            if pid > 1:
                os.kill(pid, signal.SIGHUP)
        except (OSError, ValueError):
            print('restart the service so that it reads config.json again:  systemctl '
                  'restart otp')
        return 0 if not got['left'] else 2
    if args.ha_renamed:
        said = node_carry(store, args.ha_renamed.strip(), node_name(), by='command line')
        try:
            NODE_NAME_FILE.write_text(node_name() + '\n')
        except OSError:
            pass
        print(pal.ok_line('%s is now %s; carried over: %s' % (
            args.ha_renamed, node_name(), ', '.join(said) or 'nothing (it had nothing of its own)')))
        return 0
    if args.ha_forget:
        if args.ha_forget == node_name():
            raise SystemExit('otp: that is this node')
        if not store.get_meta('node:' + args.ha_forget):
            raise SystemExit('otp: there is no node called %s in the list' % args.ha_forget)
        ha_forget(store, args.ha_forget)
        store.db.run('DELETE FROM meta WHERE k IN (?, ?)',
                     ('maint:' + args.ha_forget, 'upgrade:node:' + args.ha_forget))
        store.add_event('settings', '%s was taken off the list of nodes on the command line'
                        % args.ha_forget, 'warn', who='command line')
        print(pal.ok_line('%s is off the list (if it still runs, it writes itself back within '
                          'fifteen seconds)' % args.ha_forget))
        return 0
    if args.ha_pause or args.ha_resume or args.ha_stop:
        if args.ha_stop and not args.yes:
            raise SystemExit('otp: this takes replication away; the nodes then go their own '
                             'ways - again with --yes')
        act = 'stop' if args.ha_stop else ('pause' if args.ha_pause else 'resume')
        which = args.ha_pause or args.ha_resume
        if which in ('in', 'out'):
            act += '_' + which
        try:
            print(pal.ok_line(ha_control(store, act)['message']))
        except Exception as e:                          # noqa: BLE001
            raise SystemExit('otp: %s' % str(e).split('\n')[0])
        return 0
    if args.maintenance:
        name = args.node or node_name()
        if args.maintenance == 'status':
            row = maintenance_row(store, name)
            if args.json:
                print(json.dumps(dict(row, node=name), default=str))
            else:
                print(('%s: in maintenance since %s%s' % (
                    name, datetime.fromtimestamp(float(row.get('at') or 0)).strftime(
                        '%d-%m-%Y %H:%M:%S'), (' - ' + row['why']) if row.get('why') else ''))
                      if row.get('on') else '%s: in service' % name)
            return 0 if not row.get('on') else 3
        if args.maintenance == 'on' and not args.node:
            maintenance_ensure(store)
        try:
            maintenance_set(store, args.maintenance == 'on', args.why or 'on the command line',
                            'command line', name)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('%s: %s' % (name, 'in maintenance - RADIUS is not answered and '
                                      '/healthz says 503' if args.maintenance == 'on'
                                      else 'back in service')))
        return 0
    if args.upgrade_cancel:
        try:
            upgrade_cancel(store, 'command line')
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('the upgrade is stopped; the nodes not begun stay as they are'))
        return 0
    if args.upgrade_check:
        row = online_look(store, 'command line')
        if args.json:
            print(json.dumps(row, indent=2, default=str))
            return 0 if not row.get('error') else 1
        print(pal.head('looked at %s' % row.get('url')))
        if row.get('error'):
            print(pal.bad_line(row['error']))
            return 1
        for pk in row.get('packages') or []:
            mark = pal.good('newer') if _ver_tuple(pk['version']) > _ver_tuple(__version__) \
                else pal.dim('not newer')
            print('  %-24s %s  %s' % (pk['name'], mark, pal.dim(pk['url'])))
        n = row.get('newest')
        if not n:
            print(pal.warn_line('no otp package there'))
        elif row.get('newer'):
            print(pal.ok_line('otp %s is there - this server runs %s: otp --upgrade-online'
                              % (n['version'], __version__)))
        else:
            print(pal.ok_line('nothing newer than %s' % __version__))
        return 0

    if args.upgrade_online:
        plan = upgrade_plan(store)
        if plan and plan['state'] == 'running':
            raise SystemExit('otp: an upgrade is going on - otp --upgrade-follow')
        row = online_look(store, 'command line')
        if row.get('error'):
            raise SystemExit('otp: %s: %s' % (row.get('url'), row['error']))
        want = args.upgrade_online
        pk = row.get('newest') if want == 'newest' else next(
            (x for x in row.get('packages') or [] if x['version'] == want), None)
        if not pk:
            raise SystemExit('otp: %s is not at %s' % (want, row.get('url')))
        if _ver_tuple(pk['version']) <= _ver_tuple(__version__):
            print(pal.ok_line('nothing newer than %s at %s' % (__version__, row.get('url'))))
            return 0
        nodes = [n['name'] for n in ha_nodes(store)] or [node_name()]
        print(pal.head('otp %s → %s' % (__version__, pk['version'])) + pal.dim('  from %s'
                                                                            % pk['url']))
        print('  ' + ('the nodes %s, one at a time - each in maintenance while it is upgraded'
                      % ', '.join(nodes) if len(nodes) > 1 else
                      'this server - for a minute nobody can sign in to the VPN'))
        if not args.yes:
            try:
                ok = input('  go on? (y/N) ').strip().lower() in ('y', 'yes', 'a', 'ano')
            except (EOFError, KeyboardInterrupt):
                ok = False
            if not ok:
                print('  nothing done')
                return 1
        print(pal.dim('  fetching it and checking its signature…'))
        try:
            meta = online_fetch(store, pk['version'], 'command line')
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('otp %s fetched, signed by %s' % (meta['version'],
                                                             meta.get('signed_by'))))
        try:
            upgrade_start(store, 'command line')
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        return cli_upgrade_follow(store, pal)

    if args.upgrade_follow:
        return cli_upgrade_follow(store, pal)

    if args.downgrade_check:
        try:
            got = downgrade_list(store)
        except Exception as e:                          # noqa: BLE001
            raise SystemExit('otp: %s' % e)
        if args.json:
            print(json.dumps(got, indent=2, default=str))
            return 0
        print(pal.head('going back from %s - looked at %s' % (__version__, got['url'])))
        print(pal.dim('  it may go back to %s or newer (set by otp %s; this machine allows %s)'
                      % (got['floor'], got['floor_by'], got['root_floor'] or 'nothing yet')))
        if not got['versions']:
            print(pal.ok_line('no version older than %s is there' % __version__))
        for v in got['versions']:
            if v['why']:
                print(pal.bad_line('%-10s %s' % (v['version'], '; '.join(v['why']))))
            else:
                print(pal.ok_line('%-10s may be gone back to: otp --downgrade %s'
                                  % (v['version'], v['version'])))
        return 0

    if args.downgrade:
        plan = upgrade_plan(store)
        if plan and plan['state'] == 'running':
            raise SystemExit('otp: an upgrade is going on - otp --upgrade-follow')
        want = args.downgrade
        is_file = want.endswith(('.tar.gz', '.tgz')) or os.path.sep in want
        if not is_file:
            why = downgrade_why_not(store, want)
            if why:
                raise SystemExit('otp: otp %s cannot be gone back to: %s' % (want, '; '.join(why)))
        nodes = [n['name'] for n in ha_nodes(store)] or [node_name()]
        print(pal.head('otp %s → %s (going back)' % (__version__, os.path.basename(want))))
        print('  ' + ('the nodes %s, one at a time - each in maintenance while it is done'
                      % ', '.join(nodes) if len(nodes) > 1 else
                      'this server - for a minute nobody can sign in to the VPN'))
        print('  ' + pal.dim('the database stays as it is; what came in the newer versions is '
                             'gone until you upgrade again'))
        if not args.yes:
            try:
                ok = input('  go back? (y/N) ').strip().lower() in ('y', 'yes', 'a', 'ano')
            except (EOFError, KeyboardInterrupt):
                ok = False
            if not ok:
                print('  nothing done')
                return 1
        print(pal.dim('  checking it: its signature, how far back this may go, the tables…'))
        try:
            if is_file:
                if not os.path.isfile(want):
                    raise ValueError('%s is not a file' % want)
                meta = downgrade_file(store, want, 'command line')
            else:
                meta = downgrade_fetch(store, want, 'command line')
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('otp %s checked (signed by %s) - the database can take it'
                          % (meta['version'], meta.get('signed_by'))))
        try:
            upgrade_start(store, 'command line')
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        return cli_upgrade_follow(store, pal)

    if args.upgrade_status:
        meta = json.loads(store.get_meta('upgrade:pkg') or 'null')
        plan = upgrade_plan(store)
        if args.json:
            print(json.dumps({'package': meta, 'plan': plan}, indent=2, default=str))
            return 0
        print('package: %s' % ('otp %s (%s bytes, signed by %s, sent by %s)' % (
            meta['version'], meta['bytes'], meta.get('signed_by'), meta.get('by'))
            if meta else 'none sent'))
        if not plan:
            print('no upgrade started on the pages')
            return 0
        print('upgrade to %s, started by %s: %s' % (plan['version'], plan.get('by'),
                                                     plan['state']))
        for st in plan['steps']:
            print('  %-20s %-11s %s' % (st['name'], st.get('state') or 'waiting',
                                        st.get('said') or ''))
        return 0
    if args.ha_status:
        rows = ha_nodes(store)
        if args.json:
            out = lambda data: print(json.dumps(data, indent=2, default=str))
            out({'node': node_name(), 'nodes': rows})
            return 0
        print(pal.head('the cluster') + pal.dim('  (this node: %s, database %s)'
                                              % (node_name(), store.db.where())))
        if not rows:
            print('  ' + pal.dim('no node has written a heartbeat yet - is the daemon running?'))
        for n in rows:
            mark = pal.ok_line if n['alive'] else pal.bad_line
            print(mark('%-16s %-15s %s  heard %s ago%s' % (
                n['name'], n.get('address') or '', n.get('version') or '?',
                human_span(n["age"]), '  (this one)' if n['me'] else '')))
        mine = [n for n in rows if n['me']]
        if mine and mine[0].get('mid') and mine[0]['mid'] != machine_id() and mine[0]['alive']:
            print(pal.bad_line('another machine (%s, %s) writes as %s too: two machines call '
                               'themselves %s - give one its own name (otp --set node_name=NAME '
                               'on it, then systemctl restart otp)' % (
                                   mine[0].get('address') or '?', mine[0].get('host') or '?',
                                   node_name(), node_name())))
        if store.db.engine != 'postgres':
            print(pal.dim('  one node: a cluster needs PostgreSQL - see otp --ha-setup'))
        rep = ha_repl_state(store)
        if rep['mode'] == 'replicated':
            print(pal.head('replication') + pal.dim('  (this node is %d of 2; the other: %s)'
                                                    % (int(rep['slot']), rep['peer'])))
            for r in rep['incoming']:
                # Errors counted so far do not make a running one bad (1.0.47):
                # every time the other node was away is one, for good.
                ok = r['enabled'] and r['running']
                line = 'in  <- %-12s %s, last heard %s%s' % (
                    rep['peer'], 'running' if r['running'] else
                    ('PAUSED' if not r['enabled'] else 'NOT RUNNING'),
                    human_span(time.time() - float(r['last_msg'])) + ' ago' if r.get('last_msg')
                    else 'never', ', %d error(s) counted so far (each time the other was away '
                    'is one)' % r['apply_errors'] if r['apply_errors'] else '')
                print((pal.ok_line if ok else pal.bad_line)(line))
            if not rep['incoming']:
                print(pal.bad_line('in  <- nothing is taken from the other node'))
            for r in rep['outgoing']:
                ok = r['active'] and r['wal_status'] != 'lost'
                print((pal.ok_line if ok else pal.bad_line)(
                    'out -> %-12s %s, %s behind, WAL %s' % (
                        rep['peer'], 'taken' if r['active'] else 'NOT TAKEN (the other is away '
                        'or paused)', bytes_words(r['behind']), r['wal_status'])))
            if not rep['outgoing']:
                print(pal.bad_line('out -> nothing is taken from this node'))
            if rep.get('lost'):
                print(pal.bad_line('the other node was away too long: rebuild it from this one '
                                   '(otp --ha-resync --yes, there)'))
        return 0
    out = lambda data: print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
    who = 'command line'

    if args.status or args.check:
        d = Daemon(store, serve=False)
        s = d.status()
        try:
            import urllib.request
            req = urllib.request.Request('http://127.0.0.1:%d/api/health'
                                         % int(CONFIG.get('api_port') or 9861))
            with urllib.request.urlopen(req, timeout=3) as r:
                alive = json.loads(r.read().decode()).get('ok')
        except Exception:
            alive = False
        listening = []
        for kind, port in (('auth', CONFIG.get('radius_auth_port')),
                           ('acct', CONFIG.get('radius_acct_port'))):
            if not port:
                continue
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                probe.bind((str(CONFIG.get('radius_bind') or '0.0.0.0'), int(port)))
                listening.append((kind, port, False))
            except OSError:
                listening.append((kind, port, True))
            finally:
                probe.close()
        s['daemon_alive'] = alive
        s['ports'] = listening
        if args.json and args.check:
            # --check --json (1.0.103): the checks run as without --json, their
            # lines and their verdict in the JSON - and the same exit code. It
            # printed the state and said 0 whatever was wrong.
            words = [x for x in (sys.argv[1:] if argv is None else list(argv)) if x != '--json']
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cli_main(words + ['--no-color'])
            lines = [re.sub(r'\x1b\[[0-9;]*m', '', x).rstrip() for x in buf.getvalue().split('\n')
                     if x.strip()]
            out(dict(s, check={'ok': not rc, 'exit': rc or 0, 'lines': lines}))
            return rc or 0
        if args.json:
            out(s)
            return 0
        print(pal.head('otp %s on %s' % (__version__, s['host'])))
        print((pal.ok_line if alive else pal.bad_line)(
            'the daemon %s' % ('answers on 127.0.0.1:%s' % CONFIG.get('api_port') if alive
                               else 'is not answering - systemctl status otp')))
        for kind, port, taken in listening:
            print((pal.ok_line if taken else pal.bad_line)(
                'UDP %s (%s) %s' % (port, kind, 'is being listened on' if taken
                                    else 'is free: nothing answers RADIUS there')))
        print(pal.ok_line('the database: %s (%s)' % (store.db.where(), store.db.version())))
        t = s['tokens']
        print('  tokens: %d in use, %d waiting for a code, %d switched off; %d used in the '
              'last 30 days' % (t.get('active', 0), t.get('pending', 0), t.get('disabled', 0),
                                t.get('used_30d', 0)))
        print('  clients %d, realms %d, directories %d' % (s['clients'], s['realms'],
                                                          s['directories']))
        print('  the last 24 h: %s let in, %s refused' % (pal.good(s['day']['accept']),
                                                         pal.bad(s['day']['reject'])))
        if s.get('last'):
            print('  the last request: %s %s %s' % (stamp(s['last']['ts']),
                                                   s['last']['username'], s['last']['result']))
        print('  isemon: %s' % (('sending to %s as "%s"' % (
            CONFIG.get('isemon_targets') or '(nowhere!)', str(CONFIG.get('isemon_hostname')
                                                              or short_host())))
                                if CONFIG.get('isemon') else 'not sent'))
        for p in s['problems']:
            print(pal.bad_line(p))
        for p in trial_problem_words(s.get('trials') or []):
            print(pal.warn_line(p))
        bad = 0
        if args.check:
            print(pal.head('checking every part of it'))
            def said(ok, text, hint=''):
                print((pal.ok_line if ok else pal.bad_line)(text))
                if hint and not ok:
                    print(pal.dim('    ' + hint))
                return 0 if ok else 1
            key = sealing_key_path()
            bad += said(key.is_file(), 'the key of the tokens: %s' % key,
                        'without it no token can be opened - put back the .key beside the '
                        'latest copy in %s' % BACKUP_DIR)
            copies = backups()
            try:                        # the nightly dumps as well (1.0.59)
                copies = sorted(copies + kept_dumps(CONFIG.get('db_engine') or 'sqlite'),
                                key=lambda c: -float(c.get('at') or 0))
            except Exception:                           # noqa: BLE001
                pass
            if copies:
                age = (time.time() - copies[0]['at']) / 3600.0
                bad += said(age < 26 or not CONFIG.get('backup_daily'),
                            'the latest copy of the database: %s, %.0f h ago'
                            % (copies[0]['name'], age), 'otp --backup makes one now')
            else:
                print(pal.dim('  no copy of the database yet (the first is made at %s; '
                              'otp --backup makes one now)' % CONFIG.get('backup_at')))
            ph = php_state()
            if ph.get('version'):
                bad += said(bool(ph.get('fixed')), 'PHP %s %s' % (
                    ph['version'], 'has the php2shell fix' if ph.get('fixed')
                    else 'does NOT have the php2shell fix (CVE-2026-109618/109619)'),
                    './install.sh --upgrade puts it right')
            dirs = {d['name']: d for d in store.directories(with_secret=True)}
            clients = store.clients()
            if not clients:
                bad += said(False, 'no RADIUS client: nothing may ask this server',
                            'Settings -> Clients, or otp --add-client')
            for c in clients:
                print(pal.ok_line('client %s (%s)%s' % (
                    c['name'], c['address'],
                    ', adds @%s' % c['realm'] if c.get('realm') else '')))
            for r in store.realms():
                d = r.get('directory') or ''
                if d and d not in dirs:
                    bad += said(False, 'realm %s asks the directory %s, which is not set up'
                                % (r['name'], d), 'Settings -> Active Directory')
                else:
                    print(pal.ok_line('realm %s: %s, %s' % (
                        r['name'], 'directory ' + d if d else 'no directory - the code alone',
                        {'otp': 'the code', 'password_otp': 'the password then the code',
                         'password': 'the directory password'}.get(r.get('auth_mode'),
                                                                   r.get('auth_mode') or 'the code'))))
            if not dirs:
                print(pal.dim('  no directory to check (Settings -> Active Directory)'))
            for one in dirs.values():
                c = Directory(one).check()
                for srv in c['servers']:
                    line = 'directory %s, %s: %s' % (one['name'], srv['host'], '; '.join(
                        '%s%s' % (st['what'], (' (%s)' % st['said']) if st['said'] else '')
                        for st in srv['steps']))
                    bad += said(srv['ok'], line)
            if CONFIG.get('isemon'):
                targets = syslog_targets(CONFIG.get('isemon_targets') or '')
                bad += said(bool(targets), 'isemon: %s' % (', '.join(
                    '%s:%s/%s' % t[:3] for t in targets) or 'switched on, but sent nowhere'),
                    'Settings -> isemon: where to send them')
        return 0 if alive and not s['problems'] and not bad else 1

    if args.log or args.rejects:
        rows, total = store.radius_rows(hours=args.hours, q=args.search,
                                        result='reject' if args.rejects else 'access',
                                        limit=args.limit)
        if args.json:
            out({'rows': rows, 'total': total})
            return 0
        print(table([(r['id'], stamp(r['ts']), r['username'], r['client'], r['calling'] or '-',
                      pal.good('accept') if r['result'] == 'accept' else pal.bad(r['result']),
                      r['reason'] or r['otp'] or '') for r in rows],
                    ['id', 'when', 'name', 'client', 'from', 'result', 'why'],
                    [6, 19, 28, 14, 16, 16 if pal.on else 7, 60]))
        print(pal.dim('  %d of %d in the last %s h' % (len(rows), total, args.hours)))
        return 0

    if args.request is not None:
        r = store.radius_row(args.request) if 0 <= args.request < 2 ** 62 else None
        if not r:
            raise SystemExit('there is no request %d' % args.request)
        if args.json:
            out(r)
            return 0
        print(pal.head('request %d, %s, from %s (%s)' % (r['id'], stamp(r['ts']), r['client'],
                                                       r['src'])))
        print('  %s: %s %s' % (r['username'], (pal.good if r['result'] == 'accept'
                                               else pal.bad)(r['result']), r['reason'] or ''))
        for st in r['steps']:
            print('  ' + (pal.ok_line if st.get('ok') else pal.bad_line)(
                '%s%s%s' % (st['what'], (' - ' + st['said']) if st.get('said') else '',
                            pal.dim(' (%d ms)' % st['ms']) if 'ms' in st else '')))
        print(pal.dim('  asked:'))
        for k, v in r['attrs']:
            print('    %s = %s' % (k, v))
        print(pal.dim('  answered:'))
        for k, v in r['reply']:
            print('    %s = %s' % (k, v))
        return 0

    if args.otp_log:
        rows, total = store.otp_rows(hours=args.hours, q=args.search, limit=args.limit)
        if args.json:
            out({'rows': rows, 'total': total})
            return 0
        print(table([(stamp(r['ts']), r['name'], pal.good('yes') if r['ok'] else pal.bad('no'),
                      r['said'], r['how'], r['src']) for r in rows],
                    ['when', 'name', 'ok', 'said', 'how', 'from'],
                    [19, 30, 12 if pal.on else 3, 40, 8, 20]))
        return 0

    if args.tokens:
        rows, total = store.tokens(q=args.search, limit=args.limit if any(
            x == '--limit' or x.startswith('--limit=') for x in sys.argv) else 1000)
        if args.json:
            out({'rows': rows, 'total': total})
            return 0
        print(table([(r['name'], r['state'], stamp(r['created']), stamp(r['last_used'])
                      if r['last_used'] else 'never', r['scratch_left'], r['failures'] or 0,
                      r['created_by'] or '') for r in rows],
                    ['name', 'state', 'made', 'last used', 'codes', 'wrong', 'by'],
                    [34, 9, 19, 19, 5, 5, 22]))
        print(pal.dim('  %d token(s)' % total))
        return 0

    if args.token:
        tok = store.token_shown(store.token(args.token))
        checks, _ = store.otp_rows(hours=24 * 365, name=norm_name(args.token), limit=args.limit)
        if args.json:
            out({'token': tok, 'checks': checks})
            return 0
        if not tok:
            print(pal.bad_line('%s has no token' % norm_name(args.token)))
            return 1
        for k in ('name', 'state', 'created', 'created_by', 'activated', 'last_used',
                  'last_from', 'scratch_left', 'failures', 'digits', 'period', 'algorithm',
                  'window_steps', 'note'):
            v = tok.get(k)
            if k in ('created', 'activated', 'last_used'):
                v = stamp(v) if v else 'never'
            print('  %-14s %s' % (k, v if v not in (None, '') else '-'))
        print(table([(stamp(r['ts']), pal.good('yes') if r['ok'] else pal.bad('no'), r['said'],
                      r['how']) for r in checks], ['when', 'ok', 'said', 'how'],
                    [19, 12 if pal.on else 3, 44, 8]))
        return 0

    if args.events:
        rows, total = store.events(args.limit, 0, args.search)
        if args.json:
            out({'rows': rows, 'total': total})
            return 0
        print(table([(stamp(r['ts']), r['kind'], r['who'] or '', r['words']) for r in rows],
                    ['when', 'kind', 'who', 'what'], [19, 22, 18, 90]))
        return 0

    tk = Tokens(store)
    if args.enroll:
        had = store.token(args.enroll)
        if had and had.get('state') != 'pending':
            # Not silently (1.0.59): the token in use stops working now.
            cli_sure(args, 'the token of %s in use is replaced, and stops working now'
                     % norm_name(args.enroll))
        if args.by in ('mail', 'sms'):
            # Codes sent by mail or SMS (1.0.76).
            try:
                got = tk.enroll_sent(args.enroll, 'cli', args.by, args.to or '',
                                     note=args.note or None)
            except ValueError as e:
                raise SystemExit(str(e))
            store.add_event('tokens', 'a token for %s was made on the command line: codes by %s '
                            'to %s' % (got['name'], args.by, got['dest']), who=who)
            if args.json:
                out(got)
                return 0
            print(pal.head('a token for %s - codes by %s to %s' % (
                got['name'], 'mail' if args.by == 'mail' else 'SMS', got['dest'])))
            if got['scratch']:
                print('  recovery codes, each good once:  %s' % '  '.join(got['scratch']))
            return 0
        got = tk.enroll(args.enroll, 'cli', pending=args.pending, note=args.note or None)
        store.add_event('tokens', 'a token for %s was made on the command line'
                        % got['name'], who=who)
        if args.json:
            out(got)
            return 0
        print(pal.head('a token for %s%s' % (got['name'], ' - waiting for a code (otp '
                                                         '--confirm NAME CODE)' if args.pending
                                             else '')))
        if not args.no_qr:
            print(QrCode(got['uri']).terminal(invert=args.invert))
        print('  key:      %s' % got['secret_spaced'])
        print('  in full:  %s' % got['uri'])
        if got['scratch']:
            print('  recovery codes, each good once:  %s' % '  '.join(got['scratch']))
        return 0

    if args.confirm:
        ok, said = tk.confirm(args.confirm[0], args.confirm[1], 'cli')
        print((pal.ok_line if ok else pal.bad_line)(said))
        return 0 if ok else 1

    if args.verify:
        ok, said, facts = tk.check(args.verify[0], args.verify[1], how='cli', dry=True)
        if args.json:
            out({'ok': ok, 'said': said, 'facts': facts})
        else:
            print((pal.ok_line if ok else pal.bad_line)('%s%s' % (said, (
                ' (%+d step)' % facts['off']) if facts.get('off') else '')))
        return 0 if ok else 1

    for flag, state in (('disable_token', 'disabled'), ('enable_token', 'active')):
        name = getattr(args, flag)
        if name:
            if not store.token(name):
                raise SystemExit('%s has no token' % norm_name(name))
            if state == 'active' and (store.token(name) or {}).get('state') != 'disabled':
                print(pal.ok_line('the token of %s is not switched off' % norm_name(name)))
                return 0
            state = token_switch_state(store, name, state == 'active')     # 1.0.59
            store.token_write(name, {'state': state, 'failures': 0, 'fail_times': '[]',
                                     'locked_until': None})
            store.add_event('tokens', 'the token of %s was switched %s on the command line'
                            % (norm_name(name), 'off' if state == 'disabled' else 'on'), who=who)
            print(pal.ok_line('the token of %s is %s' % (norm_name(name), state)))
            return 0

    if args.delete_token:
        if not store.token(args.delete_token):
            raise SystemExit('%s has no token' % norm_name(args.delete_token))
        cli_sure(args, 'the token of %s is taken away for good' % norm_name(args.delete_token))
        store.token_drop(args.delete_token)
        # What was kept beside it goes too, as on the pages (1.0.44).
        for k in ('staged:', 'mailed:', 'disabled_from:'):
            store.db.run('DELETE FROM meta WHERE k = ?', (k + norm_name(args.delete_token),))
        store.add_event('tokens', 'the token of %s was taken away on the command line'
                        % norm_name(args.delete_token), 'warn', who=who)
        print(pal.ok_line('gone'))
        return 0

    if args.scratch:
        if not store.token(args.scratch):
            raise SystemExit('otp: %s has no token' % norm_name(args.scratch))
        codes = tk.new_scratch(args.scratch)
        store.add_event('tokens', 'new recovery codes for %s were made on the command line'
                        % norm_name(args.scratch), 'warn', who=who)
        print('  ' + '  '.join(codes))
        return 0

    if args.unlock:
        if not store.token(norm_name(args.unlock)):
            raise SystemExit('no token %s' % norm_name(args.unlock))
        store.token_write(norm_name(args.unlock), {'failures': 0, 'fail_times': '[]', 'locked_until': None})
        # Its recovery codes given back too, as on the pages (1.0.103).
        node_key_drop(store, 'scratchguard', args.unlock)
        scratch_guard_clear(args.unlock)
        store.add_event('tokens', 'the command line let %s try again at once'
                        % norm_name(args.unlock), who='command line')
        print(pal.ok_line('the wrong codes of %s are forgotten' % norm_name(args.unlock)))
        return 0

    if args.import_totpcgi:
        if not Path(args.import_totpcgi).is_dir():
            raise SystemExit('otp: %s is not a folder of .totp files' % args.import_totpcgi)
        n = collections.Counter()
        for f in sorted(Path(args.import_totpcgi).glob('*.totp')):
            try:
                said = import_totp(store, totp_file_owner(f.name), f.read_text(errors='replace'),
                                   'import',
                                   args.replace)
            except ValueError as e:
                said = 'not imported: %s' % e
            n[said.split(' ')[0]] += 1
            print('  %-40s %s' % (norm_name(f.name[:-5]), said))
        store.add_event('import', 'totpcgi files imported from %s: %s' % (
            args.import_totpcgi, dict(n)), who=who)
        args.fill_names = True

    if args.import_legacy:
        got = import_legacy(store, args.import_legacy, 'import', args.replace,
                            say=lambda t: print('  ' + t))
        bump(store)
        print(pal.ok_line('brought over: %s' % ', '.join('%s %d' % kv for kv in
                                                         sorted(got.items()))))
        args.fill_names = True

    if args.fill_names:
        print(pal.dim('  the owners\' names, from the directory of each token\'s realm...'))
        got = Daemon(store, serve=False).fill_names(by='command line')
        print(pal.ok_line('%d token(s) given their owner\'s name; %d not found, %d with no '
                          'directory to ask, %d could not be asked'
                          % (got['filled'], got['not_found'], got['no_directory'],
                             got['trouble'])))
        return 0

    if args.radtest:
        a = args.radtest
        if len(a) < 2:
            raise SystemExit('otp --radtest USER CODE [SERVER [PORT [SECRET]]]')
        user, code = a[0], a[1]
        if code == '-':
            # Not on the command line, where `ps` shows it (1.0.136).
            code = os.environ.get('OTP_RADTEST_PASSWORD') or getpass.getpass('password + code: ')
        server = a[2] if len(a) > 2 else '127.0.0.1'
        try:
            port = int(a[3]) if len(a) > 3 else int(CONFIG.get('radius_auth_port') or 1812)
        except ValueError:
            raise SystemExit('otp --radtest: the port is a number')
        secret = a[4] if len(a) > 4 else None
        if secret == '-':
            # As --secret - (1.0.139): not on the command line, where ps shows it.
            secret = ask_password('the shared secret', twice=False, env='OTP_SECRET')
        if secret is None:
            local = store.client_for('127.0.0.1')
            if not local:
                raise SystemExit('there is no client for 127.0.0.1: give the secret as the '
                                 'fifth word')
            secret = local['_secret']
        print(pal.dim('Sent Access-Request to %s:%d, User-Name = "%s", User-Password = "******"'
                      % (server, port, user)))
        try:
            got, words, took = radius_ask(server, port, secret, user, code)
        except RadiusError as e:
            print(pal.bad_line(str(e)))
            return 2
        print(((pal.good if got == ACCESS_ACCEPT else pal.bad)('Received %s' % CODE_WORDS.get(
            got, got))) + pal.dim(' in %d ms' % took))
        for k, v in words:
            if k != 'Message-Authenticator':
                print('    %s = %s' % (k, v))
        # The second window (1.0.81): the code asked for, and the request
        # again with the State - as the VPN client does. Up to three times,
        # as the server lets.
        rounds = 0
        while got == ACCESS_CHALLENGE and rounds < 5:
            rounds += 1
            state = next((v for k, v in words if k == 'State'), '')
            said = next((v for k, v in words if k == 'Reply-Message'), '')
            try:
                answer = input('%s: ' % (said or 'The code')).strip()
            except EOFError:
                answer = ''
            if not answer:
                print(pal.dim('  no code typed - stopped'))
                return 1
            print(pal.dim('Sent Access-Request with the State, User-Password = "******"'))
            try:
                got, words, took = radius_ask(server, port, secret, user, answer,
                                              extra=[('State', state)])
            except RadiusError as e:
                print(pal.bad_line(str(e)))
                return 2
            print(((pal.good if got == ACCESS_ACCEPT else pal.bad)('Received %s' % CODE_WORDS.get(
                got, got))) + pal.dim(' in %d ms' % took))
            for k, v in words:
                if k != 'Message-Authenticator':
                    print('    %s = %s' % (k, v))
        row = store.db.row('SELECT id FROM radius_log ORDER BY id DESC LIMIT 1')
        if row and server in ('127.0.0.1', 'localhost', '::1'):
            print(pal.dim('  every step of it: otp --request %d' % row['id']))
        return 0 if got == ACCESS_ACCEPT else 1

    if args.clients:
        rows = store.clients()
        if args.json:
            out(rows)
            return 0
        print(table([(c['name'], c['address'], c['realm'] or '-', 'yes' if c['require_ma']
                      else 'no', 'on' if c['enabled'] else 'off', stamp(c['last_seen'])
                      if c['last_seen'] else 'never') for c in rows],
                    ['name', 'address', 'realm added', 'needs MA', 'state', 'last asked']))
        return 0

    if args.add_client:
        old = next((c for c in store.clients() if c['name'].lower() == args.add_client.lower()),
                   None)
        data = {'id': old['id'] if old else None, 'name': args.add_client,
                'address': args.address or (old or {}).get('address'),
                'secret': ask_password('the shared secret', env='OTP_SECRET')
                if args.secret == '-' else args.secret if args.secret is not None else (
                    None if old else ask_password('the shared secret', env='OTP_SECRET')),
                'realm': args.realm if args.realm is not None else (old or {}).get('realm', ''),
                # A client switched off stays off when it is changed (1.0.136).
                'require_ma': (old or {}).get('require_ma', 0),
                'enabled': (old or {}).get('enabled', 1),
                'nas_type': (old or {}).get('nas_type', ''),
                'position': (old or {}).get('position'),
                'note': args.note or (old or {}).get('note', '')}
        store.client_save(data, who)
        bump(store)
        store.add_event('clients', 'the client %s was saved on the command line'
                        % args.add_client, who=who)
        print(pal.ok_line('the client %s is saved' % args.add_client))
        return 0

    if args.del_client:
        one = next((c for c in store.clients() if c['name'].lower() == args.del_client.lower()),
                   None)
        if not one:
            raise SystemExit('there is no client called %s' % args.del_client)
        store.client_drop(one['id'])
        store.add_event('clients', 'command line took away the client %s' % one['name'],
                        who='command line')
        bump(store)
        print(pal.ok_line('gone'))
        return 0

    if args.realms:
        rows = store.realms()
        if args.json:
            out(rows)
            return 0
        print(table([(r['name'], (r['suffix'] or '(none)') + ''.join(
                          ' +' + a for a in r.get('aliases') or []), r['auth_mode'],
                      r['directory'] or '-',
                      r['lookup'], '; '.join(g['group'] for g in r['groups']) or '(anybody)')
                     for r in rows], ['name', 'takes @', 'password is', 'directory', 'lookup',
                                      'groups'], [16, 16, 13, 12, 6, 70]))
        return 0

    if args.add_realm:
        old = next((r for r in store.realms() if r['name'].lower() == args.add_realm.lower()),
                   None) or {}
        groups = old.get('groups') or []
        if args.groups is not None:
            groups = [{'group': g, 'reply': ''} for g in dn_list(args.groups)]
        store.realm_save({'id': old.get('id'), 'name': args.add_realm,
                          'suffix': args.suffix if args.suffix is not None else old.get(
                              'suffix', args.add_realm),
                          'directory': args.directory if args.directory is not None
                          else old.get('directory', ''),
                          'lookup': args.lookup or old.get('lookup') or 'upn',
                          'auth_mode': args.mode or old.get('auth_mode') or 'otp',
                          'groups': groups, 'check_disabled': old.get('check_disabled', 1),
                          'nested': old.get('nested', 1), 'reply': old.get('reply', ''),
                          # As it was (1.0.146): a realm switched off on the pages
                          # was switched on again by a note given here.
                          'enabled': old.get('enabled', 1), 'position': old.get('position'),
                          'token_name': old.get('token_name', 'whole'),
                          'methods': [m.strip() for m in args.methods.split(',')]
                          if args.methods else old.get('methods'),
                          'aliases': args.aliases if args.aliases is not None
                          else old.get('aliases') or [],
                          'note': args.note or old.get('note', '')}, who)
        store.add_event('realms', 'command line saved the realm %s' % args.add_realm,
                        who='command line')
        bump(store)
        print(pal.ok_line('the realm %s is saved' % args.add_realm))
        return 0

    if args.del_realm:
        one = next((r for r in store.realms() if r['name'].lower() == args.del_realm.lower()),
                   None)
        if not one:
            raise SystemExit('there is no realm called %s' % args.del_realm)
        try:
            store.realm_drop(one['id'])
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        store.add_event('realms', 'command line took away the realm %s' % one['name'],
                        who='command line')
        bump(store)
        print(pal.ok_line('gone'))
        return 0

    if args.directories:
        rows = store.directories()
        if args.json:
            out(rows)
            return 0
        print(table([(d['name'], d['hosts'], '%s/%s' % (d['tls'], d['port']), d['base'],
                      d['bind_dn'], 'checked' if d['verify'] else 'NOT checked')
                     for d in rows], ['name', 'servers', 'how', 'base', 'reads as',
                                      'certificate']))
        return 0

    if args.add_directory:
        old = store.directory(args.add_directory) or {}
        ca = None
        if args.ca:
            ca = Path(args.ca).read_text()
        pw = args.bind_pw if args.bind_pw is not None else os.environ.get('OTP_BIND_PW')
        if pw == '-':
            pw = ask_password('the password of %s' % (args.bind_dn or 'the binding account'),
                              twice=False, env='OTP_BIND_PW')
        data = {'id': old.get('id'), 'name': args.add_directory,
                'hosts': args.hosts or old.get('hosts'), 'base': args.base or old.get('base'),
                'bind_dn': args.bind_dn if args.bind_dn is not None else old.get('bind_dn', ''),
                'bind_pw': pw if pw is not None else (None if old else ''),
                'tls': args.tls or old.get('tls') or 'ldaps',
                'port': args.port or (old.get('port') if not args.tls else None),
                'verify': 0 if args.no_verify else old.get('verify', 1),
                'weak': (args.weak_certs == 'on') if args.weak_certs else old.get('weak', 0),
                'nested': old.get('nested', 1), 'enabled': old.get('enabled', 1),
                'timeout_s': old.get('timeout_s') or 10,
                'user_attr': old.get('user_attr') or 'sAMAccountName',
                'note': args.note or old.get('note', '')}
        if ca is not None:
            data['ca'] = ca
        store.directory_save(data, who)
        store.add_event('directories', 'command line saved the directory %s'
                        % args.add_directory, who='command line')
        bump(store)
        print(pal.ok_line('the directory %s is saved' % args.add_directory))
        return 0

    if args.del_directory:
        one = store.directory(args.del_directory)
        if not one:
            raise SystemExit('there is no directory called %s' % args.del_directory)
        try:
            store.directory_drop(one['id'])
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        store.add_event('directories', 'command line took away the directory %s' % one['name'],
                        who='command line')
        bump(store)
        print(pal.ok_line('gone'))
        return 0

    if args.directory_test or args.directory_user:
        name = args.directory_test or args.directory_user[0]
        one = store.directory(name, with_secret=True)
        if not one:
            raise SystemExit('there is no directory called %s' % name)
        ad = Directory(one)
        if args.directory_test:
            c = ad.check()
            if args.json:
                out(c)
                return 0
            for srv in c['servers']:
                print(pal.bold('  %s:%d' % (srv['host'], srv['port'])))
                for st in srv['steps']:
                    print('    ' + (pal.ok_line if st['ok'] else pal.bad_line)(
                        st['what'] + ((' - ' + st['said']) if st['said'] else '')))
            return 0 if c['ok'] else 1
        user = args.directory_user[1]
        entry = ad.find_user(user, 'upn' if '@' in user else 'sam')
        if not entry:
            print(pal.bad_line('the directory has nobody called %s' % user))
            return 1
        groups = ad.groups_of(entry, True)
        if args.json:
            out({'entry': entry, 'groups': groups})
            return 0
        for k in ('dn', 'upn', 'sam', 'display', 'mail', 'disabled', 'expires'):
            print('  %-10s %s' % (k, entry.get(k)))
        print('  groups:   %s' % ', '.join(sorted(cn for _, cn in groups)))
        return 0

    if args.settings:
        d = Daemon(store, serve=False)
        rows = d.settings_state(True)
        if args.json:
            out(rows)
            return 0
        for s in rows:
            print('  %-28s %-34s %s' % (s['key'], json.dumps(s['value'], ensure_ascii=False)[:34],
                                       pal.dim(s['source_says'])))
        return 0

    if args.export_config:
        conf = config_export(store, bool(args.with_secrets))
        text = json.dumps({'config': conf}, indent=1, ensure_ascii=False, default=str)
        if args.export_config == '-':
            print(text)
        else:
            fd = getattr(args, 'export_fd', None)
            if fd is None:
                fd = os.open(args.export_config, os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                             0o600 if args.with_secrets else 0o640)
            # The mode of a file there already too (1.0.94): O_CREAT's mode is
            # only a new file's, and secrets went into a 0644 one.
            os.fchmod(fd, 0o600 if args.with_secrets else 0o640)
            with os.fdopen(fd, 'w') as f:
                f.write(text + '\n')
            print(pal.ok_line('%s: the configuration%s' % (
                args.export_config, ', with its secrets in the clear - keep it safe'
                if args.with_secrets else ' (without the secrets)')))
        if args.with_secrets:
            store.add_event('settings', 'the configuration was exported with the secrets in it, '
                            'on the command line', 'warn', who=who)
        return 0

    if args.import_config:
        try:
            raw = json.loads(Path(args.import_config).read_text())
        except (OSError, ValueError) as e:
            raise SystemExit('otp: %s' % e)
        if isinstance(raw, dict) and raw.get('kind') == CONFIG_BUNDLE_KIND:
            # Exported from the pages with the secrets: locked (1.0.136).
            try:
                if args.passphrase_file:
                    phrase = Path(args.passphrase_file).read_text().strip()
                else:
                    phrase = os.environ.get('OTP_PASSPHRASE') or getpass.getpass(
                        'the passphrase it was exported with: ')
                raw = bundle_open(raw, phrase, kinds=(CONFIG_BUNDLE_KIND,))
            except (OSError, ValueError) as e:
                raise SystemExit('otp: %s' % e)
        conf = raw.get('config', raw) if isinstance(raw, dict) else raw
        if not args.yes:
            raise SystemExit('this puts the configuration of %s in here, over what is set up; '
                             'again with --yes' % args.import_config)
        d = Daemon(store, serve=False)
        try:
            said = config_import(store, d, conf, who, replace=bool(args.replace))
        except ApiError as e:
            raise SystemExit('otp: %s' % e)
        except (ValueError, BadSetting) as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('imported: %s' % ', '.join('%s %d' % kv for kv in sorted(said.items()))))
        return 0

    if args.set:
        d = Daemon(store, serve=False)
        want = {}
        for one in args.set:
            if '=' not in one:
                raise SystemExit('--set takes KEY=VALUE')
            k, v = one.split('=', 1)
            if v == '@env':
                # A secret not on the command line (1.0.136): from
                # OTP_VALUE_<KEY>, as the console passes it.
                if ('OTP_VALUE_' + k.strip().upper()) not in os.environ:
                    raise SystemExit('otp: %s=@env, and OTP_VALUE_%s is not set - nothing saved'
                                     % (k.strip(), k.strip().upper()))
                v = os.environ['OTP_VALUE_' + k.strip().upper()]
            want[k.strip()] = v
        # As the pages refuse them (1.0.136): the cluster has its own steps,
        # and a database named here opens empty at the next restart.
        def differs(k):
            return str(want[k]) != str(CONFIG.get(k) if CONFIG.get(k) is not None else '')
        ha = [k for k in want if k in ('ha_mode', 'ha_slot', 'ha_peer', 'ha_peer_port',
                                       'ha_address', 'ha_tls', 'ha_tls_ca') and differs(k)]
        if ha:
            raise SystemExit('otp: the cluster is changed with otp --ha-setup / --ha-join / '
                             '--ha-standalone (or on Settings - High availability); %s not saved'
                             % ', '.join(ha))
        moved = [k for k in want if k in ('db_engine', 'db_host', 'db_port', 'db_name',
                                          'db_user', 'db_password') and differs(k)]
        if moved and not args.yes:
            raise SystemExit('otp: %s names another database: at the next restart otp opens '
                             'it as it is - nothing is carried into it (Settings - The database '
                             'does that). Only to point at the same data somewhere new (a moved '
                             'server, a new password): again with --yes' % ', '.join(moved))
        try:
            said = d.save_settings(want, by=who)
        except (BadSetting, OSError) as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line(said['message']))
        return 0

    if args.admin_2fa:
        if args.admin_2fa != 'status':
            d = Daemon(store, serve=False)
            try:
                d.save_settings({'admin_2fa': '1' if args.admin_2fa == 'on' else '0'}, by=who)
            except (BadSetting, OSError) as e:
                raise SystemExit('otp: %s' % e)
            CONFIG['admin_2fa'] = 1 if args.admin_2fa == 'on' else 0
        on = bool(CONFIG.get('admin_2fa'))
        mfa = mfa_all(store)
        rows = store.accounts()
        have = [a['name'] for a in rows if str(a['name']).lower() in mfa]
        if args.json:
            out({'admin_2fa': on, 'ways': mfa_methods(), 'set_up': have,
                 'not_yet': [a['name'] for a in rows if a['name'] not in have]})
            return 0
        print(pal.ok_line('the second step of signing in to these pages is %s%s' % (
            'ON' if on else 'off', (' - offered: %s' % ', '.join(mfa_methods())) if on else '')))
        print('set up: %s' % (', '.join('%s (%s)' % (n, mfa[n.lower()]['kind']) for n in have)
                              or 'nobody'))
        left = [a['name'] for a in rows if a['name'] not in have and not a['disabled']]
        if on and left:
            print('set up at their next sign-in: %s' % ', '.join(left))
        if args.admin_2fa != 'status':
            print('the running service takes it within seconds; sign-ins already open stay open')
        return 0

    if args.users:
        rows = store.accounts()
        mfa = mfa_all(store)
        for a in rows:
            a['mfa'] = mfa.get(str(a['name']).lower())
        if args.json:
            out({'users': rows, 'mfa_on': bool(CONFIG.get('admin_2fa'))})
            return 0
        print(table([(a['name'], ROLE_WORDS.get(a['role'], a['role']), a['source'] or 'local',
                      'off' if a['disabled'] else 'on',
                      ('%s %s' % (a['mfa']['kind'], a['mfa'].get('dest') or '')).strip()
                      if a['mfa'] else '-', stamp(a['last_in']) if a['last_in']
                      else 'never', a['note'] or '') for a in rows],
                    ['name', 'role', 'from', 'state', 'second step', 'last signed in', 'note']))
        if CONFIG.get('admin_2fa'):
            print('the second step is asked for (admin_2fa); otp --reset-2fa NAME takes one away')
        return 0

    if args.add_user:
        pw = ask_password('a password for %s' % args.add_user)
        try:
            store.add_account(args.add_user, args.role or 'readonly', pw, note=args.note)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        store.add_event('accounts', 'the account %s was made on the command line, as %s'
                        % (args.add_user, args.role or 'readonly'), who=who)
        print(pal.ok_line('%s may now sign in, as %s' % (args.add_user, args.role or 'readonly')))
        return 0

    if args.passwd:
        pw = ask_password('a new password for %s' % args.passwd)
        try:
            store.set_account(args.passwd, password=pw, must_change=0)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        # As the pages do (1.0.44): a new password ends the old sign-ins.
        store.db.run('DELETE FROM sessions WHERE kind = ? AND LOWER(name) = ?',
                     ('admin', args.passwd.lower()))
        store.add_event('accounts', 'the password of %s was set on the command line'
                        % args.passwd, who=who)
        print(pal.ok_line('the password of %s is set' % args.passwd))
        return 0

    if args.reset_2fa:
        acc = store.account(args.reset_2fa)
        if not acc:
            raise SystemExit('otp: there is no account called %s' % args.reset_2fa)
        had = mfa_reset(store, acc['name'], who)
        store.db.run('DELETE FROM sessions WHERE kind = ? AND LOWER(name) = ?',
                     ('admin', acc['name'].lower()))
        print(pal.ok_line('the second step of %s is reset - set up again at the next sign-in'
                          % acc['name']) if had else
              pal.ok_line('%s had no second step set up' % acc['name']))
        return 0

    for flag in ('set_role', 'del_user', 'disable_user', 'enable_user'):
        name = getattr(args, flag)
        if not name:
            continue
        try:
            acc = store.account(name)
            if not acc:
                raise ValueError('there is no account called %s' % name)
            if flag == 'set_role' and not args.role:
                raise ValueError('which role? --set-role %s --role %s' % (name, '|'.join(ROLES_ALL)))
            if (flag in ('del_user', 'disable_user') or (flag == 'set_role' and args.role != 'fulladmin')) \
                    and acc.get('role') == 'fulladmin' and not store.fulladmins_left(but=name):
                raise ValueError('that is the last full administrator who can sign in')
            if flag == 'set_role':
                store.set_account(name, role=args.role)
            elif flag == 'del_user':
                store.drop_account(name)
            else:
                store.set_account(name, disabled=1 if flag == 'disable_user' else 0)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        store.add_event('accounts', '%s: %s on the command line' % (name, flag.replace('_', ' ')),
                        who=who)
        print(pal.ok_line('done'))
        return 0

    if args.backup:
        got = make_backup(store, 'on the command line')
        print(pal.ok_line('%s, and the key beside it' % got))
        return 0

    if args.backup_info or (args.restore and not args.yes):
        # What a copy holds and where it was made (1.0.63), before anything
        # is put back.
        f = args.backup_info or args.restore
        if not Path(f).is_file():
            raise SystemExit('otp: there is no file %s' % f)
        said, why = db_file_peek(f, store.db.engine, need_admin=False)
        if said is None:
            raise SystemExit('otp: %s' % why)
        if args.json:
            out(said)
        else:
            m = said.get('machine') or {}
            use = m.get('in_use') or {}
            print(pal.head('%s - %s' % (f, DUMP_WORDS.get(said['kind'], said['kind']))))
            if said.get('version'):
                print('  made by otp %s%s' % (said['version'], ', ' + stamp(said['made'])
                                              if said.get('made') else ''))
            for k, v in sorted((said.get('counts') or {}).items()):
                print('  %-12s %s' % (k, v))
            if m:
                print('  made on      %s (%s)' % (m.get('node') or '?', m.get('host') or '?'))
                print('  database     %s %s' % (use.get('db_engine') or '?', '' if use.get(
                    'db_engine') == 'sqlite' else '%s:%s/%s' % (use.get('db_host'), use.get(
                        'db_port'), use.get('db_name'))))
                if use.get('ha_mode'):
                    print('  cluster      %s, slot %s, the other node %s' % (
                        use['ha_mode'], use.get('ha_slot'), use.get('ha_peer')))
                print('  its %s (only to read - it is never put back):' % m.get('config_file'))
                for line in json.dumps(m.get('config') or {}, indent=1).split('\n'):
                    print('    ' + line)
            elif said['kind'] == 'copy':
                print(pal.dim('  (made before 1.0.63: where it was made is not in it)'))
        if args.restore:
            raise SystemExit('this replaces everything in %s with the copy; again with --yes'
                             % store.db.where())
        return 0

    if args.rbackup_status:
        v = rb_page(store)
        print('backups to the destinations: %s%s; %s' % (
            'on a schedule, next %s' % v['next'] if CONFIG.get('rbackup') else 'by hand only',
            '', 'locked with the password' if v['locked'] else 'NOT LOCKED (no password set)'))
        for t in v['targets']:
            last = t.get('last') or {}
            print('  %-24s %-6s %-3s %s' % (t['name'][:24], t['kind'], 'on' if t.get('enabled')
                                             else 'off', ('last %s: %s' % (
                datetime.fromtimestamp(last['at']).strftime('%Y-%m-%d %H:%M'),
                'sent' if last.get('ok') else last.get('error'))) if last else 'never sent'))
        for r in v['runs'][:10]:
            print('  %s  %-10s %-9s %s' % (datetime.fromtimestamp(r['at']).strftime(
                '%Y-%m-%d %H:%M'), r.get('node'), human_bytes(r.get('bytes') or 0),
                '; '.join('%s %s' % (x['name'], 'ok' if x['ok'] else 'FAILED: %s' % x.get('error'))
                          for x in r.get('targets') or []) or r.get('error') or ''))
        return 0

    if args.rbackup_now:
        try:
            run = rb_run(store, 'command line')
        except (RbError, ValueError) as e:
            raise SystemExit('otp: %s' % e)
        if run.get('error'):
            raise SystemExit('otp: %s' % run['error'])
        print(pal.ok_line('%s (%s, %s)' % (run.get('file'), human_bytes(run.get('bytes') or 0),
                                           'locked' if run.get('encrypted') else 'NOT locked')))
        for x in run['targets']:
            print((pal.ok_line if x['ok'] else pal.bad_line)('%s: %s' % (
                x['name'], 'sent' + (' - taken away: %s' % ', '.join(x['taken_away'])
                                     if x.get('taken_away') else '') if x['ok'] else x.get('error'))))
        return 0 if run['ok'] else 2

    if args.restore_bundle:
        path = args.restore_bundle
        if not Path(path).is_file():
            raise SystemExit('otp: there is no file %s' % path)
        password = os.environ.get('OTP_BACKUP_PASSWORD', '')
        if args.passphrase_file:
            try:
                password = Path(args.passphrase_file).read_text().split('\n')[0]
            except OSError as e:
                raise SystemExit('otp: %s' % e)
        with open(path, 'rb') as f:
            locked = f.read(8).startswith(b'Salted__')
        if locked and not password:
            password = rb_password()
            if not password:
                if not sys.stdin.isatty():
                    raise SystemExit('otp: the backup is locked: --passphrase-file FILE, or '
                                     'OTP_BACKUP_PASSWORD')
                password = getpass.getpass('the password of the backups: ')
        if not args.yes:
            work = tempfile.mkdtemp(prefix='otp-peek-', dir=str(STATE_DIR))
            try:
                _top, m = rb_open(path, password, work)
            except RbError as e:
                raise SystemExit('otp: %s' % e)
            finally:
                shutil.rmtree(work, ignore_errors=True)
            print('%s - every file checked against its checksum' % os.path.basename(path))
            for k, words in (('made_words', 'made'), ('site', 'installation'), ('node', 'node'),
                             ('host', 'machine'), ('otp', 'otp'), ('engine_words', 'database'),
                             ('ha_mode', 'cluster'), ('tokens', 'tokens')):
                print('  %-13s %s' % (words, m.get(k) if m.get(k) not in (None, '') else '-'))
            print('it would replace everything in %s, put its key of the tokens in place%s; '
                  'again with --yes' % (store.db.where(), '' if args.keep_node_name else
                                        ' and make this machine node %s' % m.get('node')))
            return 0
        try:
            got = rb_restore(store, path, password, 'command line',
                             keep_node_name=args.keep_node_name, need_admin=False)
        except (RbError, ValueError, OSError) as e:
            raise SystemExit('otp: %s' % e)
        BIND_STRICT['tokens'] = False
        bind_tokens(store)
        m = got['manifest']
        print(pal.ok_line('put back: %s, made %s on %s (otp %s); what this machine had is kept '
                          'as %s' % (os.path.basename(path), m.get('made_words'), m.get('node'),
                                     m.get('otp'), got.get('safety'))))
        for x in got['said']:
            print(pal.ok_line(x))
        print('now:  systemctl restart otp')
        if m.get('ha_mode') == 'replicated':
            print('it came from a cluster: this machine is one server now - make it two again '
                  'with  otp --ha-setup  (RESTORE.md, section 4)')
        return 0

    if args.restore:
        # The same restore as the pages (1.0.44): every kind of copy, a copy
        # of what is replaced made first, the key beside it or in it.
        if not Path(args.restore).is_file():
            raise SystemExit('otp: there is no file %s' % args.restore)
        try:
            got = db_file_restore(store, args.restore, 'command line',
                                  key_file=_key_beside(args.restore), need_admin=False)
        except (ValueError, OSError) as e:
            raise SystemExit('otp: %s' % e)
        BIND_STRICT['tokens'] = False
        bind_tokens(store)
        print(pal.ok_line('put back (%s); what it replaced is kept as %s; %s'
                          % (DUMP_WORDS.get(got['kind'], got['kind']), got['safety'], got['key'])))
        if not store.db.value("SELECT COUNT(*) FROM accounts WHERE role = 'fulladmin' AND "
                              "COALESCE(disabled, 0) = 0"):
            print(pal.bad_line('nobody can sign in to the pages as a full administrator now: '
                               'otp --add-user NAME --role fulladmin'))
        return 0

    if args.tidy:
        print(pal.ok_line('tidied: %s' % store.tidy()))
        return 0

    if args.isemon_test:
        if not CONFIG.get('isemon_targets'):
            raise SystemExit('nothing to send to: otp --set isemon_targets=HOST:514')
        sh = Shipper()
        CONFIG['isemon'] = 1
        sh.configure()
        sh.put('otp', 'daemon', 'a test from otp %s on the command line - isemon reads nothing '
               'from this line' % __version__)
        sh.flush(3)
        time.sleep(0.5)
        st = sh.state()
        for t in st['targets']:
            if t in st['trouble']:
                print(pal.bad_line('%s: %s' % (t, st['trouble'][t])))
            else:
                print(pal.ok_line('%s: sent (%d)' % (t, st['sent'].get(t, 0))))
        return 0

    build_parser().print_help()
    return 2


_DAEMON_LOCK = None


def daemon_lock():
    """One daemon at a time. A second one - started by hand beside the
    service - would share nothing and answer half the requests."""
    global _DAEMON_LOCK
    import fcntl
    path = Path(STATE_DIR) / 'otp.lock'
    try:
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    except OSError:
        fd = os.open(str(path), os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        try:
            pid = os.read(os.open(str(path), os.O_RDONLY), 32).decode().strip()
        except OSError:
            pid = ''
        raise SystemExit('otp is running already%s - this one stops here.\n'
                         '  what it is doing:  otp --status\n'
                         '  the service:       systemctl status otp'
                         % (' (pid %s)' % pid if pid else ''))
    try:
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
    except OSError:
        pass
    _DAEMON_LOCK = fd


def cli_dump_copy():
    """The daemon's copy of every table, written to stdout (1.0.150): made in
    this process, its work no longer took the daemon's own time from RADIUS
    - a copy of a big database is minutes of Python."""
    load_config(saved=None)
    try:
        db = open_db()
    except DbError as e:
        sys.stderr.write('otp: %s\n' % e)
        return 1
    try:
        dump_tables(db, sys.stdout.buffer, child=True)
        sys.stdout.buffer.flush()
    finally:
        db.close()
    return 0


def run_daemon():
    become_service_user()
    load_config()
    daemon_lock()
    log_open()
    try:
        db = open_db()
        store = Storage(db)
        DAEMON_DB[0] = db
    except Exception as e:
        log('the database %s could not be opened: %s' % (CONFIG.get('db_engine'), e), 'error')
        raise SystemExit(1)
    load_config(saved=store.settings_saved())
    log_open()
    if not store.accounts():
        pw = secrets.token_urlsafe(12)
        store.add_account('admin', 'fulladmin', pw, note='made on the first start',
                          must_change=1)
        try:
            write_replacing(STATE_DIR / 'first-login.txt', 'name: admin\npassword: %s\n' % pw,
                            0o600)
        except OSError:
            pass
        store.add_event('accounts', 'there was no account, so admin was made; its password '
                        'is in %s' % (STATE_DIR / 'first-login.txt'), 'warn')
    Daemon(store).run()
    return 0


def entry():
    """The command: run as a script, or imported by /usr/local/bin/otp so its
    compiled form is kept (1.0.136) - a run no longer compiles 1.6 MB first."""
    try:
        sys.exit(cli_main())
    except KeyboardInterrupt:
        sys.exit(130)
    except (ValueError, OSError, LdapError, DbError) as e:
        # Said as one line, not a trace (1.0.44): a missing file, a name
        # with a comma, a realm that is not there.
        if isinstance(e, BrokenPipeError):
            sys.exit(0)
        if '--daemon' in sys.argv:
            raise                       # the service keeps its whole trace
        sys.stderr.write('otp: %s\n' % e)
        sys.exit(1)
    except BrokenPipeError:
        sys.exit(0)


def otp_argv(here=None):
    """How this program runs itself again (the console's commands): imported,
    so its compiled form is used."""
    here = os.path.dirname(os.path.abspath(here or __file__))
    return [sys.executable, '-I', '-c', 'import sys; sys.path.insert(0, %r); sys.argv[0] = "otp"; '
            'import otp; otp.entry()' % here]


if __name__ == '__main__':
    entry()
