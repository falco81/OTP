"""Snapshot of everything that is configuration or credentials, comparable across a restore."""
import sys, os, json, hashlib
OUT = sys.argv[1]
sys.argv=['otp']; sys.path.insert(0, os.environ.get('OTP_LIB','/usr/local/lib/otp'))
import otp
otp.load_config()
st = otp.Storage(otp.open_db())
VOL = {'id','last_seen','last_in','last_from','last_used','last_how','last_client','at','created','pw','cols_at',
       'key_at','state_at','lock_at','scratch_at','fail_times','failures','locked_until','last_step','scratch','scratch_sealed','secret','pending_secret','pending_scratch','bind_pw','prefs','cols'}
def clean(rows, key='name'):
    out={}
    for r in rows:
        out[str(r.get(key))] = {k:v for k,v in sorted(r.items()) if k not in VOL}
    return out
snap = {}
snap['settings'] = st.settings_saved()
snap['clients'] = clean(st.clients(with_secret=True))
snap['realms'] = clean(st.realms())
snap['directories'] = clean(st.directories(with_secret=True))
for d in st.directories(with_secret=True):
    snap['directories'][d['name']]['bind_pw_plain'] = d.get('bind_pw')
snap['accounts'] = clean(st.db.rows('SELECT * FROM accounts'))
for a in st.db.rows('SELECT name, pw FROM accounts'):
    snap['accounts'][a['name']]['pw_hash'] = hashlib.sha256(str(a['pw']).encode()).hexdigest()[:12]
toks = {}
for t in st.db.rows('SELECT * FROM tokens'):
    b = otp.token_bind(t['name'])
    codes = otp.open_codes(t.get('scratch_sealed'), b)
    toks[t['name']] = {'state': t['state'], 'secret': otp.unseal_secret(t.get('secret') or '', b),
                       'pending': otp.unseal_secret(t.get('pending_secret') or '', b) if t.get('pending_secret') else None,
                       'digits': t['digits'], 'period': t['period'], 'algorithm': t['algorithm'],
                       'scratch_left': t['scratch_left'], 'codes': sorted(c['c'] for c in (codes or []) if not c.get('used')),
                       'display': t.get('display'), 'note': t.get('note'), 'window': t.get('window_steps')}
snap['tokens'] = toks
snap['meta'] = {r['k']: r['v'] for r in st.db.rows('SELECT k, v FROM meta') if r['k'].split(':')[0] in ('web','fw','mail_ca','disabled_from','staged','mailed')}
snap['counts'] = {t: st.db.value('SELECT COUNT(*) FROM %s' % t) for t in otp.TABLES}
json.dump(snap, open(OUT,'w'), indent=1, sort_keys=True, default=str)
print('snap', OUT, {k: len(v) if isinstance(v, dict) else v for k, v in snap.items() if k!='counts'}, snap['counts'])
