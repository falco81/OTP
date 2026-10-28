import sys, os, json
sys.argv=['otp']; sys.path.insert(0,'/usr/local/lib/otp')
os.environ.setdefault('OTP_CONFIG','/etc/otp/config.json')
import otp
otp.load_config() if hasattr(otp,'load_config') else None
st=otp.Storage(otp.open_db(otp.CONFIG))
cl=[c for c in st.clients(with_secret=True) if c['address'].startswith('127.0.0.1')]
print(json.dumps({'secret': cl[0]['secret'], 'client': cl[0]['name']}))
