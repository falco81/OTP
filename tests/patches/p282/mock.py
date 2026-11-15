# 1.0.282 test/mockldap.py: the domain's crossRef (its NetBIOS name not the first part of its DNS name, as
# MERIT_NT is for merit.cz) and a service account holding an SPN - python3 mock.py OUTDIR
import sys
F = sys.argv[1].rstrip('/') + '/test/mockldap.py'
s = open(F).read()


def ed(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


ed("""PARTITIONS = {
    'uPNSuffixes': ['corpnet.cz', 'corpnet.example'],
    'objectClass': ['top', 'crossRefContainer'],
}""", """PARTITIONS = {
    'uPNSuffixes': ['corpnet.cz', 'corpnet.example'],
    'objectClass': ['top', 'crossRefContainer'],
}
# The domain's own entry among the partitions (1.0.282): its NetBIOS name is NOT the first part of its DNS
# name - as MERIT_NT is for merit.cz - which a guess of it got wrong.
CROSSREFS = {
    'CN=CORPNET,CN=Partitions,CN=Configuration,DC=corpnet,DC=loc': {
        'objectClass': ['top', 'crossRef'], 'nETBIOSName': ['CORPNET_NT'], 'dnsRoot': ['corpnet.loc'],
        'nCName': ['DC=corpnet,DC=loc'],
    },
}""")
ed("""            if not base or base.lower().startswith('cn=partitions,'):""",
   """            try:
                _sc = isemon._ber_int_of(_scope)
            except Exception:
                _sc = 2
            if not base or (base.lower().startswith('cn=partitions,') and _sc == 0):""")
ed("""            everything.update(SITES)""", """            everything.update(SITES)
            everything.update(CROSSREFS)
            everything.update(SERVICES)""")
ed("""# The people a VPN realm asks about:""", """# A service account holding the pages' SPN (1.0.282): what the keytab guide names.
SERVICES = {
    'CN=svc-otp-web,OU=Service,DC=corpnet,DC=loc': {
        'sAMAccountName': ['svc-otp-web'], 'objectClass': ['top', 'person', 'organizationalPerson', 'user'],
        'servicePrincipalName': ['HTTP/otp.corpnet.loc'], 'userAccountControl': ['66048'],
        'memberOf': [], '_password': 'svc-otp-web-password-1',
    },
}

# The people a VPN realm asks about:""")
open(F, 'w').write(s)
print('mock patched')
