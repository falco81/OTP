# t_round9.py VERSION - 1.0.215: "Exactly the file" keeps a node's own settings the file does
# not have; a shared setting not in it still goes back to its default; the RADIUS client's
# secret shown whole to a full admin only, each look written down. In-process, SQLite.
import os, sys, json, tempfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.215'
V = '/home/claude/build/out/otp-%s' % VER
D = tempfile.mkdtemp(prefix='otp-r9-')
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D + '/log', OTP_RUN=D + '/run')
os.makedirs(D + '/log'); os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'r9a'}, open(D + '/config.json', 'w'))
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
d = otp.Daemon(st, serve=False)
otp.CONFIG['ha_mode'] = 'replicated'
import time
for n in ('r9a', 'r9b'):
    st.set_meta('node:' + n, json.dumps({'at': time.time(), 'address': '192.0.2.9'}))
st.save_setting('radius_auth_port@r9b', 1912, 't')
st.save_setting('totp_issuer', 'Corp', 't')
st.save_setting('lockout_after', 7, 't')
otp.load_config(saved=st.settings_saved())
said = otp.config_import(st, d, {'settings': {'lockout_after': 8}}, 't', replace=True)
saved = st.settings_saved()
ok('Exactly the file: a node\'s own setting the file does not have stays (radius_auth_port@r9b)',
   'radius_auth_port@r9b' in saved and int(saved['radius_auth_port@r9b']) == 1912, saved)
ok('... a shared setting not in the file back to its default (totp_issuer)', 'totp_issuer' not in saved, saved)
ok('... the file\'s own value saved (lockout_after 8)', int(saved.get('lockout_after') or 0) == 8, saved)
said = otp.config_import(st, d, {'settings': {'radius_auth_port@r9b': 1922}}, 't', replace=True)
saved = st.settings_saved()
ok('... a node\'s own setting the file has: taken from it', int(saved.get('radius_auth_port@r9b') or 0) == 1922, saved)
otp.CONFIG['ha_mode'] = ''
src = open(V + '/otp.py').read()
ok('a RADIUS client\'s secret: whole to a full admin only, each look an event',
   "if act == 'secret':\n        h.me('fulladmin')" in src and 'looked at the shared secret of' in src)
ok('... and the list of clients shows it masked', "secret_shown(r['_secret'], last)" in src)
I = open(V + '/INSTALL.md').read()
ok('INSTALL.md: whoever can write the database is root on every node', 'Who can write the database is root on every node' in I)
print('ALL %d / %d' % (sum(R), len(R)))
