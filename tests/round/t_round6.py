# t_round6.py VERSION - the HA audit of every pane (1.0.211): a cluster of one shared
# database seen as a cluster, one thing at a time on the cluster, the database pane's guards.
# In-process against otp.py of VERSION on SQLite, another node's heartbeat written by hand.
import os, sys, json, time, tempfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.211'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r6-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r6a'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
otp.load_config(saved=None)
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:400]) if more and not cond else ''),
          flush=True)


def raises(fn, words=''):
    try:
        fn()
        return False
    except (ValueError, otp.BadSetting) as e:
        return words in str(e)


db = otp.Db('sqlite', path=os.path.join(D, 'otp.db'))
st = otp.Storage(db)
otp.sealing_key(make=True)
otp.HA_STORE['store'] = st
d = otp.Daemon(st, serve=False)
me = otp.node_name()


def beat(name, ago=0, **kw):
    st.set_meta('node:' + name, json.dumps(dict({'at': time.time() - ago, 'address': '192.0.2.%d' % (len(name) + 20)},
                                                **kw)))


# ---- a cluster of one shared database: ha_mode empty, the other node heard from -----------
ok('alone: not a cluster', otp.in_cluster(st) is False)
beat('r6b', ago=3 * 86400)
ok('... a node not heard from for three days: still not a cluster', otp.in_cluster(st) is False)
beat('r6b')
beat(me)
ok('another node heard from now, ha_mode empty (one shared database): a cluster', otp.in_cluster(st) is True)
ok('... the alerts sent by one node of the two, not both (%s leads)' % me, otp.alerts_lead(st) == (me < 'r6b'))
lv = otp.logs_view(st)
rows = lv.get('nodes') if isinstance(lv, dict) else lv
ok('... the disks and logs shown for both nodes', {r.get('node') for r in rows} >= {me, 'r6b'}, rows)

# ---- one thing at a time on the cluster ---------------------------------------------------------
st.set_meta('net:job:r6b', json.dumps({'id': 'x', 'node': 'r6b', 'state': 'running', 'at': time.time(),
                                       'boot': 0}))
real_active = otp.net_job_active
otp.net_job_active = lambda job: bool(job) and job.get('state') == 'running'
ok('the other node changes its network: a restart here refused',
   raises(lambda: otp.power_ask(st, 'reboot', [me], 'one', 't'), 'changing its network'))
ok('... and a system update', raises(lambda: otp.osup_start(st, [me], 'never', 't'), 'changing its network'))
st.db.run("DELETE FROM meta WHERE k = 'net:job:r6b'")
otp.net_job_active = real_active
st.set_meta('host:osup:plan', json.dumps({'id': 'p', 'state': 'running', 'at': time.time(), 'nodes': ['r6b']}))
ok('a system update going on: a new network refused',
   raises(lambda: otp.net_ask(st, me, {}, 't'), 'being updated'))
ok('... a restart refused, but not the update\'s own restart',
   raises(lambda: otp.power_ask(st, 'reboot', [me], 'one', 't'), 'being updated') and
   otp.cluster_busy(st, skip=('osup', 'power')) == '')
st.db.run("DELETE FROM meta WHERE k = 'host:osup:plan'")

# ---- the database pane ---------------------------------------------------------------------------
st.set_meta('db_job:r6b', json.dumps({'running': True, 'node': 'r6b', 'what': 'putting a copy back',
                                      'at': time.time(), 'began': time.time()}))
ok('a job on the database going on on the other node: none started here',
   raises(lambda: otp.db_job('erasing', lambda p: None), 'going on on r6b'))
st.db.run("DELETE FROM meta WHERE k = 'db_job:r6b'")
ok('a copy put back keeps each node\'s own: tuning, encryption to the database, asks',
   all(p in otp.META_TRANSIENT for p in ('tune_before:', 'tune_last:', 'dbtls:', 'ask:')))


class PG:
    engine = 'postgres'

    def __init__(self, subs, lrw='4'):
        self.subs, self.lrw = subs, lrw

    def value(self, sql, *a):
        if 'pg_subscription' in sql:
            return self.subs
        if 'max_logical_replication_workers' in sql:
            return self.lrw
        return None


plan = otp.tune_plan('postgres', {'ram_gb': 32, 'cpus': 8, 'disk': 'ssd', 'local': True})
got = otp.tune_keep_workers(PG(1), plan, {'max_worker_processes': '8'})
mwp, mpw = int(got['max_worker_processes'][0]), int(got['max_parallel_workers'][0])
ok('tuning a replicating PostgreSQL: replication\'s workers kept free (%d workers, %d parallel)' % (mwp, mpw),
   mwp - mpw >= 6)
got = otp.tune_keep_workers(PG(1), plan, {'max_worker_processes': '32'})
ok('... a max_worker_processes someone raised never lowered', int(got['max_worker_processes'][0]) == 32)
got = otp.tune_keep_workers(PG(0), plan, {'max_worker_processes': '8'})
ok('... alone: as before (%s)' % got['max_worker_processes'][0], int(got['max_worker_processes'][0]) == 8)

# ---- settings for another node: its own ports ---------------------------------------------------
otp.CONFIG['ha_mode'] = 'replicated'
st.save_setting('radius_acct_port@r6b', 1900, 't')
otp.load_config(saved=st.settings_saved())
ok('the sign-ins of the other node on its own accounting port: refused there',
   raises(lambda: d.save_settings({'radius_auth_port': 1900}, by='t', node='r6b'), 'one port'))
ok('... the same port for this node (its accounting on 1813): taken',
   not raises(lambda: d.save_settings({'radius_auth_port': 1900}, by='t', node=me)))
otp.CONFIG['ha_mode'] = ''

# ---- what the pages do, read in their files ------------------------------------------------------
src = open(V + '/otp.py').read()
J = open(V + '/web/assets/admin.js').read()
ok('Set it up on the database pane refused in a cluster', "if in_cluster(h.store) and act == 'setup':" in src)
ok('PostgreSQL restarted from the pages: never the shared server, never with the other node down, '
   'one node at a time, RADIUS stepping aside', 'the nodes share this database server' in src and
   "'db_restart:' + node_name()" in src and "RESTORE_WHY[0] = 'its PostgreSQL is restarted'" in src)
ok('a copy sealed with another key refused in every kind of cluster',
   "if in_cluster(store) and re.match(r'^[0-9a-f]{64}\\Z', key_hex):" in src)
ok('erasing a log in batches', "gone[t] = store.delete_older(t, time.time() + 100 * 365 * 86400)" in src)
ok('the alerts looked at again by the node that sends them only', "if alerts_lead(h.store):\n                alerts_evaluate"
   in src)
ok('SSH: Keep keeps only where it was on trial when pressed', "> float(now.get('applied_at') or 0)" in src)
ok('replication paused half way said, not a bare error', src.count("its side as it was") == 2)
ok('the firewall lets the other node in, in a cluster of one shared database too',
   'if peers and in_cluster(store):' in src)
ok('a new address of a node in a cluster of one shared database: ticked by whoever changes it',
   "want.get('shared_db_ok')" in src and 'shared_db_ok' in J)
ok('maintenance: the last node in service is said to be the last', 'No other node is answering in service' in J)
ok('Resume possible after only what goes out was paused', "(r.outgoing || []).some(function (x) { return x.active === false; })"
   in J)
# ---- replicated HA join: this node's own address in pg_hba.conf (1.0.212) ----------------------
if 'own_address' in open(V + '/otp.py').read():
    hba = os.path.join(D, 'pg_hba.conf')
    open(hba, 'w').write('local all all peer\n')
    answers = {'SHOW server_version_num': '160004', 'SHOW wal_level': 'logical', 'SHOW listen_addresses': '*',
               'SHOW max_slot_wal_keep_size': otp.HA_SLOT_KEEP, 'SHOW hba_file': hba}
    real_admin = otp.pg_admin
    otp.pg_admin = lambda sql, port=5432, db=None, secret=False: answers.get(sql, '1')
    try:
        otp.pg_prepare_local(5432, '192.0.2.71', 'otp', 'otp', 'x' * 20, lambda t: None, own_address='192.0.2.72')
        text = open(hba).read()
    finally:
        otp.pg_admin = real_admin
    ok('replicated HA: pg_hba.conf lets in the other node, this node itself (its subscription is tried from here) and '
       '127.0.0.1', all(x in text for x in ('192.0.2.71/32', '192.0.2.72/32', '127.0.0.1/32')), text)
    otp.pg_admin = lambda sql, port=5432, db=None, secret=False: answers.get(sql, '1')
    try:
        otp.pg_prepare_local(5432, '192.0.2.71', 'otp', 'otp', 'x' * 20, lambda t: None, own_address='192.0.2.72')
    finally:
        otp.pg_admin = real_admin
    ok('... run again: no line twice', open(hba).read().count('192.0.2.72/32') == 1)
print('ALL %d / %d' % (sum(R), len(R)))
