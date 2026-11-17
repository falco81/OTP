# 1.0.297: the portal - "Another address or way" keeps the proof of the old token.
#   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('90_api.py', [
("""    s = portal_me(h)
    if odict(s.get('data')).get('verify') or odict(s.get('data')).get('may_replace'):
        # An address being checked, or a new way being chosen (1.0.76): given""",
 """    s = portal_me(h)
    if odict(s.get('data')).get('verify') and odict(s.get('data')).get('may_replace'):
        # The address given up while replacing (1.0.297): back to choosing the way - the old
        # token was proved already, and "Another address or way" asked for its password and a
        # code again (another sent code used up).
        portal_data_set(h, s, verify=None)
        return {'me': portal_state(h, s)}
    if odict(s.get('data')).get('verify') or odict(s.get('data')).get('may_replace'):
        # An address being checked, or a new way being chosen (1.0.76): given"""),
])
print('ok')
