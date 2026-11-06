"""t_r254b.py - 1.0.254, after the hunt: no passkey while another node runs a version before
1.0.254 (it would read a passkey as no second step); going back below 1.0.254 refused while an
account signs in with one; a browser answer nested too deep is a wrong answer, not a 500."""
import sys, json, base64
V = '/home/claude/build/out/otp-%s' % (sys.argv[1] if len(sys.argv) > 1 else '1.0.254')
sys.path.insert(0, V)
sys.argv = ['x']
import otp  # noqa: E402

R = []


def ok(n, c, m=''):
    R.append(bool(c)); print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:300]))


class Db:
    def __init__(self, rows):
        self.r = rows

    def rows(self, sql, *a):
        if 'adm2fa:' in sql:
            return self.r
        return []


class St:
    def __init__(self, rows=()):
        self.db = Db(list(rows))


class H:
    def __init__(self, host='otp.firma.cz'):
        self.headers = {'X-Otp-Host': host}
        self.store = St()


nodes = []
otp.ha_nodes = lambda store: nodes
otp.CONFIG.update(admin_2fa=1, admin_2fa_passkey=1, admin_2fa_app=1, ha_mode='replicated')
nodes[:] = [{'name': 'nodea', 'me': True, 'age': 0, 'version': '1.0.254'},
            {'name': 'nodeb', 'me': False, 'age': 4, 'version': '1.0.253'}]
ok('the other node on 1.0.253: named', otp.mfa_old_nodes(St()) == ['nodeb'], otp.mfa_old_nodes(St()))
ok('...no passkey offered', 'passkey' not in otp.mfa_methods(H()), otp.mfa_methods(H()))
nodes[1]['version'] = '1.0.254'
ok('both on 1.0.254: the passkey offered', 'passkey' in otp.mfa_methods(H()) and not otp.mfa_old_nodes(St()))
nodes[1].update(version='1.0.250', age=3 * 86400)
ok('a node not heard from for days does not hold it back', 'passkey' in otp.mfa_methods(H()))
nodes[1].update(version='1.0.253', age=4)
otp.CONFIG['ha_mode'] = ''
ok('standalone: nothing asked of the nodes, the passkey offered', 'passkey' in otp.mfa_methods(H()) and otp.mfa_old_nodes(St()) == [])
ok('...the command line (no page) as before', 'passkey' in otp.mfa_methods())
ok('by an address: not offered', 'passkey' not in otp.mfa_methods(H('10.0.0.5')))

pk = {'k': 'adm2fa:novak', 'v': json.dumps({'kind': 'passkey', 'keys': []})}
app = {'k': 'adm2fa:svoboda', 'v': json.dumps({'kind': 'app', 'secret': 'x'})}
why = ' | '.join(otp.downgrade_why_not(St([pk, app]), '1.0.253'))
ok('going back below 1.0.254 with a passkey: refused, the account named', 'novak signs in' in why and 'svoboda' not in why and 'reset its second step' in why, why)
why = ' | '.join(otp.downgrade_why_not(St([app]), '1.0.253'))
ok('...without one: not for that', 'passkey' not in why, why)
two = dict(pk, k='adm2fa:dvorak')
why = ' | '.join(otp.downgrade_why_not(St([pk, two]), '1.0.252'))
ok('...two accounts: both named', 'dvorak, novak sign in' in why and 'their second step' in why, why)

deep = ('[' * 5000 + ']' * 5000).encode()
try:
    otp.wa_client(deep, 'webauthn.get', 'x', 'https://otp.firma.cz')
    ok('an answer nested too deep: refused', False)
except ValueError:
    ok('an answer nested too deep: refused as a wrong answer (no 500)', True)
except RecursionError:
    ok('an answer nested too deep: refused as a wrong answer (no 500)', False, 'RecursionError')
ok('the passkey setting signed with the guard on, as its siblings', otp.dbguard_setting('admin_2fa_passkey') if hasattr(otp, 'dbguard_setting') else 'admin_2fa_passkey' in otp.DBGUARD_SETTINGS)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
