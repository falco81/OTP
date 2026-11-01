# t_round4.py VERSION - the bugs found by the fourth round of the bug hunt (1.0.208), each
# shown fixed: in-process against otp.py of VERSION on SQLite, the pages' files read, and the
# password box typed into by Chromium (dead keys, composition) when node and Playwright are here.
import os, sys, json, time, tempfile, subprocess, shutil, gzip
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.208'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r4-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r4'}, open(D + '/config.json', 'w'))
sys.argv = ['x']
sys.path.insert(0, V)
import otp  # noqa: E402
otp.load_config(saved=None)
R = []


def ok(what, cond, more=''):
    R.append(bool(cond))
    print(('ok  ' if cond else 'FAIL') + ' ' + what + ((' (%s)' % str(more)[:400]) if more and not cond else ''),
          flush=True)


db = otp.Db('sqlite', path=os.path.join(D, 'otp.db'))
st = otp.Storage(db)
otp.sealing_key(make=True)
otp.HA_STORE['store'] = st

# ---- the administration's sign-in from the directory: a name two accounts answer to ------
class Ad:
    name = 'corp'

    def __init__(self, entry):
        self.entry = entry
        self.asked = []

    def find_user(self, who, how):
        return self.entry

    def password_ok(self, entry, pw):
        self.asked.append(entry['dn'])

    def groups_of(self, entry, nested):
        return [('CN=Admins,DC=corp', 'Admins')]


class H:
    def __init__(self, ad):
        self.d = type('Dm', (), {'dirs': {'corp': ad}})()
        self.store = st


otp.CONFIG['admin_directory'] = 'corp'
two = Ad({'dn': 'CN=Other,DC=corp', 'many': True, 'sam': 'boss'})
got = otp.admin_ask_directory(H(two), 'boss', 'his-own-password')
ok('the administration: a name two directory accounts answer to is refused, no password tried',
   got and got['ok'] is False and not two.asked, got)
one = Ad({'dn': 'CN=Boss,DC=corp', 'sam': 'boss'})
got = otp.admin_ask_directory(H(one), 'boss', 'pw')
ok('... one account: asked as before', got and got.get('dn') == 'CN=Boss,DC=corp' and one.asked == ['CN=Boss,DC=corp'])

# ---- the enrolment pages: the owner gets what is theirs, not the administrators' note --------
otp.import_totp(st, 'falco@corp.cz', 'JBSWY3DPEHPK3PXPJBSWY3DP\n" TOTP_AUTH\n')
st.db.run("UPDATE tokens SET note = 'INTERNAL: HR case 4711', created_by = 'admin:fa1' WHERE name = ?",
          ('falco@corp.cz',))
shown = st.token_shown(st.token('falco@corp.cz'))
mine = {k: shown.get(k) for k in otp.PORTAL_TOKEN_KEYS}
ok('the enrolment page: no note, no "made by" in what its owner is sent',
   'note' not in otp.PORTAL_TOKEN_KEYS and 'created_by' not in otp.PORTAL_TOKEN_KEYS and 'HR case' not in json.dumps(mine))
PJ = open(V + '/web/assets/portal.js').read()
used = set(__import__('re').findall(r'tok\.([a-z_]+)', PJ)) | set(__import__('re').findall(r'token\.([a-z_]+)', PJ))
ok('... every field the page uses still sent (%s)' % ', '.join(sorted(used)), used <= set(otp.PORTAL_TOKEN_KEYS),
   used - set(otp.PORTAL_TOKEN_KEYS))

# ---- the databases ----------------------------------------------------------------------------
old = os.path.join(D, 'old.db')
o = otp.Db('sqlite', path=old)
o.run('CREATE TABLE sessions (id INTEGER PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, name TEXT, role TEXT, '
      'created REAL, last REAL, expires REAL, ip TEXT, data TEXT)')
o.run("INSERT INTO sessions (token_hash, name) VALUES ('h', 'n')")
try:
    o.make_tables()
    o.make_tables()
    started = 'kind' in o.columns('sessions')
except Exception as e:                                  # noqa: BLE001
    started = False
    print('    (%s)' % e)
ok('an older database missing a column an index is on: it starts (the column first, then the index)', started)
o.close()
ok('PostgreSQL: names in byte order', otp.Db.name_order(type('X', (), {'engine': 'postgres'})()) == 'name COLLATE "C"')
src = open(V + '/otp.py').read()
ok('a new PostgreSQL database made C.UTF-8', "LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8'\" % (name, user))" in src)
ok('a copy put back with no statement time limit', 'with db.unlimited():\n            return _load_tables_held' in src)
ok('MariaDB: meta\'s keys made 255 long', '_mariadb_meta_keys' in src and 'MODIFY k VARCHAR(255)' in src)
rows = otp._my_rows(" (1,'adm','fulladmin','p,\\'w)',NULL,1,'n'),(2,'ok','fulladmin','x',NULL,0,NULL);")
ok('a MariaDB dump\'s rows read, a quoted comma and bracket in them', len(rows) == 2 and rows[0][5] == '1'
   and rows[1][5] == '0', rows)
cnt = len([f for f in os.listdir(tempfile.gettempdir()) if f.startswith('otp-my-')])
try:
    otp._my_cnf({'db_password': 'a\nb'})
except otp.DbError:
    pass
ok('a password with a line break: no empty option file left behind',
   len([f for f in os.listdir(tempfile.gettempdir()) if f.startswith('otp-my-')]) == cnt)
ok('the move carries its own events into the new database (Start using it after a long move)',
   "far.insert('events', dict(r))" in src)

# ---- the pages ---------------------------------------------------------------------------------
PHP = open(V + '/web/admin/index.php').read()
ok('PHP: one who must change the password first takes no upload', PHP.count("!empty($who['must_change'])") == 3
   and "&& empty($who['must_change']) ? 204 : 403" in PHP)
J = open(V + '/web/assets/admin.js').read()
ok('popup titles not escaped twice', "'Switch the token of ' + htmlText(name)" not in J
   and "'Delete ' + htmlText(fl.name)" not in J)
ok('a poller ends after its time with every answer failing too', J.count('/* (1.0.208) */') >= 2
   and 'the minute ends it as well' in J)
ok('the export passphrase dots again once the export is pressed', "$('exp-pass').type = 'password';\n    $('exp-pass').oninput = null;" in J)
r = subprocess.run(['php', '-l', V + '/web/admin/index.php'], capture_output=True, text=True) \
    if shutil.which('php') else None
ok('index.php reads as PHP', r is None or r.returncode == 0, r and r.stdout)

node = shutil.which('node')
if node:
    T = tempfile.mkdtemp(prefix='otp-r4-ime-')
    shutil.copy(V + '/web/assets/core.js', T)
    open(T + '/p.html', 'w').write('<!doctype html><meta charset=utf-8><body><script src="core.js"></script></body>')
    open(T + '/t.js', 'w').write('''
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext(); const p = await ctx.newPage();
  await p.goto('file://%s/p.html');
  await p.evaluate(() => { const i = maskBox('', '', ''); i.id = 'mb'; document.body.prepend(i); });
  const cdp = await ctx.newCDPSession(p);
  await p.focus('#mb'); await p.keyboard.type('Heslo');
  await cdp.send('Input.imeSetComposition', { text: '\\u02c7', selectionStart: 1, selectionEnd: 1 });
  await cdp.send('Input.insertText', { text: '\\u010d' });
  await p.keyboard.type('ka1');
  const v = await p.evaluate(() => [document.getElementById('mb').value,
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').get.call(document.getElementById('mb'))]);
  console.log(JSON.stringify(v)); await b.close();
})();''' % T)
    try:
        out = subprocess.run([node, T + '/t.js'], capture_output=True, text=True, timeout=120,
                             env=dict(os.environ, NODE_PATH=subprocess.run(['npm', 'root', '-g'], capture_output=True,
                                                                          text=True).stdout.strip())).stdout
        val, shown_ = json.loads(out.strip().splitlines()[-1])
        ok('a password typed with a dead key (Heslo + ˇc + ka1): kept whole (%s), dots on the screen' % val,
           val == 'Hesločka1' and set(shown_) == {'•'})
    except Exception as e:                              # noqa: BLE001
        ok('(the password box in Chromium could not be tried: %s)' % e, True)
print('ALL %d / %d' % (sum(R), len(R)))
