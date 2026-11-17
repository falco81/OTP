# 1.0.295: bug fixes - the database servers' rows of a node forgotten or renamed go; the meter's
# database rows timed by this node's clock, not the database server's.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('87_ha.py', [
("""    if not alive:
        store.drop_meta('maint:' + name)
        store.drop_meta('upgrade:node:' + name)
    CLUSTER_WITH.discard('cluster:with:' + name)""",
 """    if not alive:
        store.drop_meta('maint:' + name)
        store.drop_meta('upgrade:node:' + name)
        # Its database server's rows too (1.0.295): its tile, its pills on the cards, its
        # "does not answer" alert and its row of the meter stayed for good.
        try:
            db_agent_rows_drop(store.db, name)
        except Exception:                               # noqa: BLE001
            pass
    CLUSTER_WITH.discard('cluster:with:' + name)"""),
])

edit('90d_dbagent.py', [
("""    got = db_agent_call('load', {'db': CONFIG.get('db_name') or 'otp'}, timeout=timeout,
                        retry=retry)
    got.pop('said', None)""",
 """    got = db_agent_call('load', {'db': CONFIG.get('db_name') or 'otp'}, timeout=timeout,
                        retry=retry)
    got.pop('said', None)
    # When this node read it, by this node's clock (1.0.295): the database server's own clock
    # behind made its row late in the meter for good, an hour behind left it out.
    got['at'] = time.time()"""),
("""    now = time.time()
    for r in rows:
        try:
            v = json.loads(r['v'] or '{}')
        except ValueError:
            continue
        if not isinstance(v, dict):
            continue
        n = str(r['k'])[len('dbagent:node:'):]
        fresh =""",
 """    now = time.time()
    # Only of the nodes there are (1.0.295): a node forgotten or renamed left its server's tile,
    # pills and alert behind for good.
    try:
        nodes = set(host_nodes(store))
    except Exception:                                   # noqa: BLE001
        nodes = None
    for r in rows:
        try:
            v = json.loads(r['v'] or '{}')
        except ValueError:
            continue
        if not isinstance(v, dict):
            continue
        n = str(r['k'])[len('dbagent:node:'):]
        if nodes is not None and n not in nodes:
            continue
        fresh ="""),
("""    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'load:db:%'"):
        n = str(r['k'])[len('load:db:'):]
        if n == me:
            continue""",
 """    try:
        nodes = set(host_nodes(store))
    except Exception:                                   # noqa: BLE001
        nodes = None
    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'load:db:%'"):
        n = str(r['k'])[len('load:db:'):]
        if n == me or (nodes is not None and n not in nodes):
            continue"""),
])
print('ok')
