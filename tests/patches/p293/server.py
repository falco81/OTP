# 1.0.293: the database servers in the header's meter - GET /api/load has `dbservers` with an agent
# (this node's server read now through it, the other node's from its row). Without an agent
# nothing changes.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('90d_dbagent.py', [
("""def db_agent_load(fresh=False):
    \"\"\"This node's database server, in the shape of server_load() (and its database's own).\"\"\"
    now = time.time()
    if not fresh and DBAGENT_STATE['load'] and now - DBAGENT_STATE['load_at'] < 2.5:
        return DBAGENT_STATE['load']
    got = db_agent_call('load', {'db': CONFIG.get('db_name') or 'otp'}, timeout=10)
""", """def db_agent_load(fresh=False, timeout=10):
    \"\"\"This node's database server, in the shape of server_load() (and its database's own).\"\"\"
    now = time.time()
    if not fresh and DBAGENT_STATE['load'] and now - DBAGENT_STATE['load_at'] < 2.5:
        return DBAGENT_STATE['load']
    got = db_agent_call('load', {'db': CONFIG.get('db_name') or 'otp'}, timeout=timeout)
"""),
("""    if db_agent_on():
        try:
            v = dict(db_agent_load())
        except ValueError as e:
            v = {'at': time.time(), 'down': True, 'said': str(e)[:200]}
        v.update(kind='db', node=me, host=db_agent_db_host(), age=0.0)
        out.append(v)
""", """    if db_agent_on():
        # The meter asks every 2 s (1.0.293): an agent known not to answer, or one that did not
        # answer a moment ago, is not asked again then - the page would wait for it each time.
        now = time.time()
        if DBAGENT_STATE['ok'] is False:
            v = {'at': now, 'down': True, 'said': 'its agent does not answer'}
        elif now - float(DBAGENT_STATE.get('load_fail_at') or 0) < 10:
            v = {'at': now, 'down': True, 'said': DBAGENT_STATE.get('load_said') or ''}
        else:
            try:
                v = dict(db_agent_load(timeout=4))
            except ValueError as e:
                DBAGENT_STATE.update(load_fail_at=now, load_said=str(e)[:200])
                v = {'at': now, 'down': True, 'said': str(e)[:200]}
        v.update(kind='db', node=me, host=db_agent_db_host(), age=0.0)
        out.append(v)
"""),
])

edit('90r_load.py', [
("""    if CONFIG.get('ha_mode'):
        out['others'] = load_others(h.store, since)
    return out
""", """    if CONFIG.get('ha_mode'):
        out['others'] = load_others(h.store, since)
    # The database servers of their own (1.0.293): a row each after the nodes - only with an
    # agent; without one the answer is as it was.
    try:
        if db_agent_on():
            out['dbservers'] = db_agent_load_rows(h.store)
    except Exception as e:                              # noqa: BLE001
        log_sparing('load-db', 'the database servers for the meter: %s' % e, 'warn', every=600)
    return out
"""),
])
print('ok')
