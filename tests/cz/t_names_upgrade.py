# names_letters_kept (1.0.155): an upgrade keeps the people whose names have
# accents or other languages' letters signing in; a new server keeps both off.
import os, sys, tempfile
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.155'
sys.path.insert(0, '/home/claude/build/out/otp-%s' % VER); sys.argv = ['x']
R = []


def ok(w, c):
    R.append(bool(c)); print('ok  ' if c else 'FAIL', w)


def case(names, saved=None):
    os.environ['OTP_STATE'] = tempfile.mkdtemp(prefix='otp-names-')
    import importlib, otp
    importlib.reload(otp)
    otp.CONFIG.update(db_engine='sqlite', names_any_letters=1)
    st = otp.Storage(otp.open_db()); st.db.make_tables(); otp.sealing_key(make=True)
    for n in names:
        otp.Tokens(st).enroll(n, 'test')
    for k, v in (saved or {}).items():
        st.save_setting(k, v, 'admin')
    otp.CONFIG.update(names_any_letters=0, names_czsk_letters=0)
    got = {}

    class D:
        store = st

        def save_settings(self, want, by=''):
            got.update(want)
    otp.names_letters_kept(D())
    again = dict(got)
    otp.names_letters_kept(D())
    return got, again == got, st.get_meta('names:letters:checked')


g, once, m = case(['novak@corp.cz', 'jan'])
ok('a new server, names without accents: both stay off %s' % g, g == {} and m == '1')
g, once, m = case(['novak@corp.cz', 'žofie@corp.cz'])
ok('Czech names there: Czech and Slovak letters switched on %s' % g, g == {'names_czsk_letters': 1})
g, once, m = case(['łukasz@corp.cz'])
ok('a Polish name there: other languages switched on %s' % g, g == {'names_any_letters': 1})
g, once, m = case(['žofie@corp.cz'], saved={'names_czsk_letters': 0})
ok('the administrator chose Czech letters off: left so %s' % g, g == {})
g, once, m = case(['łukasz@corp.cz', 'žofie@corp.cz'], saved={'names_any_letters': 0})
ok('1.0.154 with other languages chosen off: only the Czech letters switched on %s' % g,
   g == {'names_czsk_letters': 1})
print('ALL %d / %d' % (sum(R), len(R)))
