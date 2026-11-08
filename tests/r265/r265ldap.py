#!/usr/bin/env python3
"""The product's test/mockldap.py with N extra people (zzr265uNNNNN) and an index, so a
search for one person does not walk (and copy) every entry - otherwise the mock itself,
not otp, would be what the load test measures. Usage: r265ldap.py PORT N MOCKDIR"""
import sys, threading
PORT, N, MOCKDIR = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
sys.path.insert(0, MOCKDIR + '/test')
sys.argv = [sys.argv[0]]
import mockldap as M                                    # noqa: E402

TL = threading.local()
for i in range(N):
    sam = 'zzr265u%05d' % i
    M.PEOPLE['CN=%s,OU=Load,DC=corpnet,DC=loc' % sam] = {
        'sAMAccountName': [sam], 'userPrincipalName': [sam + '@corpnet.cz'],
        'displayName': ['Load %05d' % i], 'objectClass': ['top', 'person', 'user'],
        'userAccountControl': ['512'], 'memberOf': [], '_password': 'Pw-r265-%05d' % i}
IDX = {}
for dn, a in M.PEOPLE.items():
    for k in ('sAMAccountName', 'userPrincipalName', 'mail'):
        for v in a.get(k, []):
            IDX.setdefault((k.lower(), v.lower()), set()).add(dn)
    IDX.setdefault(('distinguishedname', dn.lower()), set()).add(dn)


class People(dict):
    def _hint(self):
        h = getattr(TL, 'hint', None)
        return None if h is None else [d for d in h if dict.__contains__(self, d)]

    def keys(self):
        h = self._hint()
        return dict.keys(self) if h is None else h

    def __iter__(self):
        return iter(self.keys())

    def items(self):
        h = self._hint()
        return dict.items(self) if h is None else [(d, dict.__getitem__(self, d)) for d in h]

    def get(self, dn, default=None):
        got = dict.get(self, dn)
        if got is None:
            for d in IDX.get(('userprincipalname', str(dn).lower()), ()):
                got = dict.__getitem__(self, d)
        TL.hint = set()         # the bind's own walk after this finds nothing more: get() looked
        return got if got is not None else default


def cand(f):
    op = f.get('op')
    if op == '=':
        a = f['attr'].lower()
        if a == 'objectclass' and f['value'].lower() == 'group':
            return set()
        if a in ('samaccountname', 'userprincipalname', 'mail', 'distinguishedname'):
            return set(IDX.get((a, f['value'].lower()), ()))
        return None
    if op == 'and':
        sets = [s for s in (cand(p) for p in f['parts']) if s is not None]
        if not sets:
            return None
        out = sets[0]
        for s in sets[1:]:
            out = out & s
        return out
    if op == 'or':
        sets = [cand(p) for p in f['parts']]
        if any(s is None for s in sets):
            return None
        return set().union(*sets)
    return None


_unpack = M._unpack_filter


def unpack(body, tag):
    TL.depth = getattr(TL, 'depth', 0) + 1
    try:
        f = _unpack(body, tag)
    finally:
        TL.depth -= 1
    if TL.depth == 0:
        TL.hint = cand(f)
    return f


M._unpack_filter = unpack
M.PEOPLE = People(M.PEOPLE)
port, stop = M.serve(PORT)
print('r265 mock directory on 127.0.0.1:%d with %d load people' % (port, N), flush=True)
threading.Event().wait()
