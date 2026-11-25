"""t_fix.py - 1.0.338: an SMS of a code without {code} refused; a prompt measured with a real-length
address; the SSH prompt cut on a letter with its ": "; the editor's SMS count as sent.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, subprocess, sys, tempfile, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.338'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r338_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx338', 'api_port': 29960}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)
m.load_config(saved=None)

# ==== 1 every default still passes
bad = []
for msg in m.TEXT_MESSAGES:
    for lang in ('cs', 'en'):
        d = m.text_defaults(msg['group'], lang)
        for f in msg['fields']:
            if f[0] not in d:
                continue
            try:
                m.text_check(f, d[f[0]])
            except ValueError as e:
                bad.append((msg['id'], lang, f[0], str(e)))
ok('every default text passes', not bad, bad)

sms = [(msg, f) for msg in m.TEXT_MESSAGES for f in msg['fields'] if f[4] == 'sms' and 'code' in f[3]]
ok('there are SMS texts of a code', sms)
f = sms[0][1]
try:
    m.text_check(f, 'Váš kód pro VPN ({site}), platí {minutes} min')
    e = None
except ValueError as x:
    e = str(x)
ok('an SMS without {code} refused', e and 'the code is what this SMS is for' in e, e)
ok('an SMS with {code} taken', m.text_check(f, 'Kód {code}') == 'Kód {code}')

pr = [f for msg in m.TEXT_MESSAGES for f in msg['fields'] if f[4] == 'prompt' and 'dest' in f[3]]
if pr:
    long_ = 'ž' * 100 + ' {dest}'                          # 200 bytes: fits with the sample, not a real address
    try:
        m.text_check(pr[0], long_)
        e = None
    except ValueError as x:
        e = str(x)
    ok('a prompt too long with a real address refused', e and '253' in e, e)

# ==== 2 the SSH prompt
attr = m.ssh_prompt_attr('Zadejte kód z aplikace ' + 'žluťoučký kůň ' * 30)
n = attr[1]
text = attr[2:n]
try:
    words = text.decode('utf-8')
    e = None
except UnicodeDecodeError as x:
    e = x
ok('the SSH prompt is whole letters', e is None and len(text) <= 253, e)
ok('the SSH prompt keeps its ": "', e is None and words.endswith(': '), words[-10:] if e is None else '')
short = m.ssh_prompt_attr('Kód')
ok('a short prompt as before', short[2:short[1]] == 'Kód: '.encode('utf-8'))

# ==== 3 the editor's count
js = open(V + '/web/assets/admin.js').read()
i = js.index('function txPlainSms(t) {')
body = js[i:js.index('\n}\n', i) + 3]
out = subprocess.run(['node', '-e', body + 'var TX={data:{sms_plain:1}};process.stdout.write(txPlainSms("Kód – „x“ žluť"));'],
                     capture_output=True, text=True)
ok('the editor makes the SMS plain as it is sent', out.stdout == m.sms_plain('Kód – „x“ žluť') if m.CONFIG.get('sms_plain', 1) else True,
   (out.stdout, out.stderr[-200:]))

cs = json.load(open(V + '/web/lang/cs.json'))
pats = {v['source'] for v in cs['patterns'].values()}
ok('its words in Czech', '{0}: the code is what this SMS is for - put it in' in pats)
print('ALL %d / %d' % (sum(R), len(R)))
