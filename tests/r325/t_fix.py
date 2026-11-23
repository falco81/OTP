"""t_fix.py - 1.0.325: an uploaded backup kept when putting it back failed; a mail taken out while it was sent
stays out; a missing column added beside a constraint. The built otp.py over SQLite.

    python3 t_fix.py VERSION
"""
import importlib.util, inspect, json, os, shutil, sys, tempfile, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else "1.0.325"
V = "/home/claude/build/out/otp-%s" % VER
R = []


def ok(n, c, m=""):
    R.append(bool(c))
    print(("ok  " if c else "FAIL") + " " + n + ("" if c else " " + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix="t_r325_")
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + "/state"
os.makedirs(D + "/run")
json.dump({"db_engine": "sqlite", "node_name": "fx325", "api_port": 29955}, open(D + "/config.json", "w"))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + "/config.json", OTP_LOGDIR=D, OTP_RUN=D + "/run", OTP_STATE_DIR=D)
sys.argv = ["otp"]
spec = importlib.util.spec_from_file_location("otp", V + "/otp.py")
m = importlib.util.module_from_spec(spec)
sys.modules["otp"] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)

# ==== 1 the upload kept on failure
src = inspect.getsource(m._rb_restore_job)
ok('rbackup: the upload deleted only when it went', 'went[0] = True' in src and 'if src is not None and went[0]:' in src)

# ==== 2 the outgoing mail: taken out meanwhile stays out
m.CONFIG['mail_mode'] = 'smtp'
from email.message import EmailMessage
for outcome in ('ok', 'later'):
    def send(store, msg, to, outcome=outcome):
        for k in [r['k'] for r in st.db.rows("SELECT k FROM meta WHERE k LIKE 'mailq:%'")]:
            st.db.run('DELETE FROM meta WHERE k = ?', (k,))     # taken out meanwhile
        if outcome == 'ok':
            return [{'ok': True, 'said': '250 ok'}]
        raise m.MailError('451 later', [])
    m.mail_send = send
    msg = EmailMessage(); msg['Subject'] = 's'; msg.set_content('x')
    try:
        m.mail_deliver(st, msg, ['a@example.cz'], 'alert')
    except m.MailError:
        pass
    except Exception as e:                              # noqa: BLE001
        ok('mailq: %s ran' % outcome, False, repr(e))
    left = st.db.rows("SELECT k FROM meta WHERE k LIKE 'mailq:%' OR k LIKE 'mailb:%'")
    ok('mailq: taken out while sent (%s) - stays out' % outcome, not left, left)

# ==== 3 a missing column beside a constraint
import sqlite3
p = TOP + '/c.sqlite'
db = m.Db('sqlite', path=p); db.make_tables()
cols = db.columns('token_once')
if 'ts' in [c.lower() for c in cols]:
    con = sqlite3.connect(p)
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name = 'token_once'").fetchone()[0]
    con.execute('DROP TABLE token_once')
    import re
    sql2 = re.sub(r',\s*ts\s+[A-Z]+', '', sql)
    con.execute(sql2); con.commit(); con.close()
    db.close(); db = m.Db('sqlite', path=p)
    ok('setup: ts gone', 'ts' not in [c.lower() for c in db.columns('token_once')], db.columns('token_once'))
    db.columns_missing = False
    db._add_columns_now()
    ok('columns: ts added beside UNIQUE', 'ts' in [c.lower() for c in db.columns('token_once')] and not db.columns_missing,
       (db.columns('token_once'), db.columns_missing))
else:
    ok('token_once has ts', False, cols)
db.close()

print('ALL %d / %d' % (sum(R), len(R)))
