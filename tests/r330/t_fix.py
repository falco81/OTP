"""t_fix.py - 1.0.330: an AD account's primary group among its groups (primaryGroupID).
The built otp.py loaded as a module; the directory a stand-in that answers by the filter's bytes.

    python3 t_fix.py VERSION
"""
import importlib.util, json, os, shutil, sys, tempfile, atexit
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.330'
V = '/home/claude/build/out/otp-%s' % VER
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:400]), flush=True)


TOP = tempfile.mkdtemp(prefix='t_r330_')
atexit.register(lambda: shutil.rmtree(TOP, True))
D = TOP + '/state'
os.makedirs(D + '/run')
json.dump({'db_engine': 'sqlite', 'node_name': 'fx330', 'api_port': 29953}, open(D + '/config.json', 'w'))
os.environ.update(OTP_STATE=D, OTP_CONFIG=D + '/config.json', OTP_LOGDIR=D, OTP_RUN=D + '/run', OTP_STATE_DIR=D)
sys.argv = ['otp']
spec = importlib.util.spec_from_file_location('otp', V + '/otp.py')
m = importlib.util.module_from_spec(spec)
sys.modules['otp'] = m
spec.loader.exec_module(m)

USER_SID = '01050000000000051500000057040000ae080000050d000051040000'      # ...-1105
DU_SID = bytes.fromhex('01050000000000051500000057040000ae080000050d000001020000')   # ...-513
DU = 'CN=Domain Users,CN=Users,DC=corpnet,DC=loc'
VPN = 'CN=VPN_ALL,OU=Groups,DC=corpnet,DC=loc'            # has Domain Users in it
OWN = 'CN=VPN_2FACT_USERS,OU=Groups,DC=corpnet,DC=loc'    # the account's own group
USER = 'CN=Falco Tester,OU=People,DC=corpnet,DC=loc'

# 1 the SID worked out
ok('primary_group_sid: the account SID with RID 513', m.primary_group_sid(USER_SID, '513') == DU_SID)
ok('primary_group_sid: nothing without primaryGroupID', m.primary_group_sid(USER_SID, '') == b'')
ok('primary_group_sid: nothing without objectSid', m.primary_group_sid('', '513') == b'')
ok('primary_group_sid: a broken SID refused', m.primary_group_sid('0105000000', '513') == b''
   and m.primary_group_sid(USER_SID[:-2], '513') == b'' and m.primary_group_sid(USER_SID, 'x') == b'')
ok('USER_ATTRS asks primaryGroupID', 'primaryGroupID' in m.USER_ATTRS)


class Link(object):
    def __init__(self, asks):
        self.asks = asks

    def search(self, base, flt, attrs, scope=2, limit=0, paged=False):
        self.asks.append(flt)
        rows = []
        if DU_SID in flt:                                   # the primary group by its SID
            return [{'dn': DU, 'attrs': {'cn': ['Domain Users']}}]
        if USER.encode() in flt:
            rows.append({'dn': OWN, 'attrs': {'cn': ['VPN_2FACT_USERS']}})
        if DU.encode() in flt:
            rows.append({'dn': VPN, 'attrs': {'cn': ['VPN_ALL']}})
        return rows


def directory():
    d = m.Directory({'name': 'ad', 'hosts': 'x', 'base': 'OU=People,DC=corpnet,DC=loc'})
    asks = []
    d.asked = lambda do: do(Link(asks))
    return d, asks


# 2 an AD account: its primary group, and the groups that one is in
d, asks = directory()
e = {'dn': USER, 'member_of': [OWN], 'primary_sid': m.primary_group_sid(USER_SID, '513').hex()}
got = {g for g, _ in d.groups_of(e, True)}
ok('nested: own group, Domain Users, and the group Domain Users is in', got == {OWN, DU, VPN}, got)
n = len(asks)
d.groups_of(e, True)
ok('nested: kept a minute, not asked again', len(asks) == n, asks)
got = {g for g, _ in d.groups_of(e, False)}
ok('not nested: memberOf and the primary group', got == {OWN, DU}, got)
ok('the entry stays JSON (no bytes in it)', json.dumps(e) and True)

# 3 not AD (no primaryGroupID): asked exactly as before
d, asks = directory()
e2 = {'dn': USER, 'member_of': [OWN], 'primary_sid': ''}
got = {g for g, _ in d.groups_of(e2, True)}
ok('no primaryGroupID: own groups only, one search', got == {OWN} and len(asks) == 1, (got, asks))
ok('no primaryGroupID: the filter is the old one', asks[0] == m.ldap_and(
    m.ldap_equal('objectClass', 'group'), m.ldap_in_chain('member', USER)))
d, asks = directory()
ok('no primaryGroupID, not nested: memberOf, nothing asked',
   [g for g, _ in d.groups_of(e2, False)] == [OWN] and asks == [])
d, asks = directory()
ok('an entry of before (no primary_sid key)', {g for g, _ in d.groups_of({'dn': USER, 'member_of': [OWN]}, True)} == {OWN})

# 4 the primary group not found, or its search failing: the groups as before
class Quiet(Link):
    def search(self, base, flt, attrs, **kw):
        if DU_SID in flt:
            raise m.LdapError('no such attribute')
        return Link.search(self, base, flt, attrs, **kw)
d, asks = directory()
d.asked = lambda do: do(Quiet(asks))
got = {g for g, _ in d.groups_of(e, True)}
ok('primary search failing: the other groups still', got == {OWN}, got)

# 5 group rules: Domain Users now passes
d, asks = directory()
have = d.groups_of(e, True)
ok('a realm given Domain Users (by DN) passes', m.group_matches([DU], have) == DU)
ok('a realm given VPN_ALL (Domain Users in it) passes', m.group_matches([VPN], have) == VPN)
print('ALL %d / %d' % (sum(R), len(R)))
