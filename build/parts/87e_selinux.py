# ---------------------------------------------------------------------------
# SELinux (1.0.233)
# ---------------------------------------------------------------------------
# Settings → High security, a card per node. The page writes 'host:selinux:want:NODE'
# (check, prepare, enforce, permissive); that node's daemon has its root helper do it and
# says how SELinux is there in 'host:selinux:now:NODE' - looked at again every half hour.
# Nothing changes unless somebody asks: a machine with SELinux disabled stays so.
SE_WORK = {'busy': False, 'seen': 0.0}
SE_ACTIONS = ('check', 'prepare', 'enforce', 'permissive')
SE_EVERY = 1800


def selinux_want(store):
    """What otp needs of SELinux on this node: the booleans and the ports, and why."""
    bools = [{'name': 'httpd_can_network_connect',
              'why': 'the pages ask the daemon on 127.0.0.1:%s' % (CONFIG.get('api_port') or 9861)}]
    ports = []
    try:
        if ssh_gate_wanted(store):
            bools.append({'name': 'authlogin_radius', 'why': 'SSH asks otp for the code'})
            p = ssh_gate_port(store)
            if p not in (1812, 1813, 1645, 1646):
                ports.append({'port': p, 'proto': 'udp', 'type': 'radius_port_t',
                              'why': 'SSH asks otp for the code on this port'})
    except Exception:                                   # noqa: BLE001
        pass
    try:
        now = _meta_json(store, 'host:sshd:now:' + node_name()) or {}
        sp = int((now.get('values') or {}).get('port') or 22)
        if sp != 22:
            ports.append({'port': sp, 'proto': 'tcp', 'type': 'ssh_port_t',
                          'why': 'the SSH server listens on it'})
    except (TypeError, ValueError):
        pass
    eng = CONFIG.get('db_engine')
    host = str(CONFIG.get('db_host') or '').strip().lower()
    try:
        dp = int(CONFIG.get('db_port') or 0)
    except (TypeError, ValueError):
        dp = 0
    if eng == 'postgres' and host in ('', '127.0.0.1', 'localhost', '::1') and dp not in (0, 5432):
        ports.append({'port': dp, 'proto': 'tcp', 'type': 'postgresql_port_t',
                      'why': 'PostgreSQL of this node listens on it'})
    return {'booleans': bools, 'ports': ports}


def selinux_view(store):
    nodes = [node_name()] + [n['name'] for n in ha_nodes(store) if n['name'] != node_name()]
    out = []
    for n in nodes:
        now = _meta_json(store, 'host:selinux:now:' + n) or {}
        want = _meta_json(store, 'host:selinux:want:' + n) or {}
        out.append({'name': n, 'me': n == node_name(), 'state': now.get('data') or {},
                    'at': now.get('at'), 'error': now.get('error') or '',
                    'said': now.get('said') or [], 'action': now.get('action') or '',
                    'pending': (want.get('do') if want and want.get('id') != now.get('done')
                                else '')})
    return {'nodes': out}


def selinux_ask(store, node, action, by):
    known = [node_name()] + [n['name'] for n in ha_nodes(store)]
    if node not in known:
        raise ValueError('there is no node %s' % node)
    if action not in SE_ACTIONS:
        raise ValueError('check, prepare, enforce or permissive')
    store.set_meta('host:selinux:want:' + node, json.dumps({
        'id': secrets.token_hex(6), 'do': action, 'by': by, 'at': time.time()}))
    if action != 'check':
        store.add_event('settings', '%s asked SELinux on %s: %s' % (by, node, {
            'prepare': 'made ready, permissive', 'enforce': 'enforcing',
            'permissive': 'permissive again'}[action]), 'warn', who=by)


def selinux_tick(daemon):
    """Every few seconds: a step asked for this node done; how it is, looked at now and then."""
    store = daemon.store
    me = node_name()
    want = _meta_json(store, 'host:selinux:want:' + me) or {}
    now = _meta_json(store, 'host:selinux:now:' + me) or {}
    asked = bool(want) and want.get('id') != now.get('done')
    if SE_WORK['busy'] or not (asked or time.time() - SE_WORK['seen'] > SE_EVERY):
        return
    SE_WORK['busy'] = True
    SE_WORK['seen'] = time.time()
    do = want.get('do') if asked and want.get('do') in SE_ACTIONS else 'check'

    def go():
        try:
            err = ''
            data = (now.get('data') or {}) if do != 'check' else {}
            said = []
            try:
                data = root_ask('selinux.ask', 'selinux.json',
                                dict(selinux_want(store), do=do), 120 if do == 'check' else 600)
                said = data.pop('said', []) if isinstance(data, dict) else []
            except ValueError as e:
                err = str(e)[:400]
                if do != 'check':
                    log('SELinux on %s: %s' % (me, err), 'warn')
            if do != 'check':
                store.add_event('settings', 'SELinux on %s: %s' % (
                    me, err or '; '.join(said) or 'done'), 'bad' if err else 'warn')
                if not err:
                    log('SELinux on %s: %s' % (me, '; '.join(said) or 'done'), 'warn')
            store.set_meta('host:selinux:now:' + me, json.dumps({
                'data': data if isinstance(data, dict) else {}, 'at': time.time(),
                'done': want.get('id') if asked else now.get('done'), 'error': err,
                'said': said, 'action': do}))
        except Exception as e:                          # noqa: BLE001
            log_sparing('selinux', 'SELinux: %s' % e, 'warn', every=600)
        finally:
            SE_WORK['busy'] = False
    threading.Thread(target=go, name='otp-selinux', daemon=True).start()


def selinux_problems(store, node=None):
    """For the security check: what keeps SELinux from protecting a node as it should -
    nothing at all where it is disabled (as until now) or not on the machine."""
    now = _meta_json(store, 'host:selinux:now:' + (node or node_name())) or {}
    d = now.get('data') or {}
    if d.get('mode') not in ('Enforcing', 'Permissive'):
        return []
    out = list(d.get('problems') or [])
    if d.get('mode') == 'Permissive' and not out:
        out.append('SELinux is permissive: nothing is refused - otp is ready for enforcing')
    return out
