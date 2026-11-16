# 1.0.292: the row of this machine's database server taken away also when otp starts with the
# setting already off (one look at its own row, once).   python3 fix_drop.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'
f = P + '90d_dbagent.py'
s = open(f).read()
a = """            elif DBLOCAL_STATE['wrote'] or (on and DBLOCAL_STATE['wrote'] is None):
                db_local_drop(daemon.store)
"""
b = """            elif DBLOCAL_STATE['wrote'] or (on and DBLOCAL_STATE['wrote'] is None):
                db_local_drop(daemon.store)
            elif DBLOCAL_STATE['wrote'] is None:
                # Started with the setting off: a row left from when it was on taken away -
                # one look at this node's own row, once; nothing more while it stays off.
                if daemon.store.get_meta('dblocal:node:' + node_name()):
                    db_local_drop(daemon.store)
                else:
                    DBLOCAL_STATE['wrote'] = False
"""
assert s.count(a) == 1
s = s.replace(a, b)
open(f, 'w').write(s)
print('ok')
