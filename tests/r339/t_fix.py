"""t_fix.py - 1.0.339: the enrolment page's link in a token's mail with its words left empty;
isemon's lines not sent while a target is down counted as dropped; a totpcgi realm that cannot be
made said and the rest imported.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, sys, tempfile, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.339'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r339_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx339', 'api_port': 29961}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)
m.CONFIG.update(mail_from='otp@example.cz', site_name='OTP')
pic = {'uri': 'otpauth://totp/OTP:bob?secret=JBSWY3DPEHPK3PXP&issuer=OTP', 'secret': 'JBSWY3DPEHPK3PXP',
       'issuer': 'OTP', 'digits': 6, 'period': 30}
URL = 'https://otp.example.cz/'


def bodies(msg):
    return (msg.get_body(('html',)).get_content(), msg.get_body(('plain',)).get_content())


for lang in ('cs', 'en'):
    w = dict(m.texts_for('token', lang))
    h, t = bodies(m.token_mail('bob@example.cz', 'bob', pic, lang=lang, pending=True, portal_url=URL, w=w))
    ok('%s: with its words, the link as before' % lang, URL in h and URL in t)
    w['pending'] = ''
    h, t = bodies(m.token_mail('bob@example.cz', 'bob', pic, lang=lang, pending=True, portal_url=URL, w=w))
    ok('%s: its words left empty, the link still there' % lang, URL in h and URL in t, t[-400:])
    h, t = bodies(m.token_mail('bob@example.cz', 'bob', pic, lang=lang, pending=False, portal_url=URL, w=w))
    ok('%s: not to be confirmed: no link' % lang, URL not in h and URL not in t)

src = open(V + '/otp.py').read()
i = src.index('if time.time() < until:\n                    self.missed[key] += 1')
ok('isemon: lines passed over while down counted as dropped', 'self.dropped += 1' in src[i:i + 400])
i = src.index('self.down[key] = (time.time() + wait, wait)\n                self.missed[key] += 1')
ok('isemon: the line that failed counted as dropped', 'self.dropped += 1' in src[i:i + 200])
ok('totpcgi: a realm refused said, the rest imported', "say('realm %s: not imported - %s' % (suffix, e))" in src)
print('ALL %d / %d' % (sum(R), len(R)))
