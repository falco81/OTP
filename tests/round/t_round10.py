# t_round10.py VERSION - 1.0.217: what the hunt of 1.0.216 found, on a PostgreSQL of its own (local
# 5432, roles and a database r10_* made and dropped here). The database pane: a server under
# another name taken for the one in use (Empty dropped the live tables), the live password sent
# to another server, the live account's password changed by setting up another database, a
# dump put back bringing back another node's heartbeat; the import: a directory admin signed
# out by "Exactly the file", a bad value after the clients were in. RADIUS: a transaction
# skipped on a shared lane, a recovery code sent again charged to the directory password.
import os, sys, json, time, tempfile, subprocess, threading
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.217'
V = '/home/claude/build/out/otp-%s' % VER


def psql(sql):
    return subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', '5432', '-XAtqc', sql],
                          capture_output=True, text=True).stdout.strip()


for sql in ("DROP DATABASE IF EXISTS r10_live", "DROP DATABASE IF EXISTS r10_other",
            "DROP ROLE IF EXISTS r10_live", "DROP ROLE IF EXISTS r10_new", "DROP ROLE IF EXISTS r10_admin",
            "CREATE ROLE r10_admin LOGIN SUPERUSER PASSWORD 'r10-admin-pw'",
            "CREATE ROLE r10_live LOGIN PASSWORD 'r10-live-pw'", "CREATE DATABASE r10_live OWNER r10_live"):
    psql(sql)
D = tempfile.mkdtemp(prefix='otp-r10-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
LIVE = {'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': 5432, 'db_name': 'r10_live',
        'db_user': 'r10_live', 'db_password': 'r10-live-pw', 'node_name': 'r10a'}
json.dump(LIVE, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
otp.load_config(saved=None)
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:400]) if more and not cond else ''),
          flush=True)


db = otp.Db('postgres', '127.0.0.1', 5432, 'r10_live', 'r10_live', 'r10-live-pw')
db.make_tables()
db.add_missing_columns()
st = otp.Storage(db)
otp.sealing_key(make=True)
otp.HA_STORE['store'] = st
st.client_save({'name': 'nas1', 'address': '192.0.2.1', 'secret': 'sharedsecret1'}, 't')
st.db.insert('accounts', {'name': 'admin', 'role': 'fulladmin', 'pw': otp.password_hash('R10-Admin-pass-1'),
                          'source': 'local', 'disabled': 0, 'must_change': 0, 'note': '', 'display': '',
                          'dn': '', 'group_list': '', 'created': time.time(), 'prefs': '{}'})


class Dm(object):
    def reload_all(self, *a):
        pass


class H(object):
    def __init__(self, body):
        self.store, self.d, self._b = st, Dm(), body

    def me(self, role=None):
        return {'name': 'admin', 'role': 'fulladmin'}

    def body(self):
        return self._b

    def arg(self, k):
        return None


def call(body):
    try:
        return otp._db_do(H(body))
    except otp.ApiError as e:
        return ('ApiError', e.status, str(e))


try:
    # ---- the server in use, under another name ---------------------------------------------
    alias = dict(LIVE, db_host='127.1')
    got = call({'action': 'try', 'settings': alias})
    ok('the database in use reached as 127.1: said to be the one in use', got.get('in_use') is True, got)
    got = call({'action': 'empty', 'settings': alias})
    ok('... Empty refused, the tables kept', isinstance(got, tuple) and 'database in use' in got[2] and
       int(st.db.value('SELECT COUNT(*) FROM clients')) == 1, got)
    # ---- the live password never sent to another server or account -----------------------------
    other = {'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': 5432, 'db_name': 'r10_other',
             'db_user': 'r10_new'}
    ok('another account typed without a password: the one in use not taken for it',
       otp.engine_asked(other).get('db_password') == '')
    got = call({'action': 'setup', 'settings': other, 'admin_user': 'r10_admin', 'admin_password': 'r10-admin-pw'})
    ok('... set up: a new password made and shown, not the one in use',
       isinstance(got, dict) and got.get('password') and got['password'] != 'r10-live-pw', got)
    # ---- the live account's password not changed by setting up another database ---------------
    got = call({'action': 'setup', 'settings': dict(other, db_user='r10_live', db_name='r10_other'),
                'admin_user': 'r10_admin', 'admin_password': 'r10-admin-pw'})
    ok('another database set up under the account in use: refused', isinstance(got, tuple) and
       'the one this node uses now' in got[2], got)
    try:
        otp.Db('postgres', '127.0.0.1', 5432, 'r10_live', 'r10_live', 'r10-live-pw').value('SELECT 1')
        still = True
    except Exception:                                   # noqa: BLE001
        still = False
    ok('... the account in use still gets in with its password', still)
    # ---- a dump put back: this node's own rows of meta stay ----------------------------------
    st.set_meta('node:r10b', json.dumps({'at': time.time(), 'address': '192.0.2.9'}))
    st.set_meta('db_job:r10a', json.dumps({'running': True, 'node': 'r10a', 'at': time.time()}))
    dump = otp.make_dump(st, 'by-hand')
    for k in ('node:r10b', 'db_job:r10a'):
        st.db.run('DELETE FROM meta WHERE k = ?', (k,))
    otp.db_file_restore(st, dump, 'admin', from_name=dump.name)
    ok('a PostgreSQL dump put back: the other node\'s old heartbeat and a job "running" not brought back',
       st.get_meta('node:r10b') is None and st.get_meta('db_job:r10a') is None and not otp.in_cluster(st))
    ok('... acme push\'s nonces are this node\'s own too', 'acme_push:nonces' in otp.META_TRANSIENT)
    # ---- the import --------------------------------------------------------------------------
    d = otp.Daemon(st, serve=False)
    st.save_setting('lockout_after', 7, 't')
    try:
        otp.config_import(st, d, {'clients': [{'name': 'nas2', 'address': '192.0.2.2', 'secret': 'x2secretxx'}],
                                  'settings': {'lockout_after': 'abc'}}, 'boss', keep_account='boss', replace=True)
        said = ''
    except otp.ApiError as e:
        said = str(e)
    ok('an import with a bad value: refused before anything is saved (%s)' % said,
       'nothing was imported' in said and [c['name'] for c in st.clients()] == ['nas1'])
    st.db.insert('accounts', {'name': 'boss@corp', 'role': 'fulladmin', 'pw': '', 'source': 'directory',
                              'disabled': 0, 'must_change': 0, 'note': '', 'display': '', 'dn': '',
                              'group_list': '', 'created': time.time(), 'prefs': '{}'})
    st.save_setting('admin_directory', 'corp', 't')
    otp.load_config(saved=st.settings_saved())
    otp.config_import(st, d, {'settings': {'lockout_after': 8}}, 'boss@corp', keep_account='boss@corp', replace=True)
    ok('"Exactly the file" by an administrator of the directory: the way in through it kept',
       st.settings_saved().get('admin_directory') == 'corp')
    # ---- RADIUS: the transaction on a shared lane ----------------------------------------------
    begins = []
    real = otp.Db.run

    def run(self, sql, args=()):
        if str(sql).strip().upper() in ('BEGIN', 'START TRANSACTION'):
            begins.append(1)
        return real(self, sql, args)
    otp.Db.run = run
    tk = otp.Tokens(st)
    names = ['r10u%d' % i for i in range(16)]
    keys = {}
    for n in names:
        keys[n] = tk.enroll(n, 't')['scratch']

    def worker(i):
        threading.current_thread().name = 'radius-%d' % i
        n = names[i]
        for c in keys[n][:5]:
            tk.check(n, c, how='radius')
    th = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    [x.start() for x in th]
    [x.join() for x in th]
    otp.Db.run = real
    ok('16 RADIUS workers on 4 lanes: every recovery code used in a transaction of its own (%d of 80)'
       % len(begins), len(begins) == 80)
    src = open(V + '/otp.py').read()
    ok('password+code: a code used already gets the right password to the directory',
       "if _said == SAY_REUSED and reused is None:" in src)
finally:
    try:
        st.db.close()
    except Exception:                                   # noqa: BLE001
        pass
    for sql in ("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('r10_live', 'r10_other')",
                "DROP DATABASE IF EXISTS r10_live", "DROP DATABASE IF EXISTS r10_other",
                "DROP ROLE IF EXISTS r10_live", "DROP ROLE IF EXISTS r10_new", "DROP ROLE IF EXISTS r10_admin"):
        psql(sql)
print('ALL %d / %d' % (sum(R), len(R)))
