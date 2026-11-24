"""t_fix.py - 1.0.331: the console's live RADIUS view keeps a place for each node; curses keys not
typed as letters; the command line's events put by for the daemon to send to the SIEM and isemon.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, subprocess, sys, tempfile, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.331'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r331_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx331', 'api_port': 29954}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)

# ==== 1 the spool
ok('the spool is in the run folder', str(m.CLI_EVENTS_FILE) == D + '/run/cli-events.jsonl')
ok('nothing to take at first', m.cli_events_take() == [])
m.cli_event_spool('accounts', 'the password of Žofie was set on the command line', 'info', 'root')
m.cli_event_spool('cluster', 'paused', 'warn', '')
got = m.cli_events_take()
ok('taken in order, words as written', got == [('accounts', 'the password of Žofie was set on the command line', 'info', 'root'),
                                               ('cluster', 'paused', 'warn', '')], got)
ok('emptied once taken', m.cli_events_take() == [] and os.path.getsize(m.CLI_EVENTS_FILE) == 0)
with open(m.CLI_EVENTS_FILE, 'ab') as f:
    f.write(b'not json\n{"kind": "x"}\n')
m.cli_event_spool('k', 'w')
ok('a broken line passed over', m.cli_events_take() == [('k', 'w', 'info', '')])
big = 'x' * 3000
for _ in range(200):
    m.cli_event_spool('k', big)
ok('the spool has a most', os.path.getsize(m.CLI_EVENTS_FILE) <= m.CLI_EVENTS_MOST)
m.cli_events_take()
os.unlink(m.CLI_EVENTS_FILE)
os.symlink(TOP + '/elsewhere', m.CLI_EVENTS_FILE)
m.cli_event_spool('k', 'w')
ok('a link in its place not followed', not os.path.exists(TOP + '/elsewhere'))
os.unlink(m.CLI_EVENTS_FILE)

# cli_store's Storage tells the spool
src = open(V + '/otp.py').read()
ok('cli_store hooks the spool', 'store.on_event = cli_event_spool' in src[src.index('def cli_store'):src.index('def half_joined_words')])
st = m.Storage(m.open_db()); st.db.make_tables()
st.on_event = m.cli_event_spool
st.add_event('accounts', 'made on the command line', who='root')
ok('add_event on the command line reaches the spool', m.cli_events_take() == [('accounts', 'made on the command line', 'info', 'root')])

# the daemon takes them only where it sends
loop = src[src.index('for one in cli_events_take():') - 300:src.index('for one in cli_events_take():')]
ok('the daemon takes them where it has a SIEM', "getattr(self, 'siem', None) is not None" in loop)


# ==== 2 keys
class FakeCurses(object):
    KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT = 259, 258, 260, 261
    KEY_PPAGE, KEY_NPAGE, KEY_HOME, KEY_END = 339, 338, 262, 360
    KEY_ENTER, KEY_BACKSPACE, KEY_DC, KEY_RESIZE, KEY_BTAB = 343, 263, 330, 410, 353
    error = Exception


class Win(object):
    def __init__(self, keys):
        self.keys = list(keys)

    def getch(self):
        return self.keys.pop(0) if self.keys else -1

    def nodelay(self, x):
        pass


con = m.Console.__new__(m.Console)
con.curses = FakeCurses()
key = lambda *ks: con._getkey(Win(ks))
ok('Shift+Tab is back a field, not "š"', key(353) == 'up', key(353))
ok('Insert is nothing, not "ŋ"', key(331) is None, key(331))
ok('F1 is nothing', key(265) is None)
ok('a letter is a letter', key(ord('a')) == 'a')
ok('UTF-8 "ž" as two bytes', key(0xc5, 0xbe) == 'ž', key(0xc5, 0xbe))
ok('Tab, Enter, arrows as before', key(9) == 'tab' and key(10) == 'enter' and key(259) == 'up')

# ==== 3 the live view: a place for each node
lr = src[src.index('    def live_radius'):src.index('    def live_radius') + 3000]
ok('live view keeps a place for each node', "seen.get(node, 0)" in lr and "seen[node] = max(" in lr)


# run its poll for real: a stand-in for --log, two nodes numbering on their own
class Stop(Exception):
    pass


calls = []
answers = [
    [{'id': 1200, 'node': 'b', 'result': 'accept'}, {'id': 4999, 'node': 'a', 'result': 'accept'},
     {'id': 5001, 'node': 'a', 'result': 'accept'}],
    [{'id': 1200, 'node': 'b'}, {'id': 4999, 'node': 'a'}, {'id': 5001, 'node': 'a'},
     {'id': 1202, 'node': 'b', 'result': 'reject'}, {'id': 5003, 'node': 'a', 'result': 'accept'}],
]
con.pal = m.Pal(False) if hasattr(m, 'Pal') else None


class P(object):
    def __getattr__(self, n):
        return lambda x: str(x)


con.pal = P()
shown = []


def fake_out(*a):
    calls.append(a)
    if not answers:
        raise Stop()
    return {'rows': answers.pop(0)}


con.out = fake_out
import threading as _th
_real = _th.Thread


class T(object):
    def __init__(self, target=None, **kw):
        self.t = target

    def start(self):
        try:
            self.t()
        except Stop:
            pass


m.threading.Thread = T
_sleep = m.time.sleep
m.time.sleep = lambda s: None
import collections as _co
_dq = m.collections.deque
q_seen = []


class DQ(_dq):
    def append(self, x):
        q_seen.append(x)
        _dq.append(self, x)


m.collections.deque = DQ
try:
    con.live_radius()
except Exception:
    pass
finally:
    m.threading.Thread = _real
    m.time.sleep = _sleep
    m.collections.deque = _dq
ok('the live view shows the quieter node\'s new request', len(q_seen) == 5 and '1202' not in str(q_seen[:3]),
   q_seen)
print('ALL %d / %d' % (sum(R), len(R)))
