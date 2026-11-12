# ui_chain_restore.py SAVED - the node's certificate row put back as it was before the UI test (signed as otp signs).
import sys, json
SAVED = sys.argv[1]
sys.path.insert(0, '/usr/local/lib/otp'); sys.argv = ['x']
import otp
otp.load_config(saved=None)
st = otp.Storage(otp.open_db())
k, v = json.load(open(SAVED))
st.set_meta(k, v)
print('put back', k)
