"""t_fix.py - 1.0.332: the alert of a certificate running out by its life; the ECDSA certificate
watched, and not handed to nginx once run out.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, sys, tempfile, time, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.332'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r332_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx332', 'api_port': 29955}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
st = m.Storage(m.open_db()); st.db.make_tables(); m.sealing_key(make=True)
now = time.time()
D1 = 86400


def cert(nb, na, cn='otp.example.cz', fp='a'):
    return {'not_before': now + nb * D1, 'not_after': now + na * D1, 'cn': cn, 'fingerprint': fp}


def alerts(web, days=21):
    m.CONFIG['alerts_cert_days'] = days
    st.set_meta('node:' + m.node_name(), json.dumps({'web': web}))
    got = m.alert_problems(st)
    return {k: v for k, v in got.items() if k.startswith('cert:')}


# ==== 1 by its life
a = alerts({'cert_now': cert(-1, 5)})                 # 6-day certificate, 5 left
ok('a 6-day certificate with 5 days left: no alert', a == {}, a)
a = alerts({'cert_now': cert(-4.8, 1.2)})             # 1.2 days of 6 left: past a quarter
ok('a 6-day certificate with 1.2 days left: warned', 'cert:node:fx332' in a and a['cert:node:fx332']['level'] == 'warn', a)
a = alerts({'cert_now': cert(-5.9, 0.1)})
ok('a 6-day certificate nearly out: bad', (a.get('cert:node:fx332') or {}).get('level') == 'bad', a)
a = alerts({'cert_now': cert(-70, 20)})               # 90-day: as before
ok('a 90-day certificate with 20 left: warned as before', (a.get('cert:node:fx332') or {}).get('level') == 'warn', a)
a = alerts({'cert_now': cert(-70, 25)})
ok('a 90-day certificate with 25 left: nothing, as before', a == {}, a)
a = alerts({'cert_now': cert(-85, 5)})
ok('a 90-day certificate with 5 left: bad, as before', (a.get('cert:node:fx332') or {}).get('level') == 'bad', a)
a = alerts({'cert_now': {'not_after': now + 10 * D1, 'cn': 'x', 'fingerprint': 'z'}})
ok('no not_before: as before (warned at 10)', (a.get('cert:node:fx332') or {}).get('level') == 'warn', a)
a = alerts({'cert_now': cert(-1, 5)}, days=0)
ok('alerts of certificates off: nothing', a == {})

# ==== 2 the ECDSA one watched
a = alerts({'cert_now': cert(-100, 200), 'alt_cert_now': cert(-300, 3, fp='b')})
ok('the ECDSA certificate running out: alerted', 'cert:node-ecdsa:fx332' in a and 'ECDSA' in a['cert:node-ecdsa:fx332']['title'], a)
a = alerts({'cert_now': cert(-100, 200), 'vip_cert_now': cert(-100, 200, fp='v'),
            'vip_alt_cert_now': cert(-300, -1, fp='w')})
ok('the VIP\'s ECDSA certificate run out: bad', (a.get('cert:vip-ecdsa:vip') or {}).get('level') == 'bad'
   and 'ran out' in a['cert:vip-ecdsa:vip']['title'], a)

# ==== 3 not given to nginx once run out
ok('tls_alt_ran_out by its info', m.tls_alt_ran_out({'info': {'not_after': now - 10}})
   and not m.tls_alt_ran_out({'info': {'not_after': now + 10}}) and not m.tls_alt_ran_out({}))
src = open(V + '/otp.py').read()
tr = src[src.index('def tls_resolved(prof):'):src.index('def tls_resolved(prof):') + 2500]
ok('tls_resolved leaves out a run-out ECDSA one', 'if alt and tls_alt_ran_out(alt):' in tr)
ws = src[src.index("def _alt(target):"):src.index("def _alt(target):") + 700]
ok('web_state reads the ECDSA file only while the profile has one', 'if not tls_alt(prof):' in ws and 'NGINX_ALT_FILES' in ws)
print('ALL %d / %d' % (sum(R), len(R)))
