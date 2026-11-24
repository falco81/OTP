"""1.0.331 (parts): the console's live RADIUS view shows both nodes' requests; keys of curses
(Shift+Tab, Insert, F1...) no longer typed as letters; events written on the command line and
the console sent to the SIEM and isemon as well."""
import sys, pathlib
P = pathlib.Path(sys.argv[1])


def edit(name, pairs):
    p = P / name
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (name, n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit('96_console.py', [
("""        q = collections.deque()
        state = {'seen': None, 'stop': False}
""",
 """        q = collections.deque()
        # A place in the log for each node (1.0.331): each node numbers its rows on its own (odd,
        # even) - one place for both hid the quieter node's requests, as the alerts did (1.0.262).
        state = {'seen': None, 'stop': False}
"""),
("""                for r in rows:
                    if state['seen'] is not None and (r.get('id') or 0) <= state['seen']:
                        continue
                    q.append(one(r))
                    state['seen'] = max(state['seen'] or 0, r.get('id') or 0)
                if state['seen'] is None:
                    state['seen'] = 0
""",
 """                first = state['seen'] is None
                seen = state['seen'] if not first else {}
                for r in rows:
                    node = str(r.get('node') or '')
                    if not first and (r.get('id') or 0) <= seen.get(node, 0):
                        continue
                    q.append(one(r))
                    seen[node] = max(seen.get(node, 0), r.get('id') or 0)
                state['seen'] = seen
"""),
("""                 127: 'bs', 8: 'bs', c.KEY_DC: 'del', c.KEY_RESIZE: 'resize', 21: 'ctrl-u',
                 9: 'tab'}
""",
 """                 127: 'bs', 8: 'bs', c.KEY_DC: 'del', c.KEY_RESIZE: 'resize', 21: 'ctrl-u',
                 9: 'tab', getattr(c, 'KEY_BTAB', 353): 'up'}
"""),
("""        if 32 <= k < 0x110000:
            try:
                return chr(k)
            except ValueError:
                return None
        return None

    def _line_in(""",
 """        # A byte, never a key of curses (1.0.331): Shift+Tab (353) was typed as "š", Insert as
        # "ŋ" - into a shared secret entered once, every request of that client then refused.
        if 32 <= k < 256:
            return chr(k)
        return None

    def _line_in("""),
])

edit('80_daemon.py', [
("""def names_nfc_asked(store):
""",
 """CLI_EVENTS_FILE = RUN_DIR / 'cli-events.jsonl'
CLI_EVENTS_MOST = 256 * 1024


def cli_event_spool(kind, words, level='info', who=''):
    \"\"\"An event written on the command line (the console too) put by for the daemon to send to
    the SIEM and isemon (1.0.331): only the daemon sends, and it was told of its own events
    alone - a password set, an account removed, the cluster paused on the console went nowhere.\"\"\"
    import fcntl
    line = (json.dumps({'kind': str(kind), 'words': str(words), 'level': str(level or 'info'),
                        'who': str(who or '')}, ensure_ascii=False) + '\\n').encode('utf-8')
    try:
        fd = os.open(str(CLI_EVENTS_FILE), os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                     0o660)
    except OSError:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if os.fstat(fd).st_size + len(line) <= CLI_EVENTS_MOST:
            os.write(fd, line)
    except OSError:
        pass
    finally:
        os.close(fd)


def cli_events_take():
    \"\"\"[(kind, words, level, who)] put by on the command line, the file emptied (1.0.331).\"\"\"
    import fcntl
    try:
        fd = os.open(str(CLI_EVENTS_FILE), os.O_RDWR | os.O_NOFOLLOW)
    except OSError:
        return []
    data = b''
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        while True:
            got = os.read(fd, 65536)
            if not got:
                break
            data += got
        if data:
            os.ftruncate(fd, 0)
    except OSError:
        return []
    finally:
        os.close(fd)
    out = []
    for raw in data.splitlines():
        try:
            e = json.loads(raw.decode('utf-8'))
            out.append((str(e['kind']), str(e['words']), str(e.get('level') or 'info'),
                        str(e.get('who') or '')))
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return out


def names_nfc_asked(store):
"""),
("""                try:
                    names_nfc_asked(self.store)  # the other node put a copy back (1.0.327)
""",
 """                try:
                    hook = getattr(self.store, 'on_event', None)
                    if hook and getattr(self, 'siem', None) is not None:
                        for one in cli_events_take():   # the command line's events (1.0.331)
                            hook(*one)
                except Exception as e:          # noqa: BLE001
                    log_sparing('cli-events', 'the command line\\'s events: %s' % e, 'warn', every=600)
                try:
                    names_nfc_asked(self.store)  # the other node put a copy back (1.0.327)
"""),
])

edit('95_cli.py', [
("""    store = Storage(db, quick=True)
    _cli_name_held()
""",
 """    store = Storage(db, quick=True)
    # Its events to the SIEM and isemon too, through the daemon (1.0.331).
    store.on_event = cli_event_spool
    _cli_name_held()
"""),
])
