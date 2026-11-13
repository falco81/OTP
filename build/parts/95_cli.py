

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
    # No terminal (cron, ssh without -t, a pipe): one line of stdin, as --set
    # KEY=- takes it (1.0.205) - getpass read it, asked "and again" and ended
    # in a traceback at the end of the input.
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        if not line:
            raise SystemExit('otp: %s: nothing on stdin and no terminal to ask on' % prompt)
        return line.rstrip('\r\n')
    try:
        first = getpass.getpass('%s: ' % prompt)
        if twice:
            again = getpass.getpass('and again: ')
            if first != again:
                raise SystemExit('those two are not the same')
    except (EOFError, KeyboardInterrupt):
        raise SystemExit('otp: %s: not given' % prompt)
    return first


def not_on_command_line(what, value, how):
    """A secret written out on the command line is refused (1.0.187): ps, the
    shell's history and the process accounting all keep it. - asks for it."""
    # Only - (asked, or a line of stdin) or nothing (1.0.205): '@envSecret' was
    # taken as it was written, the secret on the command line after all. --set
    # KEY=@env reads OTP_VALUE_KEY before this is asked.
    if value not in (None, '', '-'):
        raise SystemExit('otp: %s is not taken on the command line, where ps and the shell\'s '
                         'history keep it: %s' % (what, how))


def ask_secret_value(key):
    """KEY=- of --set: from OTP_VALUE_<KEY>, else asked (twice), else one line of stdin."""
    env = 'OTP_VALUE_' + key.upper()
    if os.environ.get(env):
        return os.environ[env]
    if sys.stdin.isatty():
        return ask_password(key, twice=True, env=None)
    line = sys.stdin.readline().rstrip('\r\n')
    if not line:
        # Nothing on stdin (a cron job, ssh without -t) saved an empty value
        # over the secret (1.0.207). Emptied on purpose: KEY= with nothing.
        raise SystemExit('otp: %s: nothing came on stdin and there is no terminal to ask on '
                         '(to empty it on purpose: --set %s=)' % (key, key))
    return line


class CliApiHandler(ApiHandler):
    """What a page asks, asked by the command line (1.0.188): the route's own
    checks, events and words, as a full administrator called 'command line'
    (root on this machine is that already). No HTTP: no socket, no session."""

    def __init__(self, daemon, who, body=None, args=None, path=''):
        self.server = type('S', (), {'daemon': daemon})()
        self.headers = {'X-Otp-Client': '127.0.0.1'}
        self.client_address = ('127.0.0.1', 0)
        self.args = dict(args or {})
        self._body = dict(body or {})
        self.route_path = path
        self.who = who

    def me(self, role='readonly'):
        return {'id': 0, 'name': self.who, 'role': 'fulladmin', 'kind': 'admin',
                'account': {'name': self.who, 'role': 'fulladmin', 'source': 'local'}}

    def session(self, kind='admin'):
        return self.me()


def cli_api(daemon, who, method, path, body=None, args=None):
    """One route of the pages, run here: its answer, or SystemExit with its words."""
    fn = ROUTES.get((method, path))
    if not fn:
        raise SystemExit('otp: the pages have no %s %s' % (method, path))
    h = CliApiHandler(daemon, who, body, args, path)
    try:
        return fn(h)
    except ApiError as e:
        raise SystemExit('otp: %s' % e)
    except (ValueError, BadSetting) as e:
        raise SystemExit('otp: %s' % e)


def cli_os_roots(args, pal, api, out):
    """otp --os-roots, --os-roots-add FILE, --os-roots-remove FINGERPRINT (1.0.265): Settings ->
    Certificates and TLS -> Trusted roots of the system, on the command line."""
    if args.os_roots_add:
        try:
            with open(args.os_roots_add, 'rb') as f:
                raw = f.read(OSR_MAX * OSR_PEM_MAX + 1)
        except OSError as e:
            raise SystemExit('otp: %s' % e)
        try:
            text = osr_text(raw)
        except ValueError as e:
            raise SystemExit('otp: %s: %s' % (args.os_roots_add, e))
        got = api('POST', '/api/osroots', {'action': 'check', 'text': text})['certs']
        for c in got:
            print('  %s  %s  %s' % (pal.head(c['cn'] or '?'), c['kind'], pal.dim('SHA-256 ' + c['fp'])))
            print(pal.dim('    issued by %s; valid %s - %s; %s' % (
                c['issuer'], stamp(c['not_before']) if c['not_before'] else '?',
                stamp(c['not_after']) if c['not_after'] else '?', c['key'])))
            for w in c['refused']:
                print(pal.bad_line('    not taken: %s' % w))
            for w in c['warn']:
                print(pal.warn_line('    %s' % w))
            if c['already']:
                print(pal.dim('    there already'))
        if not any(not c['refused'] and not c['already'] for c in got):
            raise SystemExit('otp: nothing to add')
        cli_sure(args, 'every program of every node will trust what these sign')
        r = api('POST', '/api/osroots', {'action': 'add', 'text': text})
        if args.json:
            out(r)
        else:
            print(pal.ok_line(r['message']))
        return 0
    if args.os_roots_remove:
        cli_sure(args, 'what %s signs is no longer trusted by the system of any node' % args.os_roots_remove)
        r = api('POST', '/api/osroots', {'action': 'remove', 'fp': args.os_roots_remove})
        if args.json:
            out(r)
        else:
            print(pal.ok_line(r['message']))
        return 0
    v = api('GET', '/api/osroots')
    if args.json:
        out(v)
        return 0
    print(pal.head('the system\'s trusted roots - otp\'s additions (%d of %d at most)' % (len(v['certs']), v['max'])))
    names = [n['name'] for n in v['nodes']]
    print(table([[c['cn'] or '?', c['kind'] or '?', c['fp'][:16],
                  stamp(c['not_after']) if c.get('not_after') else '?', c.get('key') or '?'] +
                 (['yes' if c['on'].get(n) else 'no' for n in names] if len(names) > 1 else [])
                 for c in v['certs']],
                ['name', 'kind', 'sha-256', 'valid until', 'key'] + (names if len(names) > 1 else [])))
    for c in v['certs']:
        for w in c.get('warn') or []:
            print(pal.warn_line('  %s: %s' % (c['cn'], w)))
    for n in v['nodes']:
        s = n['system'] or {}
        print(pal.head('%s%s' % (n['name'], ' (this one)' if n['me'] else '')))
        say = {'applied': pal.ok_line, 'failed': pal.bad_line}.get(n['status'], pal.warn_line)
        print(say('  %s%s' % ({'applied': 'as wanted', 'waiting': 'waiting', 'failed': 'failed',
                               'none': 'nothing added by otp'}.get(n['status'], n['status']),
                              (': ' + n['why']) if n['why'] else '')))
        if n.get('dir'):
            print(pal.dim('  local additions in %s, made into the system\'s list by %s' % (n['dir'], n['tool'])))
        if s:
            print(pal.dim('  the system\'s own list: %s certificates in %s%s' % (
                s.get('count', '?'), s.get('path', '?'),
                ('; package %s' % s['package']) if s.get('package') else '')))
        others = [o for o in n.get('others') or []]
        if others:
            print(pal.dim('  added by somebody else (otp leaves them as they are):'))
            for o in others:
                cs = o.get('certs') or []
                print('    %s  %s' % (o.get('file'), ', '.join('%s (%s)' % (c.get('cn'), c.get('kind')) for c in cs)
                                      or ('a link to %s' % o['link'] if o.get('link') else 'no certificate read')))
        py = n.get('python') or {}
        if py and not py.get('system'):
            print(pal.warn_line('  otp\'s own connections trust %s - not the system\'s list' % (
                py.get('cafile') or py.get('capath') or '?')))
    return 0


def cli_ask_wait(store, kind, asked, secs=90, say=None):
    """What every node answered to an ask (asked = {'id', 'nodes'}): waited for
    until all have, or secs. {node: answer or None}."""
    end = time.time() + secs
    got = {}
    while time.time() < end:
        got = {n: v for n, v in node_ask_results(store, kind, asked['id']).items()
               if n in asked['nodes']}
        if got and all(got.get(n) for n in asked['nodes']):
            break
        time.sleep(0.5)
    return {n: got.get(n) for n in asked['nodes']}


def cli_show(obj, pal, indent=2, depth=0, most=60):
    """A view of the pages as lines: KEY  value, nested ones indented."""
    pad = ' ' * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v in (None, '', [], {}):
                continue
            if isinstance(v, (dict, list)) and depth < 3:
                print('%s%s' % (pad, pal.dim(str(k)) if pal else k))
                cli_show(v, pal, indent + 2, depth + 1, most)
            else:
                text = json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) \
                    else (stamp(v) if isinstance(v, float) and v > 1e9 and str(k).endswith(('at', 'end', 'since', 'after', 'before')) else str(v))
                print('%s%-24s %s' % (pad, k, text[:200]))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:most]):
            if isinstance(v, (dict, list)):
                print('%s- %s' % (pad, next((str(v[k]) for k in ('name', 'node', 'target', 'rule', 'key',
                                                               'kind', 'what') if v.get(k)), '')
                                  if isinstance(v, dict) else ''))
                cli_show(v, pal, indent + 2, depth + 1, most)
            else:
                print('%s- %s' % (pad, v))
        if len(obj) > most:
            print('%s… %d more' % (pad, len(obj) - most))
    else:
        print('%s%s' % (pad, obj))


def cli_ask_said(pal, answers):
    """Each node's answer to an ask, one block each; the exit code."""
    bad = 0
    for n, got in answers.items():
        if not got:
            bad += 1
            print(pal.bad_line('%s: no answer - is otp running there?' % n))
            continue
        ok = got.get('ok', not got.get('error'))
        bad += 0 if ok else 1
        print((pal.ok_line if ok else pal.bad_line)('%s: %s' % (n, got.get('error') or got.get('said') or ('ok' if ok else 'failed'))))
        cli_show({k: v for k, v in got.items() if k not in ('id', 'at', 'node', 'ok', 'error', 'said')}, pal, 4)
    return 1 if bad else 0


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
    g.add_argument('--secret', metavar='-', help='the shared secret (-: from OTP_SECRET, '
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
    g.add_argument('--bind-pw', metavar='-', help='its password: - asks for it (or '
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
    g.add_argument('--get', nargs='+', metavar='KEY', help='the value of these settings, as --set '
                   'takes them: one key - the value alone (for a script); more - KEY=VALUE a line '
                   '(with --json an object); a secret only "set" or "not set"')
    g.add_argument('--set', action='append', metavar='KEY=VALUE', help='change one (again for '
                   'more); a secret (a password, a token) as KEY=-: asked for, or one line of '
                   'stdin, or OTP_VALUE_KEY - never written out here')
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
    g.add_argument('--selinux-check', action='store_true',
                   help='how SELinux stands for otp on this machine: the mode, otp\'s module, the '
                        'labels, booleans and ports it needs, what was refused since the start '
                        '(as root; nothing is changed)')
    g.add_argument('--selinux-want', action='store_true', help=argparse.SUPPRESS)
    g.add_argument('--selinux', choices=('check', 'prepare', 'apply', 'enforce', 'permissive'),
                   metavar='STEP', help='SELinux on this machine, as on the pages: check, prepare '
                   '(permissive at the next start, from disabled), apply (put in what otp needs, '
                   'while permissive), enforce, permissive - asked first unless --yes (as root)')
    g.add_argument('--selinux-report', nargs='?', const='', metavar='FILE',
                   help='what SELinux says on this machine, for whoever writes otp\'s module: one '
                        'file (/root/otp-selinux-report-NODE-DATE.tar.gz unless named); nothing '
                        'is changed (as root)')
    g.add_argument('--dir-caps', action='store_true',
                   help='each directory\'s cap of wrong passwords on these pages, and its domain\'s '
                        'policy as last read')
    g.add_argument('--dir-cap', metavar='NAME=SPEC', action='append',
                   help='a directory\'s own cap: NAME=3/30 (3 wrong passwords in 30 min), '
                        'NAME=setting (as the setting), NAME=none (no cap)')
    g.add_argument('--dir-policy', metavar='NAME',
                   help='read the domain\'s lockout and password policy (and its fine-grained ones) '
                        'and say the cap recommended')
    g.add_argument('--dir-sample', nargs=2, metavar=('NAME', 'USER'),
                   help='every attribute of one person in a directory - where the e-mail address '
                        'and the mobile number can be read')
    g.add_argument('--guard-status', action='store_true',
                   help='the guard against writes to the database on this node: on or off, and '
                        'every row that reaches root not as otp wrote it')
    g.add_argument('--sso-status', action='store_true',
                   help='the sign-in by a load balancer or WAF on the enrolment pages: on or off, '
                        'which balancers, which header, and the last sign-in each node saw')
    g.add_argument('--sso-key', action='store_true',
                   help='make a new key for the balancer to send in X-Otp-Sso-Key, shown once '
                        '(the one before is no longer taken)')
    g.add_argument('--local-users', action='store_true',
                   help='the local users of each node\'s system (root and UID 1000 and up): who is '
                        'there, sudo, locked, the password')
    g.add_argument('--local-user', nargs=2, metavar=('WHAT', 'NAME'),
                   help='change a local user on the nodes (never root): add, password, lock, unlock, '
                        'sudo-on, sudo-off, drop or drop-home - a password is asked, never given on '
                        'the command line')
    g.add_argument('--local-policy', action='store_true',
                   help='the password policy of the local users: as set, and as in effect on each node')
    g.add_argument('--local-policy-set', nargs='+', metavar='KEY=VALUE',
                   help='set the password policy of the local users on every node: managed=1|0, minlen, '
                        'minclass, maxrepeat, difok, dictcheck, usercheck, remember, max_days, min_days, '
                        'warn_days, deny, unlock_time, fail_interval, existing')
    g.add_argument('--machine-kept', nargs='?', const='show', choices=('show', 'putback'),
                   help='what a backup carries of each machine (local users, SSH keys, SELinux\'s '
                        'booleans); putback: put it back on this machine now (only what is missing)')
    g.add_argument('--local-nodes', metavar='NODES', default='',
                   help='with --local-user: only these nodes (separated by commas); every node if not given')
    g.add_argument('--local-full-name', metavar='TEXT', default=None, help='with --local-user add: the full name')
    g.add_argument('--local-shell', metavar='PATH', default=None,
                   help='with --local-user add: the shell (/bin/bash if not given)')
    g.add_argument('--local-max-days', metavar='N', default=None,
                   help='with --local-user aging: the days a password is good (99999: no end)')
    g.add_argument('--local-min-days', metavar='N', default=None,
                   help='with --local-user aging: the least days between two changes')
    g.add_argument('--local-warn-days', metavar='N', default=None,
                   help='with --local-user aging: warned so many days before it runs out')
    g.add_argument('--local-must-change', action='store_true',
                   help='with --local-user add or password: to be changed at the next sign-in')
    g.add_argument('--console-users', metavar='USERS',
                   help='the console at login for normal users too, through sudo: * (every one), '
                        'none, or names separated by spaces or commas')
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
    g.add_argument('--read-copy', metavar='FILE', help=argparse.SUPPRESS)
    g.add_argument('--restore', metavar='FILE', help='put a copy back (--yes); without --yes, '
                   'what is in it and where it was made')
    g.add_argument('--restore-bundle', metavar='FILE', help='put back a backup sent to a '
                   'destination (otp-backup-....tar.gz.enc): everything - the database, the key '
                   'of the tokens, the node\'s name; without --yes, what is in it')
    g.add_argument('--passphrase-file', metavar='FILE', help='with --restore-bundle: the '
                   'password of the backups, one line (else OTP_BACKUP_PASSWORD, else asked)')
    g.add_argument('--keep-node-name', action='store_true', help='with --restore-bundle: this '
                   'machine keeps its node name')
    g.add_argument('--rbackup-now', action='store_true', help='a backup of this node to every '
                   'destination switched on (Settings → Backups), now - this node only, unless '
                   '--rbackup-all asks the other nodes to make theirs too')
    g.add_argument('--rbackup-all', action='store_true', help='with --rbackup-now: the other '
                   'nodes are asked to make theirs too, as Back up now on the pages')
    g.add_argument('--rbackup-status', action='store_true', help='the backup destinations and '
                   'the last backups sent')
    g.add_argument('--backup-info', metavar='FILE', help='what a copy holds and the machine it '
                   'was made on, its config.json among it')
    g.add_argument('--tidy', action='store_true', help='delete what has been kept long enough')
    g.add_argument('--isemon-test', action='store_true', help='send one line to isemon’s '
                   'receivers and say what happened')
    g = p.add_argument_group('WHAT THE PAGES DO, HERE TOO', 'For a server without its pages '
                             '(installed --no-web) or with them down (1.0.187).')
    g.add_argument('--acme', action='store_true', help='the certificates by ACME: each one\'s name, '
                   'end, who looks after it, its last order')
    g.add_argument('--acme-order', metavar='TARGET', help='order it now, followed here: a node\'s '
                   'name, vip, or all (each one ACME looks after)')
    g.add_argument('--updates', choices=('status', 'check', 'start', 'cancel'), help='the updates '
                   'of the operating system: how they stand, look for them now, start them on '
                   '--node NAME,NAME (every node when none) one at a time, or stop them')
    g.add_argument('--reboot', choices=('ask', 'auto', 'never'), default='ask', help='with '
                   '--updates start: restart a node whose update needs it - ask on the pages, '
                   'by itself, or never [ask]')
    g.add_argument('--restart-nodes', metavar='NODE,NODE', help='restart these machines now, one '
                   'at a time, the service kept on the others (all: every node)')
    g.add_argument('--restarts', action='store_true', help='the restarts asked for, and how they '
                   'went')
    g.add_argument('--mail-test', metavar='ADDRESS', help='send a test mail now, every step said')
    g.add_argument('--sms-test', metavar='NUMBER', help='send a test SMS now (a code that opens '
                   'nothing)')
    g.add_argument('--ssh-tokens', action='store_true', help='the SSH tokens (Settings - SSH '
                   'server), each one\'s way and when last used')
    g.add_argument('--ssh-token-add', metavar='NAME', help='an SSH token for the account NAME: '
                   'from the app (its QR code shown once), or --by mail|sms --to')
    g.add_argument('--ssh-token-del', metavar='NAME', help='take an SSH token away')
    g.add_argument('--lockouts', action='store_true', help='who and what is locked out now: '
                   'tokens, the pages\' sign-ins, places refused')
    g.add_argument('--lockouts-clear', metavar='all|KIND:WHO', help='forget a lockout (the KIND '
                   'and WHO --lockouts shows), or every one, on every node')
    g.add_argument('--siem-test', action='store_true', help='a test line to the syslog servers '
                   '(SIEM), sent by every node (--node: one), and what each said')
    g.add_argument('--proxy-test', metavar='URL', nargs='?', const='', help='the way out through '
                   'the proxy tried on every node (an address of your own, or the upgrades\' one)')
    g.add_argument('--snmp-test', action='store_true', help='each node\'s SNMPv3 agent asked as a '
                   'manager would ask it')
    g.add_argument('--snmp-trap', action='store_true', help='a test trap from every node to the '
                   'receivers set')
    g.add_argument('--db-tls', action='store_true', help='encryption to the database server: how '
                   'each node reaches it, and its certificates')
    g.add_argument('--db-tls-probe', metavar='MODE', choices=('require', 'verify-ca', 'verify-full'),
                   help='try that mode from every node, changing nothing')
    g.add_argument('--db-tls-apply', metavar='PHASE', choices=('server', 'connect', 'server_off'),
                   help='a step of the wizard on every node: server (otp\'s certificates into the '
                   'PostgreSQLs), connect (each node\'s connection to --db-tls-mode), server_off')
    g.add_argument('--db-tls-mode', choices=('', 'require', 'verify-ca', 'verify-full'), default=None,
                   help='with --db-tls-apply connect: the mode ("" no TLS) [verify-full]')
    g.add_argument('--db-tls-ca', choices=('otp', 'system', 'given', 'keep'), default='otp',
                   help='whose authority checks the server: otp\'s, the system\'s, one given '
                   'with --ca FILE, the one kept [otp]')
    g.add_argument('--isemon-tls', action='store_true', help='the encrypted sending to isemon: '
                   'how it stands on each node')
    g.add_argument('--isemon-tls-probe', metavar='HOST[:PORT]', help='isemon over TLS tried from '
                   'every node (--db-tls-ca otp|system|given --ca FILE; --no-verify; --mtls)')
    g.add_argument('--isemon-tls-apply', metavar='HOST[:PORT]', help='send to isemon over TLS from '
                   'now on')
    g.add_argument('--isemon-tls-off', metavar='HOST', nargs='?', const='', help='back to plain '
                   'TCP (514)')
    g.add_argument('--isemon-tls-bundle', metavar='FILE', help='the zip for isemon\'s side (its '
                   'certificate and key, locked with a passphrase asked for; --names, --mtls)')
    g.add_argument('--names', metavar='N1,N2', help='with --isemon-tls-bundle, --tls-csr, '
                   '--tls-selfsigned: the names it is for')
    g.add_argument('--mtls', action='store_true', help='with --isemon-tls-*: each node shows its '
                   'own certificate too')
    g.add_argument('--ntp', action='store_true', help='the time: each node\'s servers and how far off')
    g.add_argument('--ntp-sync', action='store_true', help='set the clock of this node (--node: '
                   'another) from its servers now')
    g.add_argument('--os-roots', action='store_true', help='the system\'s trusted roots of every '
                   'node: the certificate authorities otp added, those added by somebody else, the '
                   'system\'s own list and its package')
    g.add_argument('--os-roots-add', metavar='FILE', help='put the certificate authorities of FILE '
                   '(PEM - one or a chain - or one in DER) into the trust of the system of every node '
                   '(asked first unless --yes)')
    g.add_argument('--os-roots-remove', metavar='FINGERPRINT', help='take one otp added out of it '
                   'again (its SHA-256 fingerprint, 12 characters of it at least)')
    g.add_argument('--net', action='store_true', help='each node\'s network as it read it')
    g.add_argument('--hisec', action='store_true', help='high security: every rule, kept or not, '
                   'and its exceptions')
    g.add_argument('--hisec-waive', nargs=2, metavar=('RULE', 'on|off'), help='make RULE an '
                   'exception of high security, or not any more')
    g.add_argument('--api', nargs='+', metavar=('METHOD PATH', 'BODY'), help='any page\'s question '
                   'as the pages ask it: GET /api/ntp, or POST /api/osup \'{"action": "check"}\' '
                   '(BODY - : read from stdin, for one holding a secret) - the answer as JSON')
    g = p.add_argument_group('MAINTENANCE AND UPGRADES')
    g.add_argument('--maintenance', choices=('on', 'off', 'status'), help='this node out of '
                   'service (RADIUS not answered, /healthz 503) or back; status says which')
    g.add_argument('--node', metavar='NAME', help='with --maintenance, --set (a node\'s own '
                   'setting; * for the cluster\'s own value), --change-keep, --after-done: another '
                   'node of the cluster rather than this one')
    g.add_argument('--why', metavar='TEXT', help='with --maintenance on: why, for the events')
    g.add_argument('--after', action='store_true', help='what is to be done by hand after an '
                   'update, on every node, with the commands (as Settings → Upgrades → To be done '
                   'by hand); this node looks again first')
    g.add_argument('--after-done', metavar='ID', help='mark one of --after as done (a manual one; '
                   'an automatic one too, logged as such) - with --node for another node\'s')
    g.add_argument('--after-clear', action='store_true', help='empty "done lately" of --after (what '
                   'is still to be done stays)')
    g.add_argument('--after-brief', action='store_true', help=argparse.SUPPRESS)
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
                   '.pfx / .p12; its password in OTP_TLS_PASSWORD. An RSA and an ECDSA certificate '
                   'of the same names together (two keys in the PEM, or two .pfx): both, the ECDSA '
                   'one beside')
    g.add_argument('--tls-preset', choices=['standard', 'intermediate', 'modern'],
                   help='the protocols and ciphers: standard (TLS 1.2+1.3, ECDHE), intermediate '
                   '(Mozilla, with DHE), modern (TLS 1.3 only)')
    g.add_argument('--tls-dh', choices=sorted(DH_WORDS), help='the DH parameters')
    g.add_argument('--tls-hsts', type=int, metavar='SECONDS', help='Strict-Transport-Security '
                   '(0 = none)')
    g.add_argument('--tls-csr', metavar='CN', help='a certificate request for --tls-for (its key '
                   'waits here; --names, --org): printed, for your authority - then --tls-import what '
                   'it sends back')
    g.add_argument('--tls-selfsigned', metavar='CN', help='a certificate of its own for --tls-for '
                   '(--names; --days [825])')
    g.add_argument('--org', metavar='TEXT', default='', help='with --tls-csr, --tls-selfsigned: the '
                   'organisation')
    g.add_argument('--days', type=int, default=825, help='with --tls-selfsigned: how long [825]')
    g.add_argument('--tls-export', nargs=2, metavar=('FORMAT', 'FILE'), help='the certificate of '
                   '--tls-for into FILE: pem, fullchain, der, p7b, pfx or pemkey (the last two with '
                   'its private key, locked with a password asked for; --legacy: a PFX older Windows '
                   'open)')
    g.add_argument('--legacy', action='store_true', help='with --tls-export pfx: 3DES, for Windows '
                   'before 10 (1709) and Server 2016')
    g.add_argument('--tls-forget', action='store_true', help='otp no longer looks after the TLS of '
                   '--tls-for (nginx keeps the files it has; --yes)')
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



def backup_as_service(db, why):
    """make_backup by the otp account, never by root (1.0.249): the folder of the copies is the
    otp account's, which can make it a link - root then left a file of its own wherever it led."""
    st = os.stat(str(STATE_DIR))
    if os.geteuid() != 0 or (st.st_uid == 0 and not st.st_mode & 0o022):
        return make_backup(Storage(db), why)        # nobody but root can change the folder

    def go():
        # The folder's owner (the otp account; another in a test of its own)
        import pwd
        try:
            name = pwd.getpwuid(st.st_uid).pw_name
            os.initgroups(name, st.st_gid)
        except (KeyError, OSError):
            os.setgroups([st.st_gid])
        os.setgid(st.st_gid)
        os.setuid(st.st_uid)
        return {'path': str(make_backup(Storage(open_db()), why))}
    got = console_in_child(go, 1800)
    if got.get('error'):
        raise OSError(got['error'])
    return got.get('path')


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
    if '# OTP-REALIP-BEGIN' in text:
        # Set on the pages since 1.0.237: one place for it, not two that undo each other.
        print(pal.bad_line('it is set on the pages (Settings - Firewall and access - Behind a load '
                           'balancer or WAF): change it there, or otp --set web_proxy_from=\'%s\''
                           % ' '.join(cidrs)))
        return False
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
    load_config(saved=dbguard_settings(store.settings_saved(), store))
    HA_STORE['store'] = store
    host0 = str(CONFIG.get('db_host') or '')
    if store.db.engine == 'postgres' and host0 in ('', 'localhost', '127.0.0.1', '::1') \
            and not args.ha_shared and (args.ha_setup or CONFIG.get('ha_mode') == 'replicated'):
        if not args.ha_setup and CONFIG.get('ha_mode') == 'replicated':
            return cli_ha_bundle_again(args, pal, store)
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
                    '(the database at %s)' % db_host, 'warn', who=cli_who())
    # Under the name the running daemon holds (1.0.252): carried to a new one at its restart.
    ha_mark_shared(args.ha_peer or '', store)
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
    """The other node let in by the firewall that really runs here (1.0.213) -
    otp's own (OTP-IN), firewalld, or the system's iptables with its REJECT at the
    end - checked, and said as it is. It said "firewalld lets ..." whether firewalld
    ran or not, otp's own firewall let the other node in only once the cluster was
    made, and the join stopped on "No route to host". Kept as a node being joined
    for a day: otp's firewall keeps it in its rules, the pages show it."""
    try:
        a = peer_address(peer)
    except ValueError as e:
        print(pal.bad_line('the firewall: %s is not an address (%s)' % (peer, e)))
        return False
    ha_joining_set([str(a)], cli_who(), 'a cluster made with it')
    fam = 'ipv4' if a.version == 4 else 'ipv6'
    ipt = 'iptables' if a.version == 4 else 'ip6tables'
    net = '%s/%d' % (a, 32 if a.version == 4 else 128)
    did, ok_all = [], True

    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            return subprocess.CompletedProcess(cmd, 1, '', str(e))
    # otp's own firewall: its chain, rebuilt by root from the rules - the node
    # being joined is among them from now on; put in at once meanwhile.
    if shutil.which(ipt) and run([ipt, '-n', '-L', 'OTP-IN']).returncode == 0:
        rule = ['-s', net, '-m', 'comment', '--comment', 'otp: The other node', '-j', 'ACCEPT']
        if run([ipt, '-C', 'OTP-IN'] + rule).returncode != 0:
            run([ipt, '-I', 'OTP-IN', '1'] + rule)
        if run([ipt, '-C', 'OTP-IN'] + rule).returncode == 0:
            did.append('otp\'s firewall (OTP-IN) lets %s in' % a)
        else:
            ok_all = False
            print(pal.bad_line('otp\'s firewall (OTP-IN): %s could not be let in' % a))
    # firewalld - only when it runs: installed and stopped, its rule changed nothing.
    fw = run(['firewall-cmd', '--state']) if shutil.which('firewall-cmd') else None
    if fw is not None and fw.returncode == 0 and 'running' in (fw.stdout or ''):
        rich = ('rule family="%s" source address="%s" port port="%d" protocol="tcp" accept'
                % (fam, net, port))
        r1 = run(['firewall-cmd', '--permanent', '--add-rich-rule=' + rich])
        r2 = run(['firewall-cmd', '--add-rich-rule=' + rich])
        q = run(['firewall-cmd', '--query-rich-rule=' + rich])
        if q.returncode == 0 and r1.returncode == 0:
            did.append('firewalld lets %s reach PostgreSQL (TCP %d)' % (a, port))
        else:
            ok_all = False
            print(pal.bad_line('firewalld did not take the rule for %s: %s' % (
                a, ((r1.stderr or '') + (r2.stderr or '')).strip()[:200] or 'no answer')))
    elif shutil.which(ipt) and run([ipt, '-n', '-L', 'OTP-IN']).returncode != 0:
        # The system's own iptables (iptables-services: a REJECT at the end of INPUT):
        # let in at the top, as the cluster's other node.
        got = run([ipt, '-S', 'INPUT'])
        shut = got.returncode == 0 and (re.search(r'-j (REJECT|DROP)', got.stdout or '') or
                                        '-P INPUT DROP' in (got.stdout or ''))
        if shut:
            rule = ['-s', net, '-m', 'comment', '--comment', 'otp: The other node', '-j', 'ACCEPT']
            if run([ipt, '-C', 'INPUT'] + rule).returncode != 0:
                run([ipt, '-I', 'INPUT', '1'] + rule)
            if run([ipt, '-C', 'INPUT'] + rule).returncode == 0:
                did.append('%s lets %s in (INPUT, first)' % (ipt, a))
                print(pal.warn_line('the system\'s %s rule is not saved: kept over a restart by  '
                                    'service %s save  - or switch otp\'s firewall on '
                                    '(Settings → Firewall), which keeps it' % (ipt, ipt)))
            else:
                ok_all = False
                print(pal.bad_line('%s: %s could not be let in' % (ipt, a)))
    for line in did:
        print(pal.ok_line(line))
    if not did and ok_all:
        print(pal.ok_line('no firewall here stands between this node and %s' % a))
    return ok_all

def cli_ha_bundle_again(args, pal, store):
    """--ha-bundle on a node already replicating: the bundle for the other
    node, made again - nothing set up, nothing restarted (1.0.207)."""
    data = ha_replicated_bundle_data(store)
    if data['db'].get('db_password') in (None, '') or is_masked(str(data['db'].get('db_password'))):
        raise SystemExit('otp: the database password is not in config.json here - the bundle '
                         'could not carry it')
    phrase = ha_passphrase()
    target = Path(args.ha_bundle or '/root/otp-join-%s.json' % node_name())
    write_private(target, json.dumps(bundle_lock(data, phrase), indent=1) + '\n')
    store.add_event('settings', 'a bundle for the other node (slot %d) was made again on the '
                    'command line - it carries the key that opens every token' % data['slot'],
                    'warn', who=cli_who())
    print(pal.ok_line('the bundle for the other node (slot %d): %s' % (data['slot'], target)))
    print('  ' + pal.bold('its passphrase, shown only now: ') + pal.info(phrase))
    print('  on the other node: otp --ha-join %s --node-name NAME' % target.name)
    return 0


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
    if CONFIG.get('ha_mode') == 'replicated' and int(CONFIG.get('ha_slot') or 1) != 1:
        # The second node made the first again (1.0.249): both slot 1, the same ids made on both,
        # and replication stopped on them.
        raise SystemExit('otp: this node is the second of a cluster - --ha-bundle makes the '
                         'bundle on the first one; to begin again here, --ha-standalone first')
    port = int(CONFIG.get('db_port') or 5432)
    name, user, pw = CONFIG.get('db_name'), CONFIG.get('db_user'), CONFIG.get('db_password')
    try:
        restart, major = pg_prepare_local(port, peer, name, user, pw, say,
                                          own_address=args.ha_address or '')
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
    load_config(saved=dbguard_settings(store.settings_saved(), store))
    # A node's own settings saved while it was alone made its own now (1.0.206):
    # kept as the plain key, they became the cluster's - the second node bound
    # RADIUS to the first one's address and greeted mail servers by its name.
    ha_own_node_keys(store)
    load_config(saved=dbguard_settings(store.settings_saved(), store))
    # Made here if the daemon never ran yet (1.0.140): the bundle held an empty
    # key, and the second node wrote an empty secrets.key and could not start.
    data = {'mode': 'replicated', 'key': sealing_key_for_write().hex(), 'pg_major': major,
            'db_guard': bool(CONFIG.get('db_guard')),   # as this node has it (1.0.247)
            'slot': 2,
            'db': {'db_name': name, 'db_user': user, 'db_password': pw},
            'peer': {'name': node_name(), 'address': me, 'port': port, 'slot': 1},
            'cluster': CONFIG.get('site_name') or 'otp'}
    phrase = ha_passphrase()
    target = Path(args.ha_bundle or '/root/otp-join-%s.json' % node_name())
    write_private(target, json.dumps(bundle_lock(data, phrase), indent=1) + '\n')
    store.add_event('settings', 'this node became the first of two, replicating with %s; a '
                    'bundle for the second was made on the command line' % peer, 'warn',
                    who=cli_who())
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
    if str(peer.get('name') or '').lower() == str(node or '').lower():
        # One name for both (1.0.249): both took themselves for the lead, and replication stopped
        # on a key written by both.
        raise SystemExit('otp: %s is the first node\'s name too - give this one another '
                         '(--node-name)' % node)
    port = int(FILE_CONFIG.get('db_port') or 5432) if FILE_CONFIG.get('db_engine') == 'postgres' \
        else 5432
    # What this node holds kept first, before anything is changed (1.0.249), as --ha-resync keeps
    # it: the join empties the tables - a node in use lost its tokens with no copy of them.
    try:
        cur = open_db()
        mine = int(cur.value('SELECT COUNT(*) FROM tokens', (), 0) or 0)
    except Exception:                                   # noqa: BLE001
        cur, mine = None, 0
    if mine:
        try:
            kept = backup_as_service(cur, 'before this node joined %s, on the command line'
                                     % (peer.get('name') or 'a cluster'))
            say('a copy of what was here (%d tokens): %s' % (mine, kept))
        except Exception as e:                          # noqa: BLE001
            raise SystemExit('otp: no copy of what is here (%d tokens) could be made, so nothing '
                             'was changed: %s' % (mine, e))
    if cur is not None:
        try:
            cur.close()
        except Exception:                               # noqa: BLE001
            pass
    try:
        if not pg_local_running(port):
            pg_install_local(int(data.get('pg_major') or 16), say)
        restart, major = pg_prepare_local(port, peer['address'], name, user, pw, say,
                                          own_address=args.ha_address or '')
        if restart:
            pg_restart_local(port)
            say('PostgreSQL started again')
        firewall_peer(peer['address'], pal, port)
        local = db_open({'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': port,
                         'db_name': name, 'db_user': user, 'db_password': pw})
        local.make_tables()
        local.add_missing_columns()
        pg_publication(port, name)
        try:
            remote = db_open({'db_engine': 'postgres', 'db_host': peer['address'],
                              'db_port': int(peer.get('port') or 5432), 'db_name': name,
                              'db_user': user, 'db_password': pw})
        except DbError as e:
            # Said what it means (1.0.213), not only what psycopg2 said.
            raise ValueError('the first node\'s PostgreSQL cannot be reached: %s'
                             % pg_reach_why(str(e), peer['address'], peer.get('port') or 5432))
        me = args.ha_address or node_address()
        # The daemon stopped while the rows come over, as --ha-resync does
        # (1.0.59): its heartbeat written into the tables being copied
        # stopped the copy on a duplicate key. Started again at the end.
        if os.geteuid() == 0 and not os.environ.get('OTP_HA_NO_RESTART') and \
                subprocess.run(['systemctl', 'is-active', '--quiet', 'otp']).returncode == 0:
            subprocess.run(['systemctl', 'stop', 'otp'], capture_output=True)
            say('otp is stopped on this node while the rows come over')
        # A rebuild that fails leaves the node in maintenance, as the pages' (1.0.249).
        HA_STORE['store'] = Storage(local)
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
    # The guard of root's actions as the first node has it (1.0.247), and - a machine new to the
    # cluster - what it put in under this name forgotten, what was kept of it put back.
    if data.get('db_guard'):
        write_file_settings({'db_guard': 1})
        say('the guard of root\'s actions on, as on %s' % (peer.get('name') or 'the other node'))
    cli_guard_counts_again('joined from the command line: the rows are the other node\'s')
    keep_mark_putback('join')
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


def cli_guard_counts_again(why):
    """After this node's database was taken from the other node (1.0.248): the newest signatures
    it had seen forgotten, as the pages' rebuild does - else the rows copied, signed earlier
    there, were refused here as older ones put back. The file stays the service's."""
    try:
        dbguard_forget_seen(why)
        if DBGUARD_FILE.exists():
            chown_to_service(DBGUARD_FILE, 0o600)
    except Exception as e:                              # noqa: BLE001
        print('otp: the guard\'s counts could not be started again: %s' % e, file=sys.stderr)


def cli_udp_taken(bind, port):
    """Whether something listens on UDP PORT at radius_bind: True, False, or None when it
    could not be asked (1.0.255). As the daemon binds it - IPv6 for an address with a
    colon, both families on '::' - and only EADDRINUSE taken as listened on: an IPv6
    bind was tried as IPv4 and failed, an address not on this machine read as in use."""
    bind = str(bind or '0.0.0.0')
    fam = socket.AF_INET6 if ':' in bind else socket.AF_INET
    try:
        probe = socket.socket(fam, socket.SOCK_DGRAM)
    except OSError:
        return None
    try:
        if fam == socket.AF_INET6:
            try:
                probe.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except OSError:
                pass
        probe.bind((bind, int(port)))
        return False
    except OSError as e:
        return True if e.errno == errno.EADDRINUSE else None
    finally:
        probe.close()


def cli_rbackup_busy(older=6 * 3600):
    """The work folder of a backup or a try being made on this node now (1.0.255), or '':
    what is left of one by a stop is taken away after hours (stale_work_away), so only
    a younger one counts."""
    try:
        items = list(STATE_DIR.iterdir())
    except OSError:
        return ''
    for p in items:
        if not p.name.startswith(('otp-rbackup-', 'otp-verify-')):
            continue
        try:
            if p.is_dir() and not p.is_symlink() and time.time() - p.lstat().st_mtime < older:
                return p.name
        except OSError:
            continue
    return ''


def cli_fqdn_wait(limit=20.0):
    """This machine's full name asked of DNS to the end (1.0.262), `limit` seconds at most: a
    command line process starts with nothing in FQDN_CACHE. True once DNS has answered."""
    fqdn_cached()
    end = time.monotonic() + limit
    while not FQDN_CACHE.get('at') and time.monotonic() < end:
        time.sleep(0.1)
    return bool(FQDN_CACHE.get('at'))


def cli_full_name(name):
    """A DNS name with a domain (otp1.example.com) - not the short host name (1.0.262)."""
    n = str(name or '').strip().lower().rstrip('.')
    return '.' in n and bool(re.match(
        r'^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})\Z', n))


def cli_acme_order_one(store, t, name, who, say):
    """One order from the command line, as the pages order it (1.0.255): the
    lease acme:busy:TARGET taken first - ordered here while a node renewed it,
    both spent the CA's limit and the last one saved won - and names looked
    up by ACME's DNS servers (acme_dns_scope), not this machine's resolver."""
    lease = 'acme:busy:%s' % t
    held = json_obj(store.get_meta(lease)) or {}
    if held.get('node') and fnum(held.get('until')) > time.time():
        # This node's daemon too: it does not ask its own lease, the command line has to.
        raise ValueError('%s is being ordered on %s already - try again after %s' % (
            name, held['node'], time.strftime('%H:%M', time.localtime(fnum(held.get('until'))))))
    mine = {'node': node_name(), 'until': time.time() + 1800,
            'by': 'cli', 'id': secrets.token_hex(8)}
    store.set_meta(lease, json.dumps(mine))
    try:
        with acme_dns_scope():
            return acme_order(store, t, name, who, say)
    finally:
        try:
            # Only the one written here: a node that took it over keeps its own.
            if (json_obj(store.get_meta(lease)) or {}).get('id') == mine['id']:
                store.drop_meta(lease)
        except Exception:                               # noqa: BLE001
            pass


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
    try:
        ha_slot_set()
    except ValueError as e:
        raise SystemExit('otp: %s' % e)
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
            kept = backup_as_service(local, 'before this node was rebuilt from the other, '
                                     'on the command line')
            print(pal.ok_line('a copy of what was here: %s' % kept))
        except Exception as e:                          # noqa: BLE001
            raise SystemExit('otp: no copy of what is here could be made, so nothing was '
                             'changed: %s' % e)
        remote = ha_peer_db()
        HA_STORE['store'] = Storage(local)      # a failed one in maintenance (1.0.249)
        got = ha_rebuild(local, remote, ha_slot_set(),
                         3 - ha_slot_set(),
                         CONFIG.get('ha_address') or node_address(),
                         int(CONFIG.get('db_port') or 5432), CONFIG.get('ha_peer'),
                         int(CONFIG.get('ha_peer_port') or 5432), CONFIG.get('db_name'),
                         CONFIG.get('db_user'), CONFIG.get('db_password'),
                         lambda t: print(pal.dim('  ' + t)))
        cli_guard_counts_again('rebuilt from the other node from the command line')
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
    load_config(saved=dbguard_settings(store.settings_saved(), store))
    HA_STORE['store'] = store
    mode = CONFIG.get('ha_mode') or ''
    if mode == 'replicated' and store.db.engine == 'postgres':
        try:
            say(ha_control(store, 'stop', by=cli_who())['message'])
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
                    % node_name(), 'warn', who=cli_who())
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


# What a row of each table of the configuration holds, compared between the
# nodes - without what changes at every sign-in (1.0.207).
HA_CONTENT = {
    'settings': ('k', "concat_ws('/', k, v)"),
    'accounts': ('name', "concat_ws('/', name, role, pw, source, disabled, must_change, dn)"),
    'clients': ('name', "concat_ws('/', name, address, secret, realm, realms, require_ma, "
                        "enabled, nas_type, position)"),
    'realms': ('name', "concat_ws('/', name, suffix, directory, lookup, auth_mode, group_list, "
                       "check_disabled, reply, enabled, position, token_name, nested, methods, "
                       "aliases)"),
    'directories': ('name', "concat_ws('/', name, hosts, port, tls, verify, ca, base, bind_dn, "
                            "bind_pw, user_attr, nested, timeout_s, enabled, weak, mail_attr, "
                            "mobile_attr)"),
}


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
            if ok and t in HA_CONTENT:
                # The same number of rows, but what is in them (1.0.207): a
                # setting or an account changed on both nodes while the link
                # was down stayed swapped and was counted "same".
                q = ("SELECT md5(COALESCE(string_agg(%s, '|' ORDER BY %s COLLATE \"C\"), '')) "
                     "FROM %s" % (HA_CONTENT[t][1], HA_CONTENT[t][0], t))
                ok = store.db.value(q) == far.value(q)
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
    who = cli_who()
    me = node_name()
    target = args.tls_for or me
    if (args.tls_import or args.tls_preset or args.tls_dh or args.tls_hsts is not None) and \
            target not in tls_targets(store):
        raise ValueError('there is no node or address called %s (a node\'s name, or vip)'
                         % target)
    said = []
    if args.tls_import:
        pem, pfx, pfx2 = '', b'', b''
        for raw in args.tls_files:
            if b'-----BEGIN' in raw:
                pem += raw.decode('utf-8', 'replace') + '\n'
            else:
                # Two (1.0.240): the RSA and the ECDSA certificate of the same names.
                if pfx2:
                    raise ValueError('two .pfx / .p12 at most (an RSA and an ECDSA one)')
                if pfx:
                    pfx2 = raw
                else:
                    pfx = raw
        prof = tls_profile(store, target) or {}
        pending = unseal_secret(prof['pending_key'], 'web:tls') if prof.get('pending_key') else ''
        got, got2 = cert_bundles(cert=pem, pfx=pfx, password=os.environ.get('OTP_TLS_PASSWORD', ''),
                                 pending_key=pending, pfx2=pfx2)
        # As on the pages (1.0.187): one run out is not put in.
        if got['info'].get('not_after') and got['info']['not_after'] < time.time():
            raise ValueError('this certificate ran out on %s' % stamp(got['info']['not_after']))
        a2 = (got2 or {}).get('info') or {}
        if a2.get('not_after') and a2['not_after'] < time.time():
            raise ValueError('the second certificate (%s) ran out on %s' % (
                a2.get('key') or 'ECDSA', stamp(a2['not_after'])))
        prof.update(cert=got['cert'], chain=got['chain'], root=got['root'],
                    key=seal_secret(got['key'], 'web:tls'), info=got['info'],
                    chain_info=got['chain_info'], root_info=got['root_info'],
                    verify=got['verify'], how='imported on the command line')
        if got2:
            prof['alt'] = {'cert': got2['cert'], 'chain': got2['chain'],
                           'key': seal_secret(got2['key'], 'web:tls'), 'info': got2['info'],
                           'for': tls_alt_for(got['cert'])}
        else:
            prof.pop('alt', None)
        prof.pop('pending_key', None)
        prof.pop('csr', None)
        prof.setdefault('preset', 'standard')
        prof.setdefault('dh', 'none')
        tls_save(store, target, prof, who)
        # One put in by hand is kept (1.0.170; here too since 1.0.187): ACME's
        # next renewal replaced it.
        acme_care_set(store, target, False, who, 'a certificate was put in by hand')
        i = got['info']
        said.append('%s: %s, until %s, %d in the chain, root %s%s' % (
            target, i.get('subject'), stamp(i.get('not_after')), len(got['chain_info']),
            'given' if got['root'] else 'not given',
            ', chain checked' if got['verify'] == 'ok' else
            (' - the chain does not check: %s' % got['verify'] if got['verify'] else '')) +
            (', with a second one beside it (%s)' % (got2['info'].get('key') or 'ECDSA') if got2 else ''))
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
        store.add_event('settings', 'the TLS of %s was changed on the command line: %s, DH %s, '
                        'HSTS %s' % (target, pol['preset'], pol['dh'], pol['hsts'] or 'off'), who=who)
    if args.vip_set or args.vip or args.vip_move or args.vip_return:
        if not CONFIG.get('ha_mode'):
            raise ValueError('the VIP address is for a cluster: otp --ha-setup first')
    if args.vip_set:
        v = vip_conf(store)
        ifaces = dict(odict(v.get('ifaces')))
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
        now = odict(b.get('web')).get('cert_now') if t != 'vip' else None
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

    def copy_in(src, name, dfd):
        """One file copied by its descriptors, never by name: not through a
        link at either end, into a new file only - made in the folder opened
        once (1.0.248: by its path, the folder could be a link by then)."""
        fi = os.open(str(src), os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
        try:
            if not stat.S_ISREG(os.fstat(fi).st_mode):
                raise OSError('%s is not a plain file' % src)
            fo = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                         dir_fd=dfd)
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

    def copy_tree(src, name, pfd):
        """A folder copied the same way: each folder made and opened by the
        one above it, never a link followed - in the copy or in what is
        copied (a link in somebody else's folder led root to anything)."""
        os.mkdir(name, 0o700, dir_fd=pfd)
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=pfd)
        try:
            for e in os.scandir(str(src)):
                if e.is_symlink():
                    continue
                if e.is_dir(follow_symlinks=False):
                    copy_tree(e.path, e.name, fd)
                elif e.is_file(follow_symlinks=False):
                    copy_in(e.path, e.name, fd)
            os.fchown(fd, ids[0], ids[1])
        finally:
            os.close(fd)

    def stage(path, with_key=False):
        src = Path(path)
        if not src.exists() or reachable(src):
            return path             # said by the command itself / its own to open
        if src.is_symlink():
            src = Path(os.path.realpath(str(src)))   # a link of root's own, followed
        # A folder of root's for each file, 0700 while it is filled, the otp
        # account's only once it is (1.0.149): handed over before the copy,
        # a link put in it in between had root write wherever it led. Opened
        # once and used by its descriptor (1.0.248): the otp account owns the
        # folder it is in, and could put a link in its place meanwhile -
        # root's chown by its name then gave it any folder of the machine.
        d = tempfile.mkdtemp(prefix='.otp-cli-', dir=str(STATE_DIR))
        atexit.register(shutil.rmtree, d, True)
        dfd = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            st = os.fstat(dfd)
            if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) & 0o077:
                raise OSError('%s is not the folder just made' % d)
            if src.is_dir():
                copy_tree(src, src.name, dfd)
            else:
                copy_in(src, src.name, dfd)
                if with_key:
                    k = _key_beside(src)
                    if k is not None and Path(k).is_file():
                        copy_in(k, Path(k).name, dfd)
            os.fchown(dfd, ids[0], ids[1])
        finally:
            os.close(dfd)
        return str(Path(d) / src.name)
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
        if getattr(args, 'os_roots_add', None):
            args.os_roots_add = stage(args.os_roots_add)     # in /root too (1.0.265)
        if getattr(args, 'export_config', None) and args.export_config != '-':
            mode = 0o600 if getattr(args, 'with_secrets', False) else 0o640
            # Emptied only when written (1.0.249): a passphrase typed twice wrong, a refusal,
            # left the file there before at 0 bytes.
            fd = os.open(args.export_config, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, mode)
            os.fchmod(fd, mode)         # as root: the otp account may not change root's file
            args.export_fd = fd
        # The files of a certificate and of isemon's bundle too (1.0.248): opened after the command
        # line became the otp account, root's /root/x.pfx was refused, and a file there already
        # kept its mode (0644 for a key).
        te = getattr(args, 'tls_export', None)
        if te and len(te) == 2 and te[0] in TLS_EXPORT_KINDS:
            mode = 0o600 if TLS_EXPORT_KINDS[te[0]][2] else 0o644
            fd = os.open(te[1], os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, mode)
            os.fchmod(fd, mode)
            args.tls_export_fd = fd
        if getattr(args, 'isemon_tls_bundle', None):
            fd = os.open(args.isemon_tls_bundle, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            os.fchmod(fd, 0o600)
            args.isemon_bundle_fd = fd
    except OSError as e:
        raise SystemExit('otp: %s' % e)


def cli_store():
    become_service_user()
    load_config(saved=None)
    try:
        db = open_db()
    except DbError as e:
        raise SystemExit('otp: %s%s' % (e, half_joined_words(e)))
    store = Storage(db, quick=True)
    _cli_name_held()
    load_config(saved=dbguard_settings(store.settings_saved(), store))
    return store


def half_joined_words(e):
    """A join that stopped half way said so (1.0.213): the cluster's key and its
    password taken, this machine's PostgreSQL not made ready yet - "password
    authentication failed" was all there was to read."""
    t = str(e)
    if not (sealing_key_path().with_name('secrets.key.before-join').exists() or
            HA_JOINING_FILE.exists()):
        return ''
    if not re.search(r'password authentication failed|no pg_hba\.conf entry|does not exist', t):
        return ''
    return ('\notp: this node looks half joined to a cluster (its key and password are the '
            'cluster\'s, its PostgreSQL is not ready for them): run the join again as root - '
            'otp --ha-join BUNDLE --node-name NAME - it starts over from where it stopped')


def _cli_name_held():
    """The name the running daemon answers under (1.0.207): node_name changed in
    config.json applies when it starts again - the command line took the new
    one at once and acted as a node that was not there (maintenance of a phantom,
    --ha-forget of the running node)."""
    try:
        pid = int((STATE_DIR / 'otp.lock').read_text().strip() or 0)
        held = NODE_NAME_FILE.read_text().strip()
        if pid > 1 and held:
            os.kill(pid, 0)
        else:
            return
    except (OSError, ValueError):
        return
    if held != node_name():
        print('otp: the daemon runs as %s until it starts again (node_name %s is for then) - '
              'this acts as %s' % (held, node_name(), held), file=sys.stderr)
        CONFIG['node_name'] = held
        NAME_HELD[0] = True


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
        return round(min(82, 20 + 60 * min(0.95, fnum(st.get('part')) / 6)
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
        # A file that is not there was the defaults (1.0.207): a mistyped path ran
        # on SQLite and an empty local database.
        if not Path(args.config).is_file():
            raise SystemExit('otp: there is no config file %s' % args.config)
        CONFIG_FILE = Path(args.config)
    if args.debug:
        FROM_ARGV['debug'] = True
    # 0 is an answer (1.0.94): --tls-hsts 0 is "none", and 0 == False made it
    # "nothing asked" - the daemon started in the foreground from a script.
    # Anything not its default is asked (1.0.207) - --proxy-test alone is '' -,
    # and a default is not: --reboot, --db-tls-ca and --days have one, and
    # `otp` alone printed the help, not the status.
    acted = any(v != parser.get_default(k) and v != []
                for k, v in vars(args).items()
                if k not in ('no_color', 'json', 'debug', 'config', 'limit', 'hours', 'search',
                             'role', 'note', 'yes', 'replace', 'invert', 'pending', 'no_qr',
                             'suffix'))
    if args.daemon:
        return run_daemon()
    if args.dump_copy:
        return cli_dump_copy()
    if args.read_copy:
        # copy_read_through in a process of its own (1.0.186); the key of the
        # tokens on stdin, never on the command line.
        key = sys.stdin.readline().strip()
        try:
            got = copy_read_through(args.read_copy, bytes.fromhex(key) if key else None,
                                    child=True)
        except (RbError, OSError, ValueError) as e:
            sys.stdout.write(json.dumps({'error': str(e)}) + '\n')
            return 1
        sys.stdout.write(json.dumps(got, default=str) + '\n')
        return 0
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
    if args.selinux_want:
        # What otp needs of SELinux here, for --selinux-check (1.0.233): read as the service.
        st = cli_store()
        got = selinux_want(st)
        try:
            got['high_security'] = bool(st.settings_saved().get('high_security'))
        except Exception:                               # noqa: BLE001
            pass
        print(json.dumps(got))
        return 0
    if args.selinux_check or args.selinux or args.selinux_report is not None:
        return cli_selinux(args, pal)
    if args.dir_caps or args.dir_cap or args.dir_policy or args.dir_sample or args.guard_status:
        return cli_dir_guard(args, pal)
    if args.sso_status or args.sso_key:
        return cli_sso(args, pal)
    if args.machine_kept:
        store = cli_store()
        if args.machine_kept == 'putback':
            if not store.get_meta('host:keep:' + node_name()):
                print('nothing is kept of %s yet' % node_name())
                return 1
            store.set_meta('host:putback:' + node_name(), json.dumps({'at': time.time(), 'by': cli_who()}))
            print('asked - the service puts it back within a minute (Events say what)')
            return 0
        for n in host_nodes(store):
            v = keep_view(store, n)
            print('%-12s %s' % (n, 'kept %s: %d user(s), %d SSH key(s)%s' % (
                time.strftime('%Y-%m-%d %H:%M', time.localtime(v['at'])), v['users'], v['keys'],
                ' - being put back' if v['pending'] else '') if v['at'] else 'nothing kept yet'))
        return 0
    if args.local_policy or args.local_policy_set:
        return cli_pwpolicy(args, pal)
    if args.local_users or args.local_user:
        return cli_osusers(args, pal)
    if args.console_at_login or args.console_users is not None:
        try:
            users = (console_users_parse(args.console_users) if args.console_users is not None
                     else None)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        if args.console_at_login in ('on', 'off') or users is not None:
            on = (args.console_at_login == 'on') if args.console_at_login in ('on', 'off') \
                else console_at_login()
            print(pal.ok_line(console_at_login_set(on, users)))
        else:
            print(pal.ok_line('the console at login is %s' % ('ON' if console_at_login()
                                                                else 'off')))
            print('  for normal users too (through sudo): %s' % console_users_words(console_users()))
        if not CONSOLE_PROFILE.exists():
            print(pal.warn_line('%s is not there - install.sh puts it in' % CONSOLE_PROFILE))
        return 0

    if args.console:
        return console_main(pal)

    cli_stage_files(args)
    store = cli_store()
    if args.after or args.after_done or args.after_clear:
        return cli_after(args, pal, store)     # to be done by hand (1.0.258)
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
            try:
                got = hatls_off(store, cli_who(), here=False)
            except ValueError as e:
                raise SystemExit('otp: %s' % e)
            print(pal.warn_line(got['message']))
            print('the daemons of both nodes go through the steps; follow them with  otp --ha-tls')
        if args.ha_tls_repair:
            try:
                got = hatls_start(store, cli_who(), here=False)
            except ValueError as e:
                raise SystemExit('otp: %s' % e)
            print(pal.ok_line(got['message']))
            print('the daemons of both nodes go through the steps; follow them with  otp --ha-tls')
        v = hatls_view(store)
        if args.json:
            print(json.dumps(v, indent=2, default=str, ensure_ascii=False))
            return 0
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
                said = net_trial_answer(store, node, act, cli_who())
            except ValueError as e:
                raise SystemExit('otp: %s' % e)
        else:
            try:
                said = fw_trial_answer(store, act, cli_who())
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
            got = ha_readdress(store, args.ha_address or '', args.ha_peer or '', by=cli_who())
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        for x in got['done']:
            print(pal.ok_line(x))
        for x in got['left']:
            print(pal.warn_line(x))
        if not got['done'] and not got['left']:
            print(got['message'])
        # The daemon reads config.json again (SIGHUP, as systemctl reload).
        if not daemon_hup():            # only the daemon's own process (1.0.248)
            print('restart the service so that it reads config.json again:  systemctl '
                  'restart otp')
        return 0 if not got['left'] else 2
    if args.ha_renamed:
        old = args.ha_renamed.strip()
        # Not this node, nor another one answering now (1.0.252, as at the start since 1.0.110):
        # a name mistyped took a live node's own settings, its certificate and its VIP preference.
        if old.lower() == node_name().lower():
            raise SystemExit('otp: that is this node\'s own name')
        live = [n for n in ha_nodes(store) if n['name'].lower() == old.lower() and n.get('alive')
                and not n.get('me') and (not n.get('mid') or n['mid'] != machine_id())]
        if live:
            raise SystemExit('otp: %s is another node, answering now (%s) - nothing carried over'
                             % (old, live[0].get('address') or '?'))
        said = node_carry(store, old, node_name(), by=cli_who())
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
        # Its maintenance and upgrade rows by ha_forget alone (1.0.262): taken here too, a node
        # still answering lost its own maintenance - RADIUS and the VIP back on it mid-work.
        ha_forget(store, args.ha_forget)
        store.add_event('settings', '%s was taken off the list of nodes on the command line'
                        % args.ha_forget, 'warn', who=cli_who())
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
                    name, datetime.fromtimestamp(fnum(row.get('at'))).strftime(
                        '%d-%m-%Y %H:%M:%S'), (' - ' + row['why']) if row.get('why') else ''))
                      if row.get('on') else '%s: in service' % name)
            return 0 if not row.get('on') else 3
        if args.maintenance == 'on' and not args.node:
            maintenance_ensure(store)
        try:
            maintenance_set(store, args.maintenance == 'on', args.why or 'on the command line',
                            cli_who(), name)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('%s: %s' % (name, 'in maintenance - RADIUS is not answered and '
                                      '/healthz says 503' if args.maintenance == 'on'
                                      else 'back in service')))
        return 0
    if args.upgrade_cancel:
        try:
            upgrade_cancel(store, cli_who())
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('the upgrade is stopped; the nodes not begun stay as they are'))
        return 0
    if args.upgrade_check:
        row = online_look(store, cli_who())
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
        row = online_look(store, cli_who())
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
            meta = online_fetch(store, pk['version'], cli_who())
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('otp %s fetched, signed by %s' % (meta['version'],
                                                             meta.get('signed_by'))))
        try:
            upgrade_start(store, cli_who())
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
                meta = downgrade_file(store, want, cli_who())
            else:
                meta = downgrade_fetch(store, want, cli_who())
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('otp %s checked (signed by %s) - the database can take it'
                          % (meta['version'], meta.get('signed_by'))))
        try:
            upgrade_start(store, cli_who())
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
    who = cli_who()

    if args.status or args.check:
        d = Daemon(store, serve=False)
        s = d.status()
        try:
            import urllib.request
            req = urllib.request.Request('http://127.0.0.1:%d/api/health'
                                         % int(CONFIG.get('api_port') or 9861))
            with url_open(req, timeout=3) as r:
                alive = json.loads(r.read().decode()).get('ok')
        except Exception:
            alive = False
        listening = []
        for kind, port in (('auth', CONFIG.get('radius_auth_port')),
                           ('acct', CONFIG.get('radius_acct_port'))):
            if not port:
                continue
            listening.append((kind, port, cli_udp_taken(CONFIG.get('radius_bind'), port)))
        s['daemon_alive'] = alive
        s['ports'] = listening
        # What an update left to be done by hand (1.0.258): a line here, the console's first
        # screen from the JSON; never among the problems (their exit code stays as it was).
        try:
            s['after'] = after_summary(store, fresh=True)
        except Exception:                               # noqa: BLE001
            s['after'] = {'n': 0, 'level': '', 'items': []}
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
            # The same exit code as the text (1.0.207): 0 with the daemon down.
            out(s)
            return 0 if alive and not s['problems'] else 1
        print(pal.head('otp %s on %s' % (__version__, s['host'])))
        print((pal.ok_line if alive else pal.bad_line)(
            'the daemon %s' % ('answers on 127.0.0.1:%s' % CONFIG.get('api_port') if alive
                               else 'is not answering - systemctl status otp')))
        for kind, port, taken in listening:
            if taken is None:
                print(pal.dim('  UDP %s (%s): could not be asked here whether it is listened on'
                              % (port, kind)))
                continue
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
        aft = odict(s.get('after'))
        if aft.get('n'):
            print((pal.bad_line if aft.get('level') == 'bad' else pal.warn_line)(
                'to be done by hand: %d - otp --after says what and how' % aft['n']))
            for x in (aft.get('items') or [])[:5]:
                print(pal.dim('    %s%s' % (x.get('title'), ('  [%s]' % x.get('node'))
                                            if x.get('node') != node_name() else '')))
            # In the check's verdict where it is bad (1.0.258): a warning or a note is said only.
            if args.check and aft.get('level') == 'bad':
                bad += 1
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
                                key=lambda c: -fnum(c.get('at')))
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
            return 0 if tok else 1
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
        # --hours when given (1.0.207): every event of any age was listed.
        given = any(w == '--hours' or w.startswith('--hours=')
                    for w in (sys.argv[1:] if argv is None else list(argv)))
        rows, total = store.events(args.limit, 0, args.search, extra=(
            'ts >= ?', [time.time() - float(args.hours) * 3600]) if given else None)
        if args.json:
            out({'rows': rows, 'total': total})
            return 0
        print(table([(stamp(r['ts']), r['kind'], r['who'] or '', r['words']) for r in rows],
                    ['when', 'kind', 'who', 'what'], [19, 22, 18, 90]))
        return 0

    tk = Tokens(store)
    if args.enroll and not store.token(args.enroll):
        # Under its realm's own suffix, as the pages make it (1.0.187): made for
        # novak@dpmo.local it was a second token beside novak@dpmo.cz, the one
        # RADIUS looks up first - the QR code just shown never let anyone in.
        r_of = store.realm_for(args.enroll)
        main = norm_name(realm_main_name(args.enroll, r_of))
        if main != norm_name(args.enroll):
            # Not when the name under the main suffix is another account's (1.0.252, as the pages
            # since 1.0.224/1.0.249): the token made, and its QR code shown, were that other's.
            ad = Daemon(store, serve=False).auth.directory((r_of or {}).get('directory')) \
                if r_of else None
            if ad is not None:
                try:
                    entry = Authenticator.find_person(ad, norm_name(args.enroll), 'upn', r_of)
                except LdapError as e:
                    # Said, not refused, here (root at the terminal sees whom it makes it for): as
                    # before 1.0.252 when the directory cannot be asked.
                    entry = False
                    print('  the directory could not say whether %s is another account (%s) - '
                          'made as asked' % (main, str(e)[:120]), file=sys.stderr)
                if entry is not False:
                    if entry and entry.get('many'):
                        entry = None
                    try:
                        clash = Authenticator.alias_clash(ad, norm_name(args.enroll), main, entry or {})
                    except LdapError as e:
                        clash = ''
                        print('  the directory could not say whether %s is another account (%s) - '
                              'made as asked' % (main, str(e)[:120]), file=sys.stderr)
                    if clash:
                        raise SystemExit('otp: %s' % clash)
            print('  %s is %s - another suffix of its realm' % (args.enroll, main),
                  file=sys.stderr if args.json else sys.stdout)
            args.enroll = main
    if args.enroll:
        had = store.token(args.enroll)
        bad_name = '' if had else token_name_problem(norm_name(args.enroll))
        if bad_name:
            # The pages' rule (1.0.224, here too 1.0.249): CORP\\novak was made, and found by
            # nobody - RADIUS reads it as novak.
            raise SystemExit('otp: %s' % bad_name)
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
            store.drop_meta(k + norm_name(args.delete_token))
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
        scratch_guard_give_back(store, args.unlock)
        store.add_event('tokens', 'the command line let %s try again at once'
                        % norm_name(args.unlock), who=cli_who())
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
        got = Daemon(store, serve=False).fill_names(by=cli_who())
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
        elif not code.isdigit():
            # A password on the command line (1.0.248): `ps` and the shell's history keep it.
            print('otp: a password given on the command line stays in the shell\'s history and is '
                  'shown by ps - give - as CODE: it is asked for (or OTP_RADTEST_PASSWORD)',
                  file=sys.stderr)
        server = a[2] if len(a) > 2 else '127.0.0.1'
        try:
            port = int(a[3]) if len(a) > 3 else int(CONFIG.get('radius_auth_port') or 1812)
        except ValueError:
            raise SystemExit('otp --radtest: the port is a number')
        secret = a[4] if len(a) > 4 else None
        not_on_command_line('the shared secret', secret, 'give - as the fifth word: it is asked for '
                            '(or OTP_SECRET)')
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
        not_on_command_line('the shared secret', args.secret, '--secret - asks for it (or OTP_SECRET)')
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
        cli_sure(args, 'the client %s is taken away' % one['name'])
        store.client_drop(one['id'])
        store.add_event('clients', 'command line took away the client %s' % one['name'],
                        who=cli_who())
        bump(store)
        print(pal.ok_line('gone'))
        return 0

    if args.realms:
        rows = store.realms()
        if args.json:
            out(rows)
            return 0
        takes = [(r['suffix'] or '(none)') + ''.join(' +' + a for a in r.get('aliases') or [])
                 for r in rows]
        # As wide as the aliases need (1.0.187): they were cut at 16.
        print(table([(r['name'], t, r['auth_mode'], r['directory'] or '-',
                      r['lookup'], '; '.join(g['group'] for g in r['groups']) or '(anybody)')
                     for r, t in zip(rows, takes)], ['name', 'takes @', 'password is', 'directory',
                                                     'lookup', 'groups'],
                    [16, max([16] + [min(48, len(t)) for t in takes]), 13, 12, 6, 70]))
        return 0

    if args.add_realm:
        old = next((r for r in store.realms() if r['name'].lower() == args.add_realm.lower()),
                   None) or {}
        groups = old.get('groups') or []
        if args.groups is not None:
            # A group it had keeps what it had (1.0.187): its replies (Class,
            # Filter-Id - the VPN's policies) were emptied by every --groups.
            had = {str(g.get('group') or '').lower(): g for g in groups}
            groups = [dict(had.get(g.lower()) or {'reply': ''}, group=g) for g in dn_list(args.groups)]
        if args.methods:
            # A word not known was dropped without a word (1.0.207): totp,mial
            # left the mail out.
            unknown = [m.strip() for m in args.methods.split(',')
                       if m.strip() and m.strip().lower() not in CODE_KINDS]
            if unknown:
                raise SystemExit('otp: --methods: %s is not one of %s'
                                 % (', '.join(unknown), ', '.join(CODE_KINDS)))
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
                        who=cli_who())
        bump(store)
        print(pal.ok_line('the realm %s is saved' % args.add_realm))
        return 0

    if args.del_realm:
        one = next((r for r in store.realms() if r['name'].lower() == args.del_realm.lower()),
                   None)
        if not one:
            raise SystemExit('there is no realm called %s' % args.del_realm)
        cli_sure(args, 'the realm %s is taken away' % one['name'])
        try:
            store.realm_drop(one['id'])
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        store.add_event('realms', 'command line took away the realm %s' % one['name'],
                        who=cli_who())
        bump(store)
        print(pal.ok_line('gone'))
        return 0

    if args.directories:
        rows = store.directories()
        if args.json:
            for d in rows:
                d['ip_hosts'] = ldap_ip_hosts(d)
            out(rows)
            return 0
        print(table([(d['name'], d['hosts'], '%s/%s' % (d['tls'], d['port']), d['base'],
                      d['bind_dn'], 'checked' if d['verify'] else 'NOT checked')
                     for d in rows], ['name', 'servers', 'how', 'base', 'reads as',
                                      'certificate']))
        # What a domain controller of Windows Server 2025 refuses (1.0.267), as the card says it.
        for d in rows:
            if d.get('tls') == 'none':
                print(pal.warn_line('%s: plain LDAP - domain controllers of Windows Server 2025 refuse a '
                               'sign-in over it (LDAP signing): LDAPS or STARTTLS' % d['name']))
            ips = ldap_ip_hosts(d)
            if ips:
                print(pal.warn_line('%s: servers given by address (%s) while the certificate is checked '
                               'against the name - a new domain controller\'s certificate usually '
                               'carries its name only: give them by name (FQDN)'
                               % (d['name'], ', '.join(ips))))
        return 0

    if args.add_directory:
        old = store.directory(args.add_directory) or {}
        ca = None
        if args.ca:
            ca = Path(args.ca).read_text()
        not_on_command_line('the password of the directory', args.bind_pw,
                            '--bind-pw - asks for it (or OTP_BIND_PW)')
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
                        % args.add_directory, who=cli_who())
        bump(store)
        print(pal.ok_line('the directory %s is saved' % args.add_directory))
        return 0

    if args.del_directory:
        one = store.directory(args.del_directory)
        if not one:
            raise SystemExit('there is no directory called %s' % args.del_directory)
        cli_sure(args, 'the directory %s is taken away' % one['name'])
        try:
            store.directory_drop(one['id'])
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        store.add_event('directories', 'command line took away the directory %s' % one['name'],
                        who=cli_who())
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
                return 0 if c.get('ok') else 1          # as without --json (1.0.205)
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

    if args.get:
        return cli_get(store, args)

    if args.settings:
        d = Daemon(store, serve=False)
        rows = d.settings_state(True)
        if args.search:
            # --search, as it says it does everywhere (1.0.187): it was every setting.
            q = args.search.lower()
            rows = [r for r in rows if q in ' '.join(str(r.get(k) or '') for k in
                                                     ('key', 'name', 'short', 'says')).lower()]
        if args.json:
            out(rows)
            return 0
        for s in rows:
            print('  %-28s %-34s %s' % (s['key'], json.dumps(s['value'], ensure_ascii=False)[:34],
                                       pal.dim(s['source_says'])))
        return 0

    if args.export_config:
        conf = config_export(store, bool(args.with_secrets))
        made_phrase = ''
        if args.with_secrets:
            # Locked as the pages lock it (1.0.207): with the secrets it was plain JSON
            # here - every client's secret, every password, the TLS keys.
            if getattr(args, 'passphrase_file', None):
                phrase = Path(args.passphrase_file).read_text().strip()
            else:
                phrase = os.environ.get('OTP_PASSPHRASE') or ''
            if not phrase:
                phrase = made_phrase = ha_passphrase()
            if len(phrase) < 10:
                raise SystemExit('otp: a passphrase of 10 characters at least locks the secrets')
            text = json.dumps(bundle_lock({'config': conf}, phrase, kind=CONFIG_BUNDLE_KIND),
                              indent=1, ensure_ascii=False, default=str)
        else:
            text = json.dumps({'config': conf}, indent=1, ensure_ascii=False, default=str)
        if args.export_config == '-':
            print(text)
        else:
            fd = getattr(args, 'export_fd', None)
            if fd is None:
                fd = os.open(args.export_config, os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                             0o600 if args.with_secrets else 0o640)
                # The mode of a file there already too (1.0.94): O_CREAT's mode is
                # only a new file's, and secrets went into a 0644 one. One opened by root
                # had its mode set then (1.0.249): the otp account may not change it.
                os.fchmod(fd, 0o600 if args.with_secrets else 0o640)
            os.ftruncate(fd, 0)
            with os.fdopen(fd, 'w') as f:
                f.write(text + '\n')
            print(pal.ok_line('%s: the configuration%s' % (
                args.export_config, ', with its secrets, locked with the passphrase'
                if args.with_secrets else ' (without the secrets)')))
        if made_phrase:
            # Said once, where the file is not (stdout may be the file itself).
            sys.stderr.write('the passphrase, written down now - it is not kept anywhere: %s\n'
                             % made_phrase)
        if args.with_secrets:
            store.add_event('settings', 'the configuration was exported with the secrets in it, '
                            'locked, on the command line', 'warn', who=who)
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
            elif v == '-' and k.strip() in SECRET_KEYS:
                v = ask_secret_value(k.strip())
            elif k.strip() in SECRET_KEYS:
                not_on_command_line(k.strip(), v, '--set %s=- asks for it (or reads one line of stdin, '
                                    'or OTP_VALUE_%s)' % (k.strip(), k.strip().upper()))
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
            # A node's own setting for another node, or the cluster's own value
            # with --node '*' (1.0.187), as the pages can: it was this node's only.
            said = d.save_settings(want, by=who, node=args.node or None)
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
            print('the running service takes it within seconds%s' % (
                '; sign-ins to the pages open before it was switched on are ended' if on else ''))
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
                cli_sure(args, 'the account %s is removed' % acc['name'])
                store.drop_account(name)
            else:
                store.set_account(name, disabled=1 if flag == 'disable_user' else 0)
            if flag in ('set_role', 'disable_user'):
                # Signed out, as on the pages (1.0.187): its role decided again
                # at its next sign-in; one switched off not left signed in.
                store.db.run('DELETE FROM sessions WHERE kind = ? AND LOWER(name) = ?',
                             ('admin', name.lower()))
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        store.add_event('accounts', '%s: %s on the command line' % (name, flag.replace('_', ' ')),
                        who=who)
        print(pal.ok_line('done'))
        return 0

    if args.backup:
        got = make_backup(store, 'on the command line')
        if args.json:                   # --json kept (1.0.207)
            out({'file': str(got)})
            return 0
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
            for k, v in sorted(odict(said.get('counts')).items()):
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
        if args.json:
            out(v)
            return 0
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
        # Not side by side with one the daemon makes (1.0.255): its guard (RB_JOB) is in its
        # own memory, its work folder is what this process can see of it.
        busy = cli_rbackup_busy()
        if busy and not args.yes:
            raise SystemExit('otp: a backup is being made or tried on this node already (%s) - '
                             'otp --rbackup-status; again with --yes if it was left by a stop'
                             % busy)
        others = []
        if args.rbackup_all:
            # Each node makes its own, as Back up now on the pages asks them (1.0.149).
            others = rb_now_ask_others(store, cli_who())
            if others:
                print(pal.dim('  %s make%s theirs within a minute' % (
                    ', '.join(others), 's' if len(others) == 1 else '')))
        try:
            run = rb_run(store, cli_who())
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
        if run.get('ok') and CONFIG.get('rbackup_verify') == 'after':
            # Tried at once at the first destination, as the pages' Back up now does (1.0.255):
            # from here rbackup_verify=after was never done.
            try:
                v = rb_verify(store, cli_who(), run['targets'][0]['id'], run.get('file'))
            except (RbError, ValueError, OSError) as e:
                print(pal.bad_line('sent, but it could not be tried: %s' % scrub_secret(str(e))[:300]))
                return 2
            if not v.get('ok'):
                print(pal.bad_line('sent, but it is not good: ' + '; '.join(
                    c['what'] for c in v.get('checks') or [] if not c['ok'])))
                return 2
            print(pal.ok_line('tried at %s: it can be put back' % run['targets'][0]['name']))
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
            got = rb_restore(store, path, password, cli_who(),
                             keep_node_name=args.keep_node_name, need_admin=False)
        except (RbError, ValueError, OSError) as e:
            raise SystemExit('otp: %s' % e)
        BIND_STRICT['tokens'] = False
        bind_tokens(store, trusted=True)
        names_nfc_kept(store)       # an old copy's names, in one form (1.0.226)
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
            got = db_file_restore(store, args.restore, cli_who(),
                                  key_file=_key_beside(args.restore), need_admin=False)
        except (ValueError, OSError) as e:
            raise SystemExit('otp: %s' % e)
        BIND_STRICT['tokens'] = False
        bind_tokens(store, trusted=True)
        names_nfc_kept(store)       # an old copy's names, in one form (1.0.226)
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

    # ---- what the pages do, here too (1.0.187) -------------------------------------------
    if args.acme:
        v = acme_view(store)
        if args.json:
            out(v)
            return 0
        print(pal.head('certificates by ACME: %s - %s, %s' % (
            'on' if v['on'] else 'off (otp --set acme=1)', v['directory'] or '-', v['challenge'])))
        rows = []
        for t in v['targets']:
            st_ = t.get('state') or {}
            left = (float(t['not_after']) - time.time()) / 86400 if t.get('not_after') else None
            rows.append((t['target'], t.get('name') or '(no name)', '%.0f days' % left if left is not None
                         else '-', 'ACME' if t.get('care') else 'by hand', (
                             ('ok ' if st_.get('ok') else 'failed ') + stamp(st_.get('at')) +
                             ('' if st_.get('ok') else ': %s' % (st_.get('said') or st_.get('error') or '')))
                         if st_.get('at') else 'never ordered'))
        print(table(rows, ['for', 'name', 'left', 'looked after', 'last order'], [10, 30, 9, 12, 60]))
        if v.get('account', {}).get('kid'):
            print('  account: %s, made %s' % (v['account'].get('email') or '(no mail)', stamp(v['account'].get('at'))))
        return 0

    if args.acme_order:
        if not CONFIG.get('acme'):
            raise SystemExit('otp: certificates by ACME are off - otp --set acme=1 (and acme_* ) first')
        # A process of its own has asked DNS nothing yet (1.0.262): fqdn_cached() gave the short
        # host name in its place, a certificate was ordered for "otp1" and ACME looked after it
        # from then on. DNS waited for here, and only a full name ordered.
        cli_fqdn_wait()
        if args.acme_order == 'all':
            which = acme_targets(store, answered=True)
            if not which:
                raise SystemExit('otp: this node looks after no certificate by ACME (otp --acme)')
        else:
            t = args.acme_order
            if t not in tls_targets(store) or (t == 'vip' and not vip_conf(store).get('address')):
                raise SystemExit('otp: there is no such certificate: %s' % ', '.join(tls_targets(store)))
            name = acme_name_of(store, t, answered=True)
            if not name:
                raise SystemExit('otp: the name of this certificate is not known - give it on the pages '
                                 '(Its name...) or otp --set acme_node_name=NAME --node %s' % t)
            if not cli_full_name(name):
                raise SystemExit('otp: %s is not a full DNS name (as otp1.example.com) - give the '
                                 'certificate\'s name on the pages (Its name...) or otp --set '
                                 'acme_node_name=NAME --node %s' % (name, t))
            # Ordered by hand, ACME looks after it from now on - as on the pages.
            acme_care_set(store, t, True, who, 'ordered by hand')
            which = [(t, name)]
        bad = 0
        for t, name in which:
            if not cli_full_name(name):
                bad += 1
                print(pal.bad_line('%s: %s is not a full DNS name (as otp1.example.com) - not ordered; '
                                   'give its name on the pages (Its name...) or otp --set '
                                   'acme_node_name=NAME --node %s' % (t, name, t)))
                continue
            print(pal.head('%s: %s' % (t, name)))
            try:
                cli_acme_order_one(store, t, name, who, lambda w: print('  ' + str(w)))
                print(pal.ok_line('the certificate of %s is made; the nodes put it in within a few '
                                  'seconds' % name))
            except (AcmeError, ValueError, OSError) as e:
                bad += 1
                print(pal.bad_line(str(e)))
        return 1 if bad else 0

    if args.updates:
        if args.updates == 'status':
            v = osup_view(store)
            if args.json:
                out(v)
                return 0
            plan = v.get('plan') or {}
            print(pal.head('updates of the operating system: %s' % (
                '%s, %s, by %s, %s' % (plan.get('state'), ', '.join(plan.get('order') or []),
                                        plan.get('by') or '-', stamp(plan.get('at')))
                if plan else 'none going on')))
            rows = []
            for n in v['nodes']:
                chk, row = n.get('check') or {}, n.get('row') or {}
                rows.append((n['name'] + (' (this)' if n['me'] else ''), 'up' if n['alive'] else 'not heard',
                             '%s, %s' % (chk.get('state') or '-', ('%s waiting' % chk['count']) if
                                         chk.get('count') is not None else '') if chk else 'not looked',
                             row.get('state') or '-', 'needed' if n.get('reboot') else '-'))
            print(table(rows, ['node', 'state', 'last look', 'this update', 'restart'], [22, 10, 26, 14, 8]))
            return 0
        nodes = [x.strip() for x in (args.node or '').split(',') if x.strip()] or None
        try:
            if args.updates == 'check':
                got = osup_check_ask(store, nodes or host_nodes(store), who)
                print(pal.ok_line('looking for updates on %s - otp --updates status in a minute'
                                  % ', '.join(got)))
            elif args.updates == 'start':
                cli_sure(args, 'the updates are put in on %s, one node at a time%s' % (
                    ', '.join(nodes or host_nodes(store)), {'auto': ', each restarted by itself '
                                                            'where an update needs it',
                                                            'never': ', none restarted'}.get(args.reboot, '')))
                plan = osup_start(store, nodes, args.reboot, who)
                print(pal.ok_line('the update starts: %s, one at a time - otp --updates status'
                                  % ', '.join(plan['order'])))
            else:
                osup_cancel(store, who)
                print(pal.ok_line('stopped - a node being updated finishes'))
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        return 0

    if args.restart_nodes:
        alln = host_nodes(store)
        nodes = alln if args.restart_nodes == 'all' else \
            [x.strip() for x in args.restart_nodes.split(',') if x.strip()]
        wrong = [n for n in nodes if n not in alln]
        if wrong:
            raise SystemExit('otp: there is no node %s (%s)' % (', '.join(wrong), ', '.join(alln)))
        cli_sure(args, 'the machines %s are restarted now, one at a time' % ', '.join(nodes))
        try:
            plan = power_ask(store, 'reboot', nodes, 'rolling' if len(nodes) > 1 else 'one', who)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('asked (%s) - otp --restarts says how it goes' % plan.get('id')))
        return 0

    if args.restarts:
        v = power_view(store)
        if args.json:
            out(v)
            return 0
        plan = v.get('plan') or {}
        print(pal.head('restarts: %s' % ('%s %s, %s, by %s, %s' % (
            plan.get('how'), ', '.join(plan.get('targets') or []), plan.get('order'),
            plan.get('by') or '-', stamp(plan.get('at'))) if plan else 'none of late')))
        print(table([(n['name'] + (' (this)' if n['me'] else ''), 'up' if n['alive'] else 'not heard',
                      stamp(n.get('started')) if n.get('started') else '-', odict(n.get('row')).get('state') or '-',
                      odict(n.get('row')).get('said') or '') for n in v['nodes']],
                    ['node', 'state', 'started', 'restart', 'said'], [22, 10, 20, 12, 60]))
        return 0

    if args.mail_test:
        to = args.mail_test.strip()
        if not re.match(r'^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+\Z', to):
            raise SystemExit('otp: a mail address to send it to')
        try:
            steps = mail_send(store, test_mail(to, code_lang()), [to])
        except MailError as e:
            store.add_event('mail', 'a test mail to %s failed: %s' % (to, e), 'warn', who=who)
            for st_ in getattr(e, 'steps', None) or []:
                print('  ' + (st_ if isinstance(st_, str) else json.dumps(st_, ensure_ascii=False)))
            print(pal.bad_line('not sent: %s' % e))
            return 1
        for st_ in steps or []:
            print('  ' + (st_ if isinstance(st_, str) else json.dumps(st_, ensure_ascii=False)))
        store.add_event('mail', '%s sent a test mail to %s' % (who, to), who=who)
        print(pal.ok_line('sent to %s' % to))
        return 0

    if args.sms_test:
        try:
            to = phone_checked(args.sms_test)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        try:
            said = sms_send(to, code_message('sms', to, code_new(), 'verify'))
        except SmsError as e:
            store.add_event('settings', 'a test SMS to %s failed: %s' % (to, e), 'warn', who=who)
            print(pal.bad_line('not sent: %s' % e))
            return 1
        store.add_event('settings', '%s sent a test SMS to %s' % (who, to), who=who)
        print(pal.ok_line('sent to %s%s' % (to, (': %s' % said) if said else '')))
        return 0

    if args.ssh_tokens:
        rows = sshotp_all(store)
        if args.json:
            out(rows)
            return 0
        print(table([(r['name'], {'app': 'the app'}.get(r['kind'], r['kind']) +
                      ((' to %s' % r['dest']) if r.get('dest') else ''), stamp(r.get('at')),
                      ('%s on %s' % (stamp(r['used_at']), r.get('used_on') or '?')) if r.get('used_at') else 'never',
                      r.get('note') or '') for r in rows],
                    ['account', 'codes from', 'made', 'last used', 'note'], [16, 30, 17, 28, 30]))
        return 0

    if args.ssh_token_add:
        had = sshotp_get(store, args.ssh_token_add)
        if had:
            cli_sure(args, 'the SSH token of %s in use is replaced, and stops working now'
                     % sshotp_name(args.ssh_token_add))
        try:
            got = sshotp_make(store, args.ssh_token_add, who, args.note or '', replace=bool(had),
                              kind=args.by or 'app', dest=args.to or '')
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        if got['kind'] != 'app':
            print(pal.ok_line('the SSH token of %s is made - its codes go to %s' % (got['name'], got['dest'])))
            return 0
        print(pal.head('the SSH token of %s - scan it now, it is not shown again' % got['name']))
        if not args.no_qr:
            print(QrCode(got['uri']).terminal(invert=args.invert))
        print('  key:      %s' % got['secret'])
        return 0

    if args.ssh_token_del:
        cli_sure(args, 'the SSH token of %s is taken away' % args.ssh_token_del)
        try:
            sshotp_remove(store, args.ssh_token_del, who)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('removed'))
        return 0

    if args.lockouts or args.lockouts_clear:
        now = time.time()
        per = []
        for n in [node_name()] + [x['name'] for x in ha_nodes(store) if x['name'] != node_name()]:
            got = json_obj(store.get_meta('lockouts:' + n)) or {}
            rows = [dict(r, node=n) for r in (got.get('rows') or []) if fnum(r.get('forgets')) > now]
            for r in rows:
                if r.get('locked') and fnum(r.get('until')) <= now:
                    r['locked'] = False
            per.append((n, got.get('at'), rows))
        shared = [dict(r, node='*') for r in lockouts_shared(store)]
        if args.lockouts_clear:
            asked = args.lockouts_clear
            if asked != 'all' and ':' not in asked:
                raise SystemExit('otp: --lockouts-clear all, or KIND:WHO as otp --lockouts shows them')
            kind, _, whom = asked.partition(':')
            n_done = 0
            for r in shared:
                if asked == 'all' or (r['kind'] == kind and r['who'].lower() == whom.lower()):
                    n_done += lockouts_shared_clear(store, r['kind'], r['who'], who) or 0
            # Each daemon clears its own within a few seconds (as the other node's pages ask).
            ask = {'all': 1, 'by': who} if asked == 'all' else {'key': [kind, whom], 'by': who}
            told = []
            for n, _at, rows in per:
                # As the shared ones, whatever the case (1.0.205); the node told
                # the name as it counts it.
                hit = [r for r in rows if r['kind'] == kind and r['who'].lower() == whom.lower()]
                if asked != 'all' and hit:
                    ask = {'key': [kind, hit[0]['who']], 'by': who}
                if asked == 'all' or hit:
                    try:
                        pending = json.loads(store.get_meta('lockouts:ask:' + n) or '[]')
                    except ValueError:
                        pending = []
                    store.set_meta('lockouts:ask:' + n, json.dumps(
                        (pending if isinstance(pending, list) else [])[-50:] + [ask]))
                    told.append(n)
            if not n_done and not told:
                raise SystemExit('otp: that is not counted any more')
            print(pal.ok_line('cleared%s' % ((' - %s within a few seconds' % ', '.join(told)) if told else '')))
            return 0
        allrows = shared + [r for _n, _a, rows in per for r in rows]
        if args.json:
            out(allrows)
            return 0
        print(table([(r['node'], '%s:%s' % (r['kind'], r['who']), r.get('what') or '',
                      '%d of %d' % (r.get('fails') or 0, r.get('limit') or 0),
                      ('locked until %s' % stamp(r['until'])) if r.get('locked') and r.get('until') else
                      ('locked' if r.get('locked') else 'counting')) for r in allrows],
                    ['node', 'kind:who', 'what', 'counted', 'state'], [10, 40, 30, 9, 30]))
        stale = [n for n, at, _r in per if not at or now - float(at) > 120]
        if stale:
            print(pal.dim('  not heard from of late: %s (its list may be old)' % ', '.join(stale)))
        return 0

    # ---- 1.0.188: the rest of what the pages do ----------------------------------------
    def api(method, path, body=None, qs=None):
        return cli_api(Daemon(store, serve=False), who, method, path, body, qs)

    def asked(kind, got, secs=90):
        if args.json:
            out(cli_ask_wait(store, kind, got, secs))
            return 0
        print(pal.dim('  asked of %s - each answers within seconds' % ', '.join(got['nodes'])))
        return cli_ask_said(pal, cli_ask_wait(store, kind, got, secs))

    def shown(got):
        if args.json:
            out(got)
        else:
            if isinstance(got, dict) and got.get('message'):
                print(pal.ok_line(got['message']))
                got = {k: v for k, v in got.items() if k != 'message'}
            cli_show(got, pal)
        return 0

    only = args.node or ''
    if args.siem_test:
        return asked('siem', api('POST', '/api/siem', {'action': 'test', 'node': only}))
    if args.proxy_test is not None:
        return asked('proxy', api('POST', '/api/proxy', {'action': 'try', 'url': args.proxy_test}), 60)
    if args.snmp_test or args.snmp_trap:
        return asked('snmp', api('POST', '/api/snmp', {'action': 'trap' if args.snmp_trap else 'test',
                                                      'node': only}))
    ca_pem = Path(args.ca).read_text() if args.ca else ''
    if args.db_tls:
        return shown(api('GET', '/api/dbtls'))
    if args.db_tls_probe:
        return asked('dbtls_probe', api('POST', '/api/dbtls', {
            'action': 'probe', 'mode': args.db_tls_probe, 'ca_source': args.db_tls_ca,
            'ca_pem': ca_pem, 'node': only}), 120)
    if args.db_tls_apply:
        mode = args.db_tls_mode if args.db_tls_mode is not None else 'verify-full'
        cli_sure(args, 'encryption to the database server, on %s: %s' % (only or 'every node', {
            'server': 'otp\'s certificates put into the PostgreSQLs (each reloaded)',
            'connect': 'each node\'s connection to its database made again with %s' % (mode or 'no TLS'),
            'server_off': 'otp\'s certificates taken out of the PostgreSQLs'}[args.db_tls_apply]))
        return asked('dbtls_apply', api('POST', '/api/dbtls', {
            'action': 'apply', 'phase': args.db_tls_apply, 'mode': mode, 'ca_source': args.db_tls_ca,
            'ca_pem': ca_pem, 'node': only}), 300)

    def host_port(v):
        host, _, port = str(v).rpartition(':') if re.match(r'^[^:]+:\d+$', str(v)) else (v, '', '')
        return {'host': host, 'port': int(port) if port else 6514}

    isemon_src = args.db_tls_ca if args.db_tls_ca in ('otp', 'system', 'given') else 'otp'
    if args.isemon_tls:
        got = api('GET', '/api/isemon')
        return shown(odict(got.get('tls')))
    if args.isemon_tls_probe:
        return asked('isemon_tls', api('POST', '/api/isemon', dict(
            host_port(args.isemon_tls_probe), action='tls_probe', ca_source=isemon_src,
            ca_pem=ca_pem, verify=not args.no_verify, mtls=args.mtls)), 60)
    if args.isemon_tls_apply:
        cli_sure(args, 'every node sends to isemon at %s over TLS from now on' % args.isemon_tls_apply)
        return shown(api('POST', '/api/isemon', dict(
            host_port(args.isemon_tls_apply), action='tls_apply', ca_source=isemon_src,
            ca_pem=ca_pem, verify=not args.no_verify, mtls=args.mtls)))
    if args.isemon_tls_off is not None:
        cli_sure(args, 'isemon is sent to over plain TCP (514) again - not encrypted')
        return shown(api('POST', '/api/isemon', {'action': 'tls_off', 'host': args.isemon_tls_off}))
    if args.isemon_tls_bundle:
        phrase = os.environ.get('OTP_PASSPHRASE') or ask_password(
            'a passphrase to lock the zip with (12 characters or more)', twice=True, env=None)
        got = api('POST', '/api/isemon', {'action': 'tls_bundle', 'port': 6514, 'mtls': args.mtls,
                                          'names': args.names or '', 'passphrase': phrase})
        fd = getattr(args, 'isemon_bundle_fd', None)
        if fd is None:
            fd = os.open(args.isemon_tls_bundle, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            os.fchmod(fd, 0o600)
        os.ftruncate(fd, 0)
        with os.fdopen(fd, 'wb') as f:
            f.write(base64.b64decode(got['file']))
        print(pal.ok_line('%s: isemon\'s certificate and key, locked with the passphrase given'
                          % args.isemon_tls_bundle))
        return 0
    target = args.tls_for or node_name()
    if args.tls_csr:
        got = api('POST', '/api/web', {'action': 'tls_csr', 'target': target, 'cn': args.tls_csr,
                                       'names': args.names or '', 'org': args.org})
        if args.json:
            out(got)
            return 0
        print(pal.ok_line(got.get('message') or 'made'))
        print(got.get('csr') or '')
        return 0
    if args.tls_selfsigned:
        cli_sure(args, 'a certificate of its own, made here, for %s - in place of the one it has' % target)
        return shown(api('POST', '/api/web', {'action': 'tls_selfsigned', 'target': target,
                                              'cn': args.tls_selfsigned, 'names': args.names or '',
                                              'days': args.days, 'org': args.org}))
    if args.tls_export:
        kind, path = args.tls_export
        if kind not in TLS_EXPORT_KINDS:
            raise SystemExit('otp: --tls-export %s FILE' % '|'.join(TLS_EXPORT_KINDS))
        body = {'action': 'tls_export', 'target': target, 'kind': kind, 'legacy': args.legacy}
        if TLS_EXPORT_KINDS[kind][2]:
            body['passphrase'] = os.environ.get('OTP_PASSPHRASE') or ask_password(
                'a password for the file (10 characters or more)', twice=True, env=None)
        got = api('POST', '/api/web', body)
        mode = 0o600 if TLS_EXPORT_KINDS[kind][2] else 0o644
        fd = getattr(args, 'tls_export_fd', None)
        if fd is None:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
            os.fchmod(fd, mode)
        os.ftruncate(fd, 0)
        with os.fdopen(fd, 'wb') as f:
            f.write(base64.b64decode(got['file']))
        print(pal.ok_line('%s: %s' % (path, TLS_EXPORT_KINDS[kind][0])))
        return 0
    if args.tls_forget:
        cli_sure(args, 'otp no longer looks after the TLS of %s; nginx keeps the files it has' % target)
        return shown(api('POST', '/api/web', {'action': 'tls_forget', 'target': target}))
    if args.ntp:
        return shown(api('GET', '/api/ntp'))
    if args.ntp_sync:
        return shown(api('POST', '/api/ntp', {'action': 'sync', 'node': only or node_name()}))
    if args.os_roots or args.os_roots_add or args.os_roots_remove:
        return cli_os_roots(args, pal, api, out)
    if args.net:
        return shown(api('GET', '/api/net'))
    if args.hisec:
        got = api('GET', '/api/hisec')
        if args.json:
            out(got)
            return 0
        print(pal.head('high security: %s' % ('on' if got.get('on') else 'off (otp --set high_security=1)')))
        for part, words in (('block', 'not kept'), ('waived', 'exceptions'), ('warn', 'to look at')):
            rows = got.get(part) or []
            if rows:
                print(pal.head('  %s (%d)' % (words, len(rows))))
                print(table([(r.get('rule'), r.get('title') or r.get('what'), r.get('fix') or '')
                             for r in rows], ['rule', 'what', 'put right by'], [18, 70, 40]))
        if not any(got.get(p) for p in ('block', 'waived', 'warn')):
            print(pal.ok_line('every rule kept'))
        return 0
    if args.hisec_waive:
        rule, on = args.hisec_waive
        if on not in ('on', 'off'):
            raise SystemExit('otp: --hisec-waive RULE on|off')
        return shown(api('POST', '/api/hisec', {'action': 'waive', 'rule': rule, 'on': on == 'on'}))
    if args.api:
        method = args.api[0].upper()
        if method not in ('GET', 'POST') or len(args.api) < 2:
            raise SystemExit('otp: --api GET|POST /api/... [BODY]')
        path, _, query = args.api[1].partition('?')
        body = None
        if len(args.api) > 2:
            raw = sys.stdin.read() if args.api[2] == '-' else args.api[2]
            try:
                body = json.loads(raw)
            except ValueError:
                raise SystemExit('otp: the body is JSON: {"action": "..."}')
            if not isinstance(body, dict):
                raise SystemExit('otp: the body is a JSON object')
            def keys(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        yield str(k)
                        yield from keys(v)
                elif isinstance(o, list):
                    for v in o:
                        yield from keys(v)
            # A setting known not to be one is not taken for a secret (1.0.207):
            # acme_key, admin_show_key, token_names_case were refused.
            secretish = [k for k in keys(body) if k in SECRET_KEYS or (re.search(
                r'pass|secret|token|key|pin', k, re.I) and not (k in DEFAULTS and k not in
                                                                SECRET_KEYS))]
            if args.api[2] != '-' and secretish:
                raise SystemExit('otp: %s - a secret is not taken written out on the command '
                                 'line: give the body through stdin (--api POST PATH -)'
                                 % ', '.join(sorted(set(secretish))))
        qs = dict(x.split('=', 1) if '=' in x else (x, '') for x in query.split('&') if x)
        got = cli_api(Daemon(store, serve=False), who, method, path,
                      body if method == 'POST' else None, qs)
        print(json.dumps(got, indent=1, ensure_ascii=False, default=str))
        return 0

    def daemon_here():
        try:
            os.kill(int((Path(STATE_DIR) / 'otp.lock').read_text().strip() or 0), 0)
            return True
        except (OSError, ValueError):
            return False

    if args.isemon_test and CONFIG.get('isemon') and daemon_here():
        # From every node, by each daemon's own sender (1.0.188), as the pages do.
        return asked('isemon', api('POST', '/api/isemon', {'action': 'test', 'node': only}), 60)
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
        return 1 if st['trouble'] else 0               # trouble said is a failure (1.0.205)

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


def _selinux_helper(extra, want, timeout=600):
    """The root helper of this machine run for SELinux, what otp needs given on stdin."""
    helper = Path(__file__).resolve().parent / 'otp_web.py'
    if not helper.exists():
        helper = Path('/usr/local/lib/otp/otp_web.py')
    if not helper.exists():
        raise SystemExit('otp: the root helper (otp_web.py) is not installed')
    return subprocess.run(['/usr/bin/python3', '-I', str(helper)] + extra, input=want or '{}',
                          capture_output=True, text=True, timeout=timeout)


def cli_selinux(args, pal):
    """otp --selinux-check, --selinux STEP, --selinux-report (1.0.233, 1.0.236): as root - the
    root helper does it, what otp needs read first as the service."""
    if os.geteuid() != 0:
        raise SystemExit('otp: SELinux is root\'s - run it as root')
    try:
        want = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--selinux-want'],
                              capture_output=True, text=True, timeout=120).stdout.strip()
        json.loads(want or '{}')
    except (OSError, subprocess.SubprocessError, ValueError):
        want = '{}'
    if args.selinux_report is not None:
        node = re.sub(r'[^A-Za-z0-9._-]', '', node_name())[:60] or 'node'
        out = args.selinux_report or '/root/otp-selinux-report-%s-%s.tar.gz' % (
            node, time.strftime('%Y%m%d-%H%M'))
        print(pal.dim('gathering what SELinux says here - a minute or two (ausearch, semanage)...'))
        got = _selinux_helper(['--selinux-report', out], want, 1200)
        sys.stderr.write(got.stderr)
        if got.returncode != 0:
            return got.returncode
        print(pal.ok_line('the report is in %s (%d kB)' % (out, os.path.getsize(out) >> 10)))
        print('  look through avc*.txt in it before sending it on: the audit log holds the command '
              'lines of the programs SELinux refused something to')
        return 0
    step = args.selinux or 'check'
    if step == 'check':
        got = _selinux_helper(['--selinux-check', '--want-stdin'] + (['--json'] if args.json else []),
                              want)
    else:
        if step == 'permissive':
            # Refused under high security from here too (1.0.252), as on the pages since 1.0.249:
            # the service's own reading of it, given with what otp needs.
            try:
                hs = bool(json.loads(want or '{}').get('high_security'))
            except ValueError:
                hs = False
            if hs or _hs_on():
                raise SystemExit('otp: high security is on: SELinux is not switched to permissive - '
                                 'switch high security off first')
        words = {'prepare': 'SELinux permissive at the next start of this machine, every file '
                            'labelled then (the machine is not restarted now)',
                 'apply': 'otp\'s module, the labels of its files, the booleans and ports it needs '
                          'put in (still permissive)',
                 'enforce': 'SELinux ENFORCING on this machine, now and after a restart',
                 'permissive': 'SELinux permissive on this machine, now and after a restart'}[step]
        if not args.yes:
            if not sys.stdin.isatty():
                raise SystemExit('otp: %s - add --yes to do it without a terminal' % words)
            if input('%s. Go on? [y/N] ' % words).strip().lower() not in ('y', 'yes'):
                print('nothing done')
                return 1
        got = _selinux_helper(['--selinux-do', step] + (['--json'] if args.json else []), want)
    sys.stdout.write(got.stdout)
    sys.stderr.write(got.stderr)
    return got.returncode


CLI_STARTED_ROOT = os.geteuid() == 0


def cli_who():
    """Who did it, for the events: the command line - and, run through sudo (the console of a
    normal user, 1.0.240), whose sudo it was."""
    by = os.environ.get('SUDO_USER') or ''
    # Root when it was started (1.0.249): most commands become the otp account before they act.
    if CLI_STARTED_ROOT and by and by != 'root' and re.match(r'^[A-Za-z_][A-Za-z0-9_.-]{0,31}$', by):
        return 'command line (sudo %s)' % by
    return 'command line'


def cli_get(store, args):
    """otp --get KEY... (1.0.244): the settings as they are in effect on this node - the counterpart
    of --set. A secret is never shown, only whether it is set."""
    bad = [k for k in args.get if k not in DEFAULTS]
    if bad:
        import difflib
        near = []
        for b in bad:
            near += [k for k in difflib.get_close_matches(b.lower(), list(DEFAULTS), 3, 0.6)
                     if k not in near]
            near += sorted(k for k in DEFAULTS if b.lower() in k and k not in near)[:5]
        print('otp: no such setting: %s%s' % (', '.join(bad), (' - did you mean: ' + ', '.join(near))
                                              if near else ' (otp --settings lists them)'),
              file=sys.stderr)
        return 2
    Daemon(store, serve=False)              # the settings saved on the pages read in, as --settings
    got = {}
    for k in args.get:
        v = CONFIG.get(k)
        got[k] = ('set' if v else 'not set') if k in SECRET_KEYS else v
    if args.json:
        print(json.dumps(got, ensure_ascii=False, default=str))
        return 0

    def plain(v):
        if isinstance(v, bool):
            return '1' if v else '0'
        if v is None:
            return ''
        if isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False, default=str)
        return str(v)
    if len(args.get) == 1:
        print(plain(got[args.get[0]]))
    else:
        for k in args.get:
            print('%s=%s' % (k, plain(got[k])))
    return 0


def cli_pwpolicy(args, pal):
    """otp --local-policy [KEY=VALUE...] (1.0.245): the password policy of the local users."""
    store = cli_store()
    if args.local_policy_set:
        b = dict(pwp_conf(store))
        for w in args.local_policy_set:
            if '=' not in w:
                print('KEY=VALUE, e.g. minlen=12')
                return 2
            k, v = w.split('=', 1)
            if k not in PWP_DEFAULT:
                print('no such rule: %s (%s)' % (k, ', '.join(sorted(PWP_DEFAULT))))
                return 2
            b[k] = v.strip().lower() in ('1', 'yes', 'on', 'true') if k in ('managed', 'existing') else v
        try:
            c = pwp_checked_api(b)
        except ValueError as e:
            print('refused: %s' % e)
            return 1
        store.set_meta('host:pwpolicy:conf', json.dumps(dict(c, at=time.time(), by=cli_who())))
        store.add_event('settings', '%s %s the password policy of the local users' % (
            cli_who(), 'set' if c['managed'] else 'gave back to the system'), 'warn', who=cli_who())
        print('saved - each node puts it in within a few seconds')
    c = pwp_conf(store)
    print('the password policy of the local users: %s' % ('set by otp on every node' if c['managed']
                                                          else "each node's system's own (nothing written)"))
    if c['managed']:
        print('  at least %d characters, %d kind(s); the same in a row at most %s; %d not in the old one;'
              ' dictionary %s; the name %s' % (c['minlen'], c['minclass'], c['maxrepeat'] or 'any',
                                               c['difok'], 'refused' if c['dictcheck'] else 'taken',
                                               'refused' if c['usercheck'] else 'taken'))
        print('  good for %s; warned %d days before; %d days at least between two; the last %d not again'
              % ('%d days' % c['max_days'] if c['max_days'] < 99999 else 'ever', c['warn_days'],
                 c['min_days'], c['remember']))
        print('  %s' % ('locked after %d wrong for %d s (counted within %d s)' % (
            c['deny'], c['unlock_time'], c['fail_interval']) if c['deny'] else 'never locked for wrong passwords'))
    v = osu_view(store)
    for n in v['nodes']:
        p = n.get('policy') or {}
        state = ('not answering' if not n['alive'] else 'refused: ' + n['policy_error'] if n.get('policy_error')
                 else 'as set' if n.get('policy_applied') else 'being put in')
        print('%s: %s' % (n['name'], state))
        if p.get('pwquality'):
            q = p['pwquality']
            pam = p.get('pam') or {}
            print('  in effect: minlen %s, minclass %s, maxrepeat %s, dictcheck %s; remember %s; good for %s days;'
                  ' faillock deny %s; PAM: pwquality %s, pwhistory %s, faillock %s%s' % (
                      q.get('minlen'), q.get('minclass'), q.get('maxrepeat'), q.get('dictcheck'), p.get('remember'),
                      odict(p.get('aging')).get('max_days'), odict(p.get('faillock')).get('deny'),
                      'yes' if pam.get('pwquality') else 'no', 'yes' if pam.get('pwhistory') else 'no',
                      'yes' if pam.get('faillock') else 'no',
                      ('; authselect ' + p['authselect']['profile']) if p.get('authselect') else ''))
    return 0


def cli_osusers(args, pal):
    """otp --local-users, --local-user WHAT NAME (1.0.243): Settings -> Local users. The change is
    asked as from the pages - each node's daemon has its root helper do it."""
    import getpass
    store = cli_store()
    who = cli_who()
    every = host_nodes(store)
    nodes = [n.strip() for n in str(args.local_nodes or '').split(',') if n.strip()] or every
    bad = [n for n in nodes if n not in every]
    if bad:
        print('no such node: %s (the nodes: %s)' % (', '.join(bad), ', '.join(every)))
        return 2

    def settle(secs=60, since=None):
        # A list asked is waited for too (1.0.248): it is no change, never "pending" - the row
        # read was the old one, or none yet.
        end = time.time() + secs
        while time.time() < end:
            v = osu_view(store)
            mine = [n for n in v['nodes'] if n['name'] in nodes]
            if not any(n['pending'] for n in mine) and (
                    since is None or all(fnum(n.get('at')) >= since for n in mine if n['alive'])):
                return v
            time.sleep(1)
        return osu_view(store)

    if args.local_user:
        what, name = args.local_user
        f = {'name': name}
        do = {'add': 'add', 'password': 'password', 'lock': 'lock', 'unlock': 'unlock',
              'sudo-on': 'sudo', 'sudo-off': 'sudo', 'drop': 'drop', 'drop-home': 'drop',
              'aging': 'aging'}.get(what)
        if not do:
            print('add, password, lock, unlock, sudo-on, sudo-off, drop, drop-home or aging')
            return 2
        if do == 'aging':
            for k in ('max_days', 'min_days', 'warn_days'):
                v = getattr(args, 'local_' + k)
                if v is not None:
                    f[k] = v
            if len(f) == 1:
                print('--local-max-days, --local-min-days or --local-warn-days')
                return 2
        if do in ('add', 'password'):
            if not sys.stdin.isatty():
                print('the password is asked at a terminal only - never given on the command line')
                return 2
            one = getpass.getpass('the password for %s%s: ' % (name, ' (empty: none - a key only)'
                                                               if do == 'add' else ''))
            if one or do == 'password':
                if getpass.getpass('again: ') != one:
                    print('the two passwords are not the same - nothing done')
                    return 1
            f['password'] = one
            f['must_change'] = bool(args.local_must_change)
        if do == 'add':
            if args.local_full_name is not None:
                f['gecos'] = args.local_full_name
            f['shell'] = args.local_shell or '/bin/bash'
        if do == 'sudo':
            f['on'] = what == 'sudo-on'
        if do == 'drop':
            f['home'] = what == 'drop-home'
            if sys.stdin.isatty() and input('take %s away on %s%s? type yes: ' % (
                    name, ', '.join(nodes), ' with the home folder' if f['home'] else '')).strip() != 'yes':
                print('nothing done')
                return 1
        try:
            t0 = time.time()
            osu_ask(store, nodes, 'list', who)
            settle(30, t0)                  # what each node has, read first (the UID)
            done = osu_ask(store, nodes, do, who, **f)
        except ValueError as e:
            print(pal.bad('refused: %s' % e) if hasattr(pal, 'bad') else 'refused: %s' % e)
            return 1
        print('asked of %s - waiting for each node...' % ', '.join(done))
        v = settle()
        rc = 0
        for n in v['nodes']:
            if n['name'] not in done:
                continue
            last = [x for x in n.get('said') or [] if x.get('name') == name][-1:]
            if n['pending']:
                print('  %s: not done yet (is otp running there?)' % n['name'])
                rc = 1
            elif last:
                print('  %s: %s%s' % (n['name'], 'done' if last[0]['ok'] else 'refused',
                                      (' - ' + last[0]['said']) if last[0].get('said') else ''))
                rc = rc or (0 if last[0]['ok'] else 1)
        return rc
    t0 = time.time()
    osu_ask(store, nodes, 'list', who)
    v = settle(30, t0)
    for n in v['nodes']:
        if n['name'] not in nodes:
            continue
        print('%s%s%s' % (n['name'], '' if n['alive'] else ' (not answering)',
                          (' - ' + n['error']) if n.get('error') else ''))
        if not n.get('at'):
            print('  not read yet')
            continue
        for u in n['users']:
            if not u.get('login') and not u.get('root'):
                continue
            tags = []
            if u.get('root'):
                tags.append('view only')
            if u.get('sudo') and not u.get('root'):
                tags.append('sudo')
            if u.get('locked'):
                tags.append('locked')
            tags.append('password: ' + ('none' if not u.get('password') else 'to change at sign-in'
                                        if u.get('must_change') else 'set'))
            print('  %-20s UID %-6s %-16s %s%s' % (u['name'], u['uid'], u.get('shell') or '-',
                                                   ', '.join(tags),
                                                   ('  (' + u['gecos'] + ')') if u.get('gecos') else ''))
        others = sum(1 for u in n['users'] if not u.get('login') and not u.get('root'))
        if others:
            print('  and %d account(s) with no shell' % others)
    return 0


def cli_sso(args, pal):
    """otp --sso-status, --sso-key (1.0.239): the sign-in by a load balancer or WAF."""
    store = cli_store()
    if args.sso_key:
        if not args.yes and sys.stdin.isatty():
            got = input('a new key: the one the balancer sends now is no longer taken. Go on? [y/N] ')
            if got.strip().lower() not in ('y', 'yes'):
                print('nothing changed')
                return 1
        tok = secrets.token_urlsafe(32)
        d = Daemon(store, serve=False)
        try:
            d.save_settings({'portal_sso_key': tok}, by='root on %s' % node_name())
        except (BadSetting, OSError) as e:
            raise SystemExit('otp: %s' % e)
        store.add_event('settings', 'root on %s made a new key for the sign-in by the load '
                        'balancer - the one before is no longer taken' % node_name(), 'warn')
        if args.json:
            print(json.dumps({'key': tok}))
        else:
            print(pal.ok_line('the new key - shown only now; the balancer sends it in %s:'
                              % SSO_KEY_HEADER))
            print(tok)
        return 0
    v = sso_view(store)
    if args.json:
        print(json.dumps(v))
        return 0
    print(pal.ok_line('signed in by the load balancer on the enrolment pages: %s'
                      % ('ON' if v['on'] else 'off')))
    print('  the balancers:   %s' % (', '.join(v['from']) or '(none named)'))
    print('  the header:      %s   (with the key in %s: %s)'
          % (v['header'], v['key_header'], 'set' if v['key_set'] else 'NOT SET - otp --sso-key'))
    print('  signing out:     %s' % (v['logout'] or '(the sign-in of these pages)'))
    if v['on'] and not v['web_proxy']:
        print('  note: "Behind a load balancer or WAF" is off - every client is the balancer\'s '
              'address (otp --set web_proxy_from=ADDR --set web_proxy=1)')
    for x in v['last']:
        print('  last on %-10s %s  %-9s %s <- %s%s' % (
            x.get('node') or '?', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(fnum(x.get('at')))),
            'signed in' if x.get('ok') else 'REFUSED', x.get('name') or '?', x.get('peer') or '?',
            ('  (%s)' % x['why']) if x.get('why') else ''))
    if not v['last']:
        print('  no sign-in by the balancer seen yet')
    return 0


def cli_dir_guard(args, pal):
    """otp --dir-caps, --dir-cap, --dir-policy, --dir-sample, --guard-status (1.0.236)."""
    store = cli_store()
    by = 'root on %s' % node_name()
    if args.guard_status:
        on = bool(CONFIG.get('db_guard'))
        bad = []
        if on:
            for r in store.db.rows('SELECT k, v FROM meta'):
                if dbguard_meta_kept(r['k']) and not dbguard_ok(store.db, 'm', r['k'], r['v'], quiet=True):
                    bad.append(('meta', r['k']))
            for r in store.db.rows('SELECT k, v FROM settings'):
                if dbguard_setting_kept(r['k']) and not dbguard_ok(store.db, 's', r['k'], r['v'], quiet=True):
                    bad.append(('setting', r['k']))
            for r in store.db.rows('SELECT * FROM accounts'):
                if not dbguard_account_ok(store.db, r):
                    bad.append(('account', r['name']))
            for r in store.db.rows('SELECT * FROM directories'):
                if not dbguard_directory_ok(store.db, r['name']):
                    bad.append(('directory', r['name']))
        if args.json:
            print(json.dumps({'on': on, 'not_otps': [{'kind': k, 'what': w} for k, w in bad]}))
            return 0
        print(pal.ok_line('the guard against writes to the database is %s on %s' % (
            'ON' if on else 'off', node_name())))
        if on:
            print(('  %d row(s) that reach root are not as otp wrote them - not acted on:' % len(bad))
                  if bad else '  every row that reaches root is as otp wrote it')
            for k, w in bad[:200]:
                print('    %-9s %s' % (k, w))
        return 0
    if args.dir_cap:
        want = {}
        for spec in args.dir_cap:
            name, _, rule = spec.partition('=')
            rule = rule.strip().lower()
            if rule == 'setting':
                want[name.strip()] = {'tries': None, 'window_min': None}
            elif rule == 'none':
                want[name.strip()] = {'tries': 0}
            else:
                m = re.match(r'^(\d+)(?:/(\d+))?$', rule)
                if not m or int(m.group(1)) < 1:
                    raise SystemExit('otp: --dir-cap NAME=3/30, NAME=setting or NAME=none')
                want[name.strip()] = {'tries': int(m.group(1)), 'window_min': int(m.group(2)) if m.group(2) else None}
        try:
            said = dir_pw_caps_set(store, want, by)
        except ValueError as e:
            raise SystemExit('otp: %s' % e)
        print(pal.ok_line('saved: %s' % '; '.join(said)) if said else 'nothing changed')
        return 0
    if args.dir_policy or args.dir_sample:
        name = args.dir_policy or args.dir_sample[0]
        row = next((d for d in store.directories(with_secret=True)
                    if d['name'].lower() == str(name).lower()), None)
        if not row:
            raise SystemExit('otp: there is no directory called %s' % name)
        ad = Directory(row)
        try:
            if args.dir_policy:
                pol = dir_policy_read(store, ad)
                if args.json:
                    print(json.dumps(pol))
                    return 0
                lo, pw = pol.get('lockout') or {}, pol.get('password') or {}
                print(pal.ok_line('%s - %s' % (ad.name, pol.get('name') or ad.base)))
                print('  lockout: %s wrong passwords, counted over %s s, locked %s' % (
                    lo.get('threshold') or 'never', lo.get('window_s'), lo.get('duration_s')))
                print('  passwords: at least %s characters, complex %s, %s remembered' % (
                    pw.get('min_length'), 'yes' if pw.get('complex') else 'no', pw.get('history')))
                for p in pol.get('psos') or []:
                    print('  fine-grained %s: locks after %s' % (p.get('name'), p.get('threshold') or 'never'))
                rec = pol.get('recommend') or {}
                print(pal.ok_line('recommended: %s wrong passwords in %s min - %s' % (
                    rec.get('tries'), rec.get('window_min'), rec.get('why'))))
                print('  otp --dir-cap %s=%s/%s   puts it in' % (ad.name, rec.get('tries'), rec.get('window_min')))
                return 0
            got = dir_sample_of(ad, args.dir_sample[1])
        except (LdapError, LookupError) as e:
            raise SystemExit('otp: %s' % e)
        store.add_event('directories', '%s looked at every attribute of %s in %s' % (by, got['dn'], ad.name), who=by)
        if args.json:
            print(json.dumps(got))
            return 0
        print(pal.ok_line('%s%s' % (got['dn'], ' (more than one answers to that name)' if got.get('many') else '')))
        for a in got['attrs']:
            mark = 'mail ' if a['mail'] else ('phone' if a['phone'] else '     ')
            print('  %s %-32s %s' % (mark, a['name'], '(binary)' if a['binary'] else
                                     ' | '.join(a['values'])[:120]))
        print('  used now: mail %s; mobile %s' % (row.get('mail_attr') or got['defaults']['mail'],
                                                   row.get('mobile_attr') or got['defaults']['mobile']))
        return 0
    got = dir_pw_caps_list(store)
    if args.json:
        print(json.dumps(got))
        return 0
    st = got['setting']
    print(pal.ok_line('the setting: %s' % ('no cap' if not st['tries'] else
                                           '%d wrong passwords in %d min' % (st['tries'], st['window_min']))))
    if not CONFIG.get('radius_guard'):
        # One switch for the guessing guards (1.0.241).
        print(pal.warn_line('not in use: "Block a place that keeps guessing" is off - no cap is applied '
                            '(otp --set radius_guard=1)'))
    for d in got['directories']:
        own = 'as the setting' if d['tries'] is None else ('no cap' if d['tries'] == 0 else
                                                          '%d in %s min' % (d['tries'], d['window_min'] or st['window_min']))
        pol = d.get('policy') or {}
        lo = pol.get('lockout') or {}
        print('  %-20s %-18s %s%s' % (d['name'], own, ('domain locks after %s' % (lo.get('threshold') or 'never'))
                                      if pol else 'policy not read (otp --dir-policy %s)' % d['name'],
                                      '' if d['enabled'] else '  (switched off)'))
    return 0


def _early_hup(*_):
    try:
        run_dir_keep()          # systemctl reload while it starts (1.0.232)
    except Exception:           # noqa: BLE001
        pass
    HUP_ASKED.set()


def run_daemon():
    signal.signal(signal.SIGHUP, _early_hup)
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
        try:
            net_local_trial_lost()      # a network on trial cut it off from it (1.0.249)
        except Exception:                               # noqa: BLE001
            pass
        raise SystemExit(1)
    load_config(saved=dbguard_settings(store.settings_saved(), store))
    log_open()
    made = False
    if not store.accounts():
        pw = secrets.token_urlsafe(12)
        try:
            store.add_account('admin', 'fulladmin', pw, note='made on the first start',
                              must_change=1)
            made = True
        except Exception as e:                          # noqa: BLE001
            # Two nodes started together on one new database (1.0.225): the other made it
            # a moment before - not a reason to stop.
            if not store.accounts():
                raise
            log('the first account was made by another node meanwhile (%s)' % str(e)[:120], 'info')
    if made:
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
