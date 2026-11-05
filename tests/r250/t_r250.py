#!/usr/bin/env python3
"""1.0.250: rows of another shape put right, not raised at every tick; rows signed only since a
version taken in once every node runs it; old asks to back up now gone, never logged for ever.

Run as root: python3 t_r250.py VERSION"""
import os, sys, json, time, tempfile, atexit, shutil, threading

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.250'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:300] if more and not c else ''), flush=True)


TOP = tempfile.mkdtemp(prefix='otp-r250-')
atexit.register(lambda: shutil.rmtree(TOP, ignore_errors=True))
os.environ['OTP_STATE'] = TOP + '/dstate'; os.makedirs(TOP + '/dstate')
open(TOP + '/dstate/guard.json', 'w').write('{}')
sys.path.insert(0, V); sys.argv = ['otp']
import otp
otp.CONFIG.update({'db_engine': 'sqlite', 'node_name': 'nodea'})
store = otp.Storage(otp.open_db()); store.db.make_tables(); otp.sealing_key(make=True)
import pathlib; otp.WEB_DIR = pathlib.Path(TOP + '/web'); otp.WEB_DIR.mkdir()


def raw(k, v):
    store.db.run('DELETE FROM meta WHERE k = ?', (k,))
    store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, v))


class D:
    def __init__(self):
        self.store = store


# ---- _meta_json -------------------------------------------------------------------------------------------
for v in ('"text"', '[1, 2]', '5', 'null', 'not json'):
    raw('ntp:conf', v)
    ok('a row of meta of another shape (%s) read as none' % v, otp._meta_json(store, 'ntp:conf') is None)
raw('hisec:waive', '["a"]')
ok('a list asked as a list', otp._meta_json(store, 'hisec:waive', list) == ['a'])
raw('hisec:waive', '{"a": 1}')
ok('an object asked as a list: none', otp._meta_json(store, 'hisec:waive', list) is None)
store.db.run("DELETE FROM meta WHERE k IN ('ntp:conf', 'hisec:waive')")
try:
    otp.ntp_conf(store); ok('the time settings with no row', True)
except Exception as e:      # noqa: BLE001
    ok('the time settings with no row', False, e)

# ---- the local users' row ---------------------------------------------------------------------------------
asked = []
answer = {'v': {'users': [{'name': 'novak'}], 'policy': {'pwquality': {'minlen': 9}}, 'shells': ['/bin/bash']}}


def fake_users_ask(data, wait=60):
    asked.append(data.get('do'))
    a = answer['v']
    if isinstance(a, Exception):
        raise a
    return a


otp.users_ask = fake_users_ask
otp.sshkeys_ask = lambda *a, **k: None
for bad in ('"text"', '{"policy": "text", "done": "abc", "users": "x", "said": 5}', '[]', 'null',
            '{"policy": {"pwquality": "x"}}'):
    raw('host:users:now:nodea', bad)
    now = otp.osu_now(store, 'nodea')
    ok('the users row %s read as an object of the right kinds' % bad[:30],
       isinstance(now, dict) and isinstance(now.get('done', []), list) and
       isinstance(now.get('policy', {}), dict) and isinstance(now.get('users', []), list), now)
    otp.OSU_WORK['seen'] = 0.0
    try:
        otp.osu_tick(D())
        t = otp.OSU_WORK.get('thread')
        if t:
            t.join(10)
        row = json.loads(store.get_meta('host:users:now:nodea') or 'null')
        ok('...the tick does not fall, and writes the row again right', isinstance(row, dict) and
           row.get('users') == [{'name': 'novak'}] and not row.get('error'), row)
    except Exception as e:      # noqa: BLE001
        ok('...the tick does not fall, and writes the row again right', False, repr(e))
    try:
        otp.osu_view(store); ok('...the page of the local users is read', True)
    except Exception as e:      # noqa: BLE001
        ok('...the page of the local users is read', False, repr(e))

answer['v'] = 'the root helper said something'
row = {'users': [{'name': 'kept'}]}
try:
    otp.osu_keep(row, answer['v']); ok('an answer of the helper that is no object: not kept', False)
except ValueError as e:
    ok('an answer of the helper that is no object: not kept', row == {'users': [{'name': 'kept'}]} and 'str' in str(e), e)
try:
    otp.osu_keep(row, {'users': 'x'}); ok('an answer whose users are no list: not kept', False)
except ValueError:
    ok('an answer whose users are no list: not kept', row == {'users': [{'name': 'kept'}]})
raw('host:users:now:nodea', '{"users": []}')
otp.OSU_WORK['seen'] = 0.0
otp.osu_tick(D())
t = otp.OSU_WORK.get('thread')
t and t.join(10)
row = json.loads(store.get_meta('host:users:now:nodea'))
ok('...a list asked and answered with words: the error noted, the row an object', isinstance(row, dict) and
   'no list of users' in (row.get('error') or ''), row)

# an ask of another shape in the other node's row: left out
raw('host:users:want:nodea@@nodeb', json.dumps([{'id': 'a1', 'at': 'yesterday', 'do': 'list'},
                                                 {'id': ['x'], 'at': 1, 'do': 'list'}, 'x',
                                                 {'id': 'a2', 'at': time.time(), 'do': 'list'}]))
ok('asks of another shape left out', [a['id'] for a in otp.osu_asks(store, 'nodea')] == ['a2'])
store.db.run("DELETE FROM meta WHERE k LIKE 'host:users:want:%'")

# what is kept of the machine, sealed, of another shape
raw('host:keep:nodea', json.dumps({'at': 1, 'sealed': otp.seal_secret('"text"', 'hostkeep:nodea')}))
try:
    v = otp.keep_view(store, 'nodea'); ok('the kept machine of another shape: the page read', v['users'] == 0, v)
except Exception as e:      # noqa: BLE001
    ok('the kept machine of another shape: the page read', False, repr(e))

# ---- the root helper's answer -----------------------------------------------------------------------------
real_hex = otp.secrets.token_hex
otp.secrets.token_hex = lambda n=8: 'fixedid0'
try:
    (otp.WEB_DIR / 'ntp.json').write_text(json.dumps({'id': 'fixedid0', 'ok': True, 'data': ['x']}))
    try:
        otp.root_ask('ntp.ask', 'ntp.json', {'do': 'read'}, 3); ok('a helper answering no object: an error', False)
    except ValueError as e:
        ok('a helper answering no object: an error', 'no object' in str(e), e)
    (otp.WEB_DIR / 'ntp.json').write_text(json.dumps({'id': 'fixedid0', 'ok': True, 'data': {'a': 1}}))
    ok('an object: as it was', otp.root_ask('ntp.ask', 'ntp.json', {'do': 'read'}, 3) == {'a': 1})
    (otp.WEB_DIR / 'ntp.json').write_text(json.dumps({'id': 'fixedid0', 'ok': True}))
    ok('no data: an empty object, as before', otp.root_ask('ntp.ask', 'ntp.json', {'do': 'read'}, 3) == {})
finally:
    otp.secrets.token_hex = real_hex

# ---- where it broke ---------------------------------------------------------------------------------------
lines = []
real_log = otp.log
otp.log = lambda w, level='info': lines.append(w)
try:
    try:
        'x'.get('y')
    except Exception as e:      # noqa: BLE001
        otp.log_sparing('t-where-1', 'the test: %s' % e, 'warn', every=0)
    try:
        raise ValueError('a thing otp says')
    except Exception as e:      # noqa: BLE001
        otp.log_sparing('t-where-2', 'the test: %s' % e, 'warn', every=0)
    otp.log_sparing('t-where-3', 'no error at all', 'warn', every=0)
finally:
    otp.log = real_log
ok('a fault of the code: where it broke written', '[at t_r250.py:' in lines[0] and ' in <module>]' in lines[0], lines)
ok('an error otp says: its words as they are', lines[1] == 'the test: a thing otp says', lines)
ok('no error: nothing added', lines[2] == 'no error at all', lines)

# ---- heartbeats of another shape ---------------------------------------------------------------------------
otp.CONFIG['ha_mode'] = 'shared'
raw('node:junk1', '"text"'); raw('node:junk2', '{"at": "soon"}'); raw('node:junk3', '[1]')
try:
    names = [n['name'] for n in otp.ha_nodes(store)]
    ok('heartbeats of another shape left out', not any(x.startswith('junk') for x in names), names)
except Exception as e:      # noqa: BLE001
    ok('heartbeats of another shape left out', False, repr(e))
store.db.run("DELETE FROM meta WHERE k LIKE 'node:junk%'")

# ---- the guard: Back up now of a node of a version before -------------------------------------------------
otp.CONFIG['db_guard'] = 1
otp.DBGUARD['refused'].clear()
otp.store_beat = None


def beat(name, ver):
    store.set_meta('node:' + name, json.dumps({'at': time.time(), 'version': ver, 'address': '127.0.0.9'}))


beat('nodea', otp.__version__)
otp.dbguard_adopt_tick(store)
ok('one node: every version taken in', set(otp.DBGUARD_SINCE) <= set(otp.DBGUARD['adopted']), otp.DBGUARD['adopted'])
old = json.dumps({'id': 'old1', 'at': time.time() - 3600, 'by': 'x', 'from': 'nodeb'})
raw('rbackup:now:nodea@@nodeb', old)
otp.RB_JOB['running'] = False
started = []
otp.rb_job_start = lambda *a, **k: started.append(a)
otp.rb_now_asked(D())
ok('an old ask of the other node, unsigned: not checked, not logged, not done',
   not otp.DBGUARD['refused'] and not started, otp.DBGUARD['refused'])
raw('rbackup:now:nodea@@nodeb', json.dumps({'id': 'new1', 'at': time.time(), 'by': 'x', 'from': 'nodeb'}))
otp.rb_now_asked(D())
ok('a live ask unsigned, every node of this version: refused', otp.DBGUARD['refused'] and not started,
   otp.DBGUARD['refused'])

# the node of a version before alive: its rows taken as before, until it runs this one
otp.DBGUARD['refused'].clear()
beat('nodeb', '1.0.247')
otp.dbguard_adopt_tick(store)
ok('a node of a version before alive: the rows of the version not taken in',
   '1.0.248' not in otp.DBGUARD['adopted'], otp.DBGUARD['adopted'])
raw('rbackup:targets', json.dumps([{'id': 't1', 'kind': 'folder', 'path': '/x'}]))
ok('...its unsigned row of the version acted on, as before it',
   otp.dbguard_ok(store.db, 'm', 'rbackup:targets', store.get_meta('rbackup:targets')))
raw('rbackup:now:nodea@@nodeb', json.dumps({'id': 'new2', 'at': time.time(), 'by': 'x', 'from': 'nodeb'}))
otp.rb_now_asked(D())
ok('...and its Back up now done', len(started) == 1 and not otp.DBGUARD['refused'], (started, otp.DBGUARD['refused']))
ok('...a row signed long before still checked', not otp.dbguard_ok(store.db, 'm', 'fw:conf', '{"x": 1}', quiet=True))
beat('nodeb', otp.__version__)
otp.dbguard_adopt_tick(store)
ok('the other node of this version too: the version taken in', '1.0.248' in otp.DBGUARD['adopted'],
   otp.DBGUARD['adopted'])
ok('...the row it had written signed as it was',
   otp.dbguard_ok(store.db, 'm', 'rbackup:targets', store.get_meta('rbackup:targets'), early=False))
ok('...one written by somebody else after it: refused',
   (raw('rbackup:targets', '[]') or True) and not otp.dbguard_ok(store.db, 'm', 'rbackup:targets', '[]', quiet=True))

# a heartbeat written by somebody else saying an old version: no word on it
store.db.run("UPDATE meta SET v = ? WHERE k = 'node:nodeb'",
             (json.dumps({'at': time.time(), 'version': '1.0.200', 'address': '127.0.0.9'}),))
otp.dbguard_adopt_tick(store)
ok('a heartbeat not signed saying a version before: the version stays taken in', '1.0.248' in otp.DBGUARD['adopted'])

# ---- this node's own asks, gone once over -------------------------------------------------------------------
store.set_meta('rbackup:now:nodeb@@nodea', json.dumps({'id': 'o1', 'at': time.time() - 3600}))
store.set_meta('rbackup:now:nodec@@nodea', json.dumps({'id': 'o2', 'at': time.time()}))
raw('rbackup:now:nodea@@nodeb', old)
n = otp.rb_now_tidy(store)
left = sorted(r['k'] for r in store.db.rows("SELECT k FROM meta WHERE k LIKE 'rbackup:now:%'"))
ok('its own old ask taken away, the live one and the other node\'s left', n == 1 and
   left == ['rbackup:now:nodea@@nodeb', 'rbackup:now:nodec@@nodea'], (n, left))
ok('...its going signed', otp.dbguard_ok(store.db, 'm', 'rbackup:now:nodeb@@nodea', None, quiet=True))

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
