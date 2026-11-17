# 1.0.310: the rolling upgrade in a cluster (hunt round 9) - a node's own rows sent to the other node's
# database again while an upgrade runs (one lost write held the whole upgrade for good); a node forgotten
# while it still beats in its own database keeps its maintenance and its upgrade row.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('88_upgrade.py', [
("""    store = daemon.store
    if HA_REBUILDING.is_set():
        return
    plan = upgrade_plan(store)""",
 """    store = daemon.store
    if HA_REBUILDING.is_set():
        return
    plan = upgrade_plan(store)
    upgrade_resend_mine(store, plan)"""),
("""PEER_THERE = {}                   # name: (when asked, alive)""",
 """UPG_RESENT = [0.0]


def upgrade_resend_mine(store, plan):
    \"\"\"This node's own rows of the upgrade written to the other node's database again (1.0.310),
    every 30 s while a plan is not finished: a node on the newer version reaches the older one only
    so - one write lost (its database restarting, the network a moment away) and the other node
    waited for this one for good, the upgrade held until somebody stopped it.\"\"\"
    if not plan or plan.get('state') == 'done' or CONFIG.get('ha_mode') != 'replicated':
        return
    if time.monotonic() - UPG_RESENT[0] < 30:
        return
    UPG_RESENT[0] = time.monotonic()
    me = node_name()
    for k in ('upgrade:node:' + me, 'maint:' + me):
        try:
            v = store.get_meta(k)
            if v:
                _peer_update(k, v)
        except Exception:                               # noqa: BLE001
            pass


PEER_THERE = {}                   # name: (when asked, alive)"""),
])

edit('87_ha.py', [
("""    try:
        alive = any(n['name'] == name and n.get('alive') for n in ha_nodes(store))
    except Exception:                                   # noqa: BLE001
        alive = True
    store.drop_meta('node:' + name)""",
 """    try:
        alive = any(n['name'] == name and n.get('alive') for n in ha_nodes(store))
    except Exception:                                   # noqa: BLE001
        alive = True
    # Asked in its own database too (1.0.310): a node on a newer version, or with the replication
    # towards this one stopped, looks gone here while it answers - forgotten, its maintenance (kept
    # on purpose) went, and its upgrade row with it: the upgrade waited for it for good.
    if not alive:
        try:
            alive = bool(_peer_alive_there(name))
        except Exception:                               # noqa: BLE001
            pass
    store.drop_meta('node:' + name)"""),
])
print('ok')
