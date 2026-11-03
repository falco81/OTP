# t_realip.py VERSION - behind a load balancer or WAF (1.0.237). The root helper's edit of nginx's otp.conf:
# put in, changed, taken out, what otp --trusted-proxy wrote replaced only while it is on, values checked;
# the result taken by the real nginx here (nginx -t) and a request through it: the client's address from the
# header only when it comes from a balancer. The daemon's side: never asked until switched on, refused on
# without the balancers, taken out again when switched off.
# Usage (as root, nginx installed with otp's configuration): python3 t_realip.py VERSION
import os, sys, json, time, shutil, subprocess, tempfile, importlib.util, urllib.request, ssl
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.237'
V = os.environ.get('OTP_DIR') or '/home/claude/build/out/otp-%s' % VER
R = []


def ok(w, c, more=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + w + (' (%s)' % str(more)[:400] if more and not c else ''), flush=True)


os.environ['OTP_VIP_NO_SERVICES'] = '1'
spec = importlib.util.spec_from_file_location('otp_web', V + '/deploy/otp_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
CONF = '/etc/nginx/conf.d/otp.conf'
orig = open(CONF).read()
on = {'from': ['10.20.0.0/24', '192.0.2.5/32'], 'header': 'X-Real-IP', 'recursive': True}
a = W.realip_into(orig, on)
ok('on: otp\'s own lines in the HTTPS server', '# OTP-REALIP-BEGIN' in a and 'set_real_ip_from 10.20.0.0/24;' in a
   and 'real_ip_header X-Real-IP;' in a and 'real_ip_recursive on;' in a, a[:300])
where = W.server_block(a)
ok('...inside the HTTPS server { }, nowhere else', where and '# OTP-REALIP-BEGIN' in a[where[0]:where[1]] and a.count('# OTP-REALIP-BEGIN') == 1)
b = W.realip_into(a, dict(on, **{'from': ['198.51.100.7/32'], 'header': 'X-Forwarded-For', 'recursive': False}))
ok('changed: one block, the new values only', b.count('# OTP-REALIP-BEGIN') == 1 and '10.20.0.0/24' not in b
   and 'set_real_ip_from 198.51.100.7/32;' in b and 'real_ip_recursive off;' in b)
c = W.realip_into(b, {'from': [], 'header': '', 'recursive': False})
ok('off: otp\'s own lines gone, the file as it was', c == orig, (len(c), len(orig)))
w0 = W.server_block(orig)
nl = orig.index('\n', w0[0]) + 1
cli = orig[:nl] + ('    # REALIP-BEGIN - the load balancer(s), written by otp --trusted-proxy\n'
                   '    set_real_ip_from 203.0.113.9;\n    real_ip_header X-Forwarded-For;\n    real_ip_recursive on;\n'
                   '    # REALIP-END\n') + orig[nl:]
d = W.realip_into(cli, on)
ok('on over what otp --trusted-proxy wrote: it takes its place', '# REALIP-BEGIN' not in d and '203.0.113.9' not in d and '# OTP-REALIP-BEGIN' in d)
e = W.realip_into(cli, {'from': [], 'header': '', 'recursive': False})
ok('off with what otp --trusted-proxy wrote: that left as it is (as until now)', e == cli)
for bad, why in (({'from': ['10.0.0.0/8;\nevil'], 'header': 'X'}, 'network'), ({'from': ['10.0.0.1'], 'header': 'X-A;\nreturn 200'}, 'header'),
                 ({'from': ['10.0.0.1'], 'header': 'Host'}, 'header')):
    try:
        W.realip_into(orig, bad); got = ''
    except W.Refused as x:
        got = str(x)
    ok('refused, %s that is not one: %s' % (why, got[:60]), why in got or 'not' in got, got)
# the real nginx: takes it, and believes the header only from a balancer
try:
    open(CONF, 'w').write(W.realip_into(orig, {'from': ['127.0.0.1/32'], 'header': 'X-Real-IP', 'recursive': True}))
    t = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    ok('nginx -t takes it', t.returncode == 0, t.stderr[-300:])
    subprocess.run(['nginx', '-s', 'reload'], capture_output=True)
    time.sleep(1.5)
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    def seen(hdr):
        req = urllib.request.Request('https://127.0.0.1/healthz', headers=hdr)
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            r.read()
        time.sleep(0.3)
        line = subprocess.run(['tail', '-1', '/var/log/nginx/access.log'], capture_output=True, text=True).stdout
        return line.split(' ')[0] if line else ''
    # /healthz has no access log of its own in otp's file: ask the enrolment page instead
    def seen_page(hdr):
        req = urllib.request.Request('https://127.0.0.1/', headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                r.read(100)
        except Exception:
            pass
        time.sleep(0.4)
        logs = [p for p in ('/var/log/nginx/otp-access.log', '/var/log/nginx/access.log') if os.path.exists(p)]
        line = subprocess.run(['tail', '-1', logs[0]], capture_output=True, text=True).stdout if logs else ''
        return line.split(' ')[0] if line else ''
    who = seen_page({'X-Real-IP': '203.0.113.77'})
    ok('from a balancer (127.0.0.1 here): the client\'s address taken from X-Real-IP (%s)' % who, who == '203.0.113.77', who)
    open(CONF, 'w').write(W.realip_into(orig, {'from': ['192.0.2.5/32'], 'header': 'X-Real-IP', 'recursive': True}))
    subprocess.run(['nginx', '-s', 'reload'], capture_output=True); time.sleep(1.5)
    who = seen_page({'X-Real-IP': '203.0.113.77'})
    ok('from anybody else: the header not believed (%s)' % who, who == '127.0.0.1', who)
finally:
    open(CONF, 'w').write(orig)
    subprocess.run(['nginx', '-s', 'reload'], capture_output=True)
# the daemon's side
D = tempfile.mkdtemp(prefix='otp-rip-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run')
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'rip'}, open(D + '/config.json', 'w'))
sys.argv = ['x']; sys.path.insert(0, V)
import otp
otp.load_config(saved=None)
db = otp.Db('sqlite', path=D + '/otp.db'); db.make_tables(); st = otp.Storage(db); otp.sealing_key(make=True)
ok('never switched on: nothing asked of nginx (as until now)', otp.realip_desired(st) is None and 'realip' not in otp.web_desired(st))


class FakeD(otp.Daemon if hasattr(otp, 'Daemon') else object):
    pass
dmn = otp.Daemon.__new__(otp.Daemon); dmn.store = st
try:
    dmn.save_settings({'web_proxy': 1}, by='t'); e = ''
except Exception as x:
    e = str(x)
ok('switched on with no balancer named: refused', 'balancers' in e, e)
otp.CONFIG.update(web_proxy=1, web_proxy_from='10.20.0.0/24 192.0.2.5', web_proxy_header='X-Forwarded-For', web_proxy_recursive=1)
st.save_setting('web_proxy', 1)
rp = otp.realip_desired(st)
ok('on: asked with the networks, the header and the chain', rp == {'from': ['10.20.0.0/24', '192.0.2.5/32'], 'header': 'X-Forwarded-For', 'recursive': True}, rp)
otp.CONFIG['web_proxy'] = 0
st.save_setting('web_proxy', 0)
otp.SAVED_KEYS['at'] = 0.0      # as a save on the daemon does (1.0.239's 30 s cache)
ok('switched off again: asked to take otp\'s lines out', otp.realip_desired(st) == {'from': [], 'header': '', 'recursive': False})
# switched off through the daemon, as the pages do (1.0.238): the 0 was dropped as the default, and
# nginx's lines stayed
dmn2 = otp.Daemon.__new__(otp.Daemon); dmn2.store = st
otp.CONFIG.update(web_proxy=1)
try:
    dmn2.save_settings({'web_proxy': 0}, by='t'); e = ''
except Exception as x:
    e = repr(x)
ok('switched off as the pages do: the row kept, off (%s)' % e, st.settings_saved().get('web_proxy') == 0, st.settings_saved().get('web_proxy'))
otp.CONFIG['web_proxy'] = 0
otp.SAVED_KEYS['at'] = 0.0      # as a save on the daemon does (1.0.239's 30 s cache)
ok('...asked to take otp\'s lines out', otp.realip_desired(st) == {'from': [], 'header': '', 'recursive': False})
st.drop_setting('web_proxy'); st.save_setting('web_proxy_from', '10.20.0.0/24')
otp.SAVED_KEYS['at'] = 0.0      # as a save on the daemon does (1.0.239's 30 s cache)
ok('switched off on 1.0.237 (the row dropped, the balancers still named): taken out as well',
   otp.realip_desired(st) == {'from': [], 'header': '', 'recursive': False})
st.drop_setting('web_proxy_from')
for bad in ('Host', 'X-A B', '-x'):
    try:
        otp.check_setting('web_proxy_header', bad); e = ''
    except otp.BadSetting as x:
        e = str(x)
    ok('the header %r refused' % bad, 'header' in e, e)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
