# fake_node.py add|drop - another node's heartbeat in the installed otp's database (as if one of a cluster)
import sys, os, json, time
os.environ.setdefault('OTP_CONFIG', '/etc/otp/config.json')
sys.argv = ['x']
sys.path.insert(0, '/usr/local/lib/otp')
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db(), quick=True)
if sys.argv[0] and len(sys.argv) and 'drop' in os.environ.get('X', '') :
    pass
what = (sys.orig_argv[-1] if hasattr(sys, 'orig_argv') else 'add')
if what == 'drop':
    st.db.run("DELETE FROM meta WHERE k = 'node:wiz-other'")
else:
    st.set_meta('node:wiz-other', json.dumps({'at': time.time(), 'address': '192.0.2.99', 'version': otp.__version__}))
print(what, 'done')
