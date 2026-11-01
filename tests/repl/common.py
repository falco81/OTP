import os, sys, time, json
os.environ.setdefault('OTP_STATE', '/home/claude/ws/tests/repl/state')
os.environ.setdefault('OTP_CONFIG', '/home/claude/ws/tests/repl/state/config.json')
os.environ.setdefault('OTP_LOGDIR', '/home/claude/ws/tests/repl/log')
os.environ.setdefault('OTP_RUN', '/home/claude/ws/tests/repl/state')
sys.path.insert(0, '/home/claude/build/out/otp-'+os.environ.get('OTP_VER','1.0.214')+'')
import otp
import psycopg2, psycopg2.extras
PW = 'hunt8pw'
CONF = {'A': {'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': 5432, 'db_name': 'hunt8r_a',
              'db_user': 'hunt8r_otp', 'db_password': PW},
        'B': {'db_engine': 'postgres', 'db_host': '127.0.0.1', 'db_port': 5433, 'db_name': 'hunt8r_b',
              'db_user': 'hunt8r_otp', 'db_password': PW}}
SLOT = {'A': 1, 'B': 2}

def dbs():
    return otp.db_open(CONF['A']), otp.db_open(CONF['B'])

def raw(n, autocommit=True):
    c = CONF[n]
    k = psycopg2.connect(host=c['db_host'], port=c['db_port'], dbname=c['db_name'], user=c['db_user'], password=PW)
    k.autocommit = autocommit
    return k

def q(n, sql, args=()):
    k = raw(n)
    cur = k.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, args)
    out = cur.fetchall() if cur.description else cur.rowcount
    k.close()
    return out

def sub(n, enable):
    me = 'hunt8r_from_%d' % SLOT['B' if n == 'A' else 'A']
    q(n, 'ALTER SUBSCRIPTION %s %s' % (me, 'ENABLE' if enable else 'DISABLE'))

def pause():
    """Both directions stopped: writes made now on both nodes cross."""
    sub('A', False); sub('B', False)

def resume(wait=True):
    sub('A', True); sub('B', True)
    if wait:
        settle()

def lsn(n):
    return q(n, 'SELECT pg_current_wal_lsn() AS l')[0]['l']

def settle(timeout=20):
    """Until each side's slot on the other has confirmed everything written so far."""
    t0 = time.time()
    targets = {'A': lsn('A'), 'B': lsn('B')}
    while time.time() - t0 < timeout:
        ok = True
        for n in 'AB':
            r = q(n, "SELECT bool_and(confirmed_flush_lsn >= %s::pg_lsn) AS d FROM pg_replication_slots WHERE slot_name LIKE 'hunt8r_from_%%'", (targets[n],))
            if not r or not r[0]['d']:
                ok = False
        if ok:
            time.sleep(0.3)
            return True
        time.sleep(0.2)
    return False

def health():
    out = {}
    for n in 'AB':
        out[n] = q(n, "SELECT s.subname, s.subenabled, st.pid IS NOT NULL AS running, ss.apply_error_count, ss.sync_error_count "
                     "FROM pg_subscription s LEFT JOIN pg_stat_subscription st ON st.subid = s.oid AND st.relid IS NULL "
                     "LEFT JOIN pg_stat_subscription_stats ss ON ss.subid = s.oid WHERE s.subdbid = (SELECT oid FROM pg_database WHERE datname = current_database())")
    return out

COLS = 'id,name,state,last_step,failures,fail_times,locked_until,scratch,scratch_left,secret,pending_secret,key_at,state_at,lock_at,scratch_at,last_used,last_how'
def tok(n, name=None, cols=COLS):
    if name:
        return q(n, 'SELECT %s FROM tokens WHERE name = %%s' % cols, (name,))
    return q(n, 'SELECT %s FROM tokens ORDER BY id' % cols)

def same(table, order='id', cols='*'):
    a = q('A', 'SELECT %s FROM %s ORDER BY %s' % (cols, table, order))
    b = q('B', 'SELECT %s FROM %s ORDER BY %s' % (cols, table, order))
    return a == b, a, b

def store(n, quick=True):
    node(n)        # each daemon has its own CONFIG: ha_slot decides the odd/even numbering
    s = otp.Storage(otp.db_open(CONF[n]), quick=quick)
    return s

def node(n):
    """Point otp's process-wide CONFIG at node n (once_take, once_node)."""
    otp.CONFIG['ha_mode'] = 'replicated'
    otp.CONFIG['ha_slot'] = SLOT[n]
    otp.CONFIG['ha_peer'] = ''          # no direct ask of the peer: the slow-link case

def reset():
    """Empty the token tables on both nodes (replicated deletes)."""
    resume(False)
    for t in ('tokens', 'token_once', 'meta', 'otp_log', 'events', 'settings'):
        q('A', 'DELETE FROM %s' % t); settle(); q('B', 'DELETE FROM %s' % t)
    settle()
    store('A', False); store('B', False)          # make_tables() runs again here (its meta mark was emptied)
    settle()

def code(secret, when=None, digits=6):
    return otp.totp(secret, when, digits)

def plain(n, name):
    t = tok(n, name, '*')
    return otp.unseal_secret(t[0]['secret'], otp.token_bind(t[0]['name'])) if t else None
