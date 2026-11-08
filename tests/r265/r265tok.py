"""Run as the otp user with the installed python: make or remove the load test's tokens.
  make SUFFIX FIRST COUNT  -> JSON {name: base32 secret} on stdout (to a pipe, never a terminal)
  drop                     -> removes every token named zzr265%, and their log rows
  rows                     -> JSON counts of the log tables (for growth)"""
import sys, os, json, time
sys.path.insert(0, '/usr/local/lib/otp')
os.environ.setdefault('OTP_CONFIG', '/etc/otp/config.json')
args = sys.argv[1:]
sys.argv = ['otp']
import otp                                              # noqa: E402
otp.load_config()
st = otp.Storage(otp.open_db())
if args[0] == 'make':
    suffix, first, count = args[1], int(args[2]), int(args[3])
    out = {}
    now = time.time()
    for i in range(first, first + count):
        name = otp.norm_name('zzr265u%05d@%s' % (i, suffix))
        sec = otp.b32_new(20)
        st.token_write(name, {'secret': otp.seal_secret(sec, otp.token_bind(name)), 'digits': 6, 'period': 30,
                              'algorithm': 'SHA1', 'state': 'active', 'last_step': 0, 'scratch': '[]',
                              'scratch_sealed': None, 'scratch_left': 0, 'created': now,
                              'created_by': 'r265 load test', 'activated': now, 'failures': 0,
                              'fail_times': '[]', 'locked_until': None, 'note': 'r265 load test'})
        out[name] = sec
    sys.stdout.write(json.dumps(out))
elif args[0] == 'drop':
    n = st.db.value("SELECT COUNT(*) FROM tokens WHERE name LIKE 'zzr265%'")
    st.db.run("DELETE FROM tokens WHERE name LIKE 'zzr265%'")
    a = st.db.value("SELECT COUNT(*) FROM radius_log WHERE username LIKE 'zzr265%'")
    st.db.run("DELETE FROM radius_log WHERE username LIKE 'zzr265%'")
    b = st.db.value("SELECT COUNT(*) FROM otp_log WHERE name LIKE 'zzr265%'")
    st.db.run("DELETE FROM otp_log WHERE name LIKE 'zzr265%'")
    print(json.dumps({'tokens': n, 'radius_log': a, 'otp_log': b}))
elif args[0] == 'sql':
    print(json.dumps(st.db.rows(sys.stdin.read()), default=str))
elif args[0] == 'rows':
    print(json.dumps({t: st.db.value('SELECT COUNT(*) FROM %s' % t) for t in ('radius_log', 'otp_log', 'events', 'tokens', 'sessions')}))
