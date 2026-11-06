"""t_tokens.py - 1.0.256, group "tokens": S1 the owner inside an exported .totp file (a renamed
entry of a locked ZIP refused, old exports still taken, with a word where locked), S2 no switch
of token_names_case back to small letters over tokens named with capitals, S3 the replication
trigger stamps the key group for the waiting recovery codes and the name, S4 the database with
its key only where keys may be shown. Pure Python: parts exec'd with stubs, no daemon, no ports."""
import ast, base64, io, json, os, re, sys, time, zipfile, hashlib, hmac, struct, zlib, binascii
import unicodedata, secrets

PARTS = '/home/claude/build/parts'
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


def src_of(fname):
    return open(os.path.join(PARTS, fname), encoding='utf-8').read()


def defs(fname, names):
    """The top-level functions/classes named, out of a part, without their decorators."""
    text = src_of(fname)
    tree = ast.parse(text)
    lines = text.splitlines(True)
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            out.append(''.join(lines[node.lineno - 1:node.end_lineno]))
    missing = set(names) - set(re.findall(r'^(?:def|class) (\w+)', ''.join(out), re.M))
    assert not missing, missing
    return '\n\n'.join(out)


class BadSetting(Exception):
    pass


CONFIG = {'token_names_case': 'lower', 'admin_show_key': 1}
g = {'__name__': 'tt', 'CONFIG': CONFIG, 'BadSetting': BadSetting, 'os': os, 're': re,
     'json': json, 'time': time, 'io': io, 'zipfile': zipfile, 'base64': base64,
     'binascii': binascii, 'struct': struct, 'zlib': zlib, 'hashlib': hashlib, 'hmac': hmac,
     'unicodedata': unicodedata, 'secrets': secrets,
     'DEFAULTS': {'token_names_case': 'lower'}}
exec(src_of('88k_zipaes.py'), g)
exec(defs('50_storage.py', ['norm_name', 'token_case_problem']), g)
exec(defs('80_daemon.py', ['parse_totp_file']), g)
exec(defs('90_api.py', ['ApiError', 'totp_file_text', 'totp_file_name', 'totp_file_owner',
                        'totp_file_said_owner', 'totp_files_in_zip', '_token_import',
                        '_settings_do', '_db_download_ticket']), g)
g['b32_clean'] = lambda s: re.sub(r'[^A-Z2-7]', '', str(s).upper())
ApiError = g['ApiError']
SECRET = 'JBSWY3DPEHPK3PXPJBSWY3DP'

# ---- S1: the owner inside the file --------------------------------------------------------
g['unseal_secret'] = lambda v, bind: SECRET if v else ''
g['token_bind'] = lambda n: n
g['codes_open'] = lambda tok: [{'c': '12345678', 'used': False}, {'c': '87654321', 'used': True}]


class Tokens:
    @staticmethod
    def window(tok):
        return 1


g['Tokens'] = Tokens
tok = {'name': "o'neil+1@x.cz", 'secret': 'sealed', 'digits': 6, 'period': 30,
       'algorithm': 'SHA1', 'state': 'active', 'last_step': 5}
text = g['totp_file_text'](tok)
ok('S1 export writes " OTP_NAME, quoted as the file name',
   '" OTP_NAME o%27neil%2B1@x.cz\n' in text, text)
ok('S1 the line reads back as the owner', g['totp_file_said_owner'](text) == ["o'neil+1@x.cz"])
ok('S1 a file without it names nobody', g['totp_file_said_owner'](SECRET + '\n" TOTP_AUTH\n') is None)
sec, opts, codes = g['parse_totp_file'](text)
ok('S1 the importer (as before 1.0.256) passes the line by: key and codes the same',
   sec == SECRET and codes == ['12345678'] and 'OTP_NAME' in opts, (sec, codes))
old_text = re.sub(r'^" OTP_NAME .*\n', '', text, flags=re.M)
ok('S1 old-style text the same but for the line', g['parse_totp_file'](old_text)[2] == codes)

imported = []


def fake_import(store, name, text, by='import', replace=False):
    imported.append(name)
    return 'imported, 1 recovery code(s)'


class Store:
    def __init__(self, names=()):
        self.names = list(names)
        self.events = []

    def add_event(self, *a, **k):
        self.events.append(a)

    def token(self, n):
        return None

    class _DB:
        def __init__(self, outer):
            self.outer = outer

        def rows(self, sql, args=()):
            assert sql == 'SELECT name FROM tokens'
            return [{'name': n} for n in self.outer.names]

    @property
    def db(self):
        return Store._DB(self)


class D:
    def __init__(self):
        self.saved = []

    def fill_names_later(self, names, by=''):
        pass

    def save_settings(self, asked, **k):
        self.saved.append(asked)
        return {'message': 'saved'}


class H:
    def __init__(self, body, store=None):
        self._b = body
        self.store = store or Store()
        self.d = D()

    def me(self, role=''):
        return {'name': 'admin', 'role': 'fulladmin', 'id': 's1'}

    def body(self):
        return self._b


g['import_totp'] = fake_import
g['tokens_backup_open'] = lambda text, phrase: None
g['LIST_FIELDS'] = {}
g['LIST_WORD_COLUMNS'] = {}


def run_import(files, phrase='passphrase1'):
    del imported[:]
    return g['_token_import'](H({'files': files, 'passphrase': phrase}))['done']


def zipped(entries, phrase='passphrase1'):
    raw = g['zip_aes_write']([(n, t.encode()) for n, t in entries], phrase)
    return {'name': 'export.zip', 'zip': base64.b64encode(raw).decode()}


alice = g['totp_file_text'](dict(tok, name='alice@x.cz'))
done = run_import([zipped([('bob@x.cz.totp', alice)])])
ok('S1 a renamed entry of a locked ZIP is refused', imported == [] and any(
    d['name'] == 'bob@x.cz' and d['said'].startswith('not imported: the file is named for bob@x.cz')
    and 'alice@x.cz' in d['said'] for d in done), done)
done = run_import([zipped([('alice@x.cz.totp', alice)])])
done = run_import([{'name': 'bob@x.cz.totp', 'text': alice}])
ok('S1 a plain file renamed on purpose (not locked): imported by its name, as before', imported == ['bob@x.cz'], done)
done = run_import([zipped([('alice@x.cz.totp', alice)])])
ok('S1 the entry under its own name is imported, no warning',
   imported == ['alice@x.cz'] and len(done) == 1 and done[0]['said'].startswith('imported'), done)
CONFIG['token_names_case'] = 'lower'
done = run_import([zipped([('Alice@X.cz.totp', alice)])])
ok('S1 same owner in other letters (small letters) imported', imported == ['Alice@X.cz'], done)
old_alice = re.sub(r'^" OTP_NAME .*\n', '', alice, flags=re.M)
done = run_import([zipped([('alice@x.cz.totp', old_alice), ('carol@x.cz.totp', old_alice)])])
ok('S1 an old locked export is imported as before', imported == ['alice@x.cz', 'carol@x.cz'], done)
ok('S1 ...with one warning for the ZIP, after its files',
   [d for d in done if 'before 1.0.256' in d['said']] == [
       {'name': 'export.zip', 'said': 'no owner written inside (an otp export before 1.0.256, '
                                      'or a folder zipped): the owner is read from the file '
                                      'name only'}] and done[-1]['name'] == 'export.zip',
   done)
done = run_import([{'name': 'dave@x.cz.totp', 'text': old_alice}])
ok('S1 a plain totpcgi file: imported, no warning',
   imported == ['dave@x.cz'] and len(done) == 1, done)
done = run_import([{'name': 'dave@x.cz.totp', 'text': alice}])
ok('S1 a plain file naming another inside: imported by its name, as before (not locked)',
   imported == ['dave@x.cz'], done)
two = alice.replace('" TOTP_AUTH', '" OTP_NAME bob@x.cz\n" TOTP_AUTH')
done = run_import([zipped([('alice@x.cz.totp', two)])])
ok('S1 a second OTP_NAME saying another: refused', imported == [], done)
empty = alice.replace('" OTP_NAME alice@x.cz', '" OTP_NAME')
done = run_import([zipped([('alice@x.cz.totp', empty)])])
ok('S1 an empty OTP_NAME: refused', imported == [], done)
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as z:
    z.writestr('erin@x.cz.totp', old_alice)
done = run_import([{'name': 'plain.zip', 'zip': base64.b64encode(buf.getvalue()).decode()}])
ok('S1 an unlocked ZIP of old files: imported, no "before 1.0.256" warning',
   imported == ['erin@x.cz'] and not any('before 1.0.256' in d['said'] for d in done), done)

# ---- S2: token_names_case back to small letters -------------------------------------------
tcp = g['token_case_problem']
CONFIG['token_names_case'] = 'as-typed'
st = Store(['novak@x.cz', 'Novak@x.cz', 'Žofie', 'b'])
said = tcp(st, 'lower')
ok('S2 refused while names with capitals are there, counted and named',
   said.startswith('2 token(s) have capital letters') and 'Novak@x.cz' in said and
   'Žofie' in said and 'Move to' in said, said)
ok('S2 none with capitals: allowed', tcp(Store(['a@x', 'žofie']), 'lower') == '')
ok('S2 staying as-typed: no question', tcp(st, 'as-typed') == '')
CONFIG['token_names_case'] = 'lower'
ok('S2 already small letters: no question (an unrelated save not stopped)', tcp(st, 'lower') == '')
CONFIG['token_names_case'] = 'as-typed'
g['NodeMoved'] = type('NodeMoved', (Exception,), {})
g['HiSecConflict'] = type('HiSecConflict', (Exception,), {})
g['is_masked'] = lambda v: False
h = H({'settings': {'token_names_case': 'lower'}}, st)
try:
    g['_settings_do'](h)
    ok('S2 the settings page refuses the save', False, 'saved')
except ApiError as e:
    ok('S2 the settings page refuses the save (400, nothing saved)',
       e.status == 400 and h.d.saved == [] and 'nothing saved' in str(e), e)
h = H({'settings': {'token_names_case': 'lower'}}, Store(['a@x']))
ok('S2 ...and saves it where all are small letters', g['_settings_do'](h) == {'message': 'saved'}
   and h.d.saved == [{'token_names_case': 'lower'}])
h = H({'settings': {'site_name': 'x'}}, st)
ok('S2 another setting saved as ever', g['_settings_do'](h) == {'message': 'saved'})
api = src_of('90_api.py')
ok('S2 the configuration import checks it before anything is saved',
   re.search(r"case_to = odict\(conf.get\('settings'\)\).get\('token_names_case'\)", api) and
   api.index('token_case_problem(store, case_to)') < api.index("daemon.save_settings(want, by, node='*')"))
CONFIG['token_names_case'] = 'lower'

# ---- S3: the replication trigger ----------------------------------------------------------
db = src_of('20_db.py')
fn = db[db.index('CREATE OR REPLACE FUNCTION otp_keep_used()'):]
local = fn[:fn.index("  IF TG_OP = 'INSERT' THEN\n    RETURN NEW;")]
bump = local[local.index('IF NEW.secret IS DISTINCT FROM OLD.secret'):local.index('NEW.key_at := GREATEST')]
ok('S3 key_at stamped for pending_scratch', 'NEW.pending_scratch IS DISTINCT FROM OLD.pending_scratch' in bump)
ok('S3 key_at stamped for the name', 'NEW.name IS DISTINCT FROM OLD.name' in bump)
ok('S3 the old conditions kept', all(x in bump for x in (
    'NEW.secret IS DISTINCT', 'NEW.pending_secret IS DISTINCT', 'NEW.kind IS DISTINCT',
    'NEW.dest IS DISTINCT')))
ok('S3 no ? or % in the function body (the driver would take them for parameters)',
   '?' not in fn[:fn.index('END $f$')] and '%' not in fn[:fn.index('END $f$')])
ok('S3 the body is put in with CREATE OR REPLACE at each schema run (an upgrade gets it)',
   'CREATE OR REPLACE FUNCTION otp_keep_used()' in db and 'self._pg_keep_used()' in db)

# ---- S4: the database with its key ---------------------------------------------------------
class Checked(Exception):
    pass


def pchk(p):
    raise Checked()


g['dbkey_passphrase_checked'] = pchk
CONFIG['admin_show_key'] = 0
try:
    g['_db_download_ticket'](H({}), {'name': 'admin'}, {'passphrase': 'x' * 12})
    ok('S4 refused with showing keys off', False)
except ApiError as e:
    ok('S4 refused with showing keys off (403, the token exports\' words)', e.status == 403 and
       str(e) == 'showing the keys of tokens is switched off (Settings - Tokens)', e)
except Checked:
    ok('S4 refused with showing keys off', False, 'went on')
CONFIG['admin_show_key'] = 1
try:
    g['_db_download_ticket'](H({}), {'name': 'admin'}, {'passphrase': 'x' * 12})
    ok('S4 allowed with showing keys on', False)
except Checked:
    ok('S4 allowed with showing keys on (goes on to the passphrase)', True)
dl = api[api.index('def _db_download(h)'):api.index('def _db_made_now')]
ok('S4 the download without the key not touched', 'admin_show_key' not in dl)

print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
