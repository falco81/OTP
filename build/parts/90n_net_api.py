# ---- Settings → Network, Settings → Restart and power off (1.0.119) -------------------
@route('GET', '/api/net')
def _net(h):
    h.me('fulladmin')
    return net_view(h.store)


@route('POST', '/api/net')
def _net_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = b.get('action')
    node = str(b.get('node') or node_name())
    known = [node_name()] + [n['name'] for n in ha_nodes(h.store)]
    if node not in known:
        raise ApiError(400, 'there is no node %s' % node)
    try:
        if act == 'read':
            # Said again by that node within seconds; this one at once.
            h.store.set_meta('net:read:' + node, repr(time.time()))
            if node == node_name():
                try:
                    net_publish(h.store)
                except ValueError as e:
                    raise ApiError(502, str(e))
            return net_view(h.store)
        if act == 'plan':
            got = net_check(h.store, node, b.get('want') or {})
            return {'plan': got['plan'], 'want': got}
        if act == 'hide':
            job = _meta_json(h.store, 'net:job:' + node) or {}
            if not job:
                raise ApiError(409, 'there is nothing on %s to hide' % node)
            if job.get('state') not in ('done', 'failed'):
                raise ApiError(409, 'the change on %s is not over yet' % node)
            h.store.set_meta('net:seen:' + node, str(job.get('id')))
            return net_view(h.store)
        if act == 'apply':
            ask = net_ask(h.store, node, b.get('want') or {}, s['name'])
            return {'message': 'asked: %s does it now' % node, 'id': ask['id']}
    except ValueError as e:
        raise ApiError(400, str(e))
    raise ApiError(400, 'no such thing to do')


@route('GET', '/api/power')
def _power(h):
    h.me('fulladmin')
    return power_view(h.store)


@route('POST', '/api/power')
def _power_do(h):
    s = h.me('fulladmin')
    b = h.body()
    if b.get('action') == 'hide':
        plan = power_plan(h.store)
        if plan.get('id'):
            h.store.set_meta('power:seen', str(plan['id']))
        return power_view(h.store)
    try:
        plan = power_ask(h.store, str(b.get('how') or ''), b.get('targets') or [],
                         str(b.get('order') or ''), s['name'])
    except ValueError as e:
        raise ApiError(400, str(e))
    return {'message': 'asked', 'plan': plan}


@route('GET', '/api/ntp')
def _ntp(h):
    h.me('fulladmin')
    return ntp_view(h.store)


@route('POST', '/api/ntp')
def _ntp_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = b.get('action')
    node = str(b.get('node') or node_name())
    try:
        if act == 'save':
            ntp_save(h.store, b.get('conf') or {}, s['name'])
            return {'message': 'saved; each node sets its time servers within seconds'}
        if act in ('read', 'sync'):
            known = [node_name()] + [n['name'] for n in ha_nodes(h.store)]
            if node not in known:
                raise ApiError(400, 'there is no node %s' % node)
            h.store.set_meta('ntp:%s:%s' % (act, node), repr(time.time()))
            if act == 'sync':
                h.store.add_event('settings', '%s asked %s to step its clock to the time '
                                  'servers now' % (s['name'], node), 'warn', who=s['name'])
            return {'message': 'asked: %s does it within seconds' % node}
    except ValueError as e:
        raise ApiError(400, str(e))
    raise ApiError(400, 'no such thing to do')


@route('GET', '/api/console-login')
def _console_login(h):
    h.me('fulladmin')
    return console_login_view(h.store)


@route('POST', '/api/console-login')
def _console_login_do(h):
    s = h.me('fulladmin')
    b = h.body()
    on = b.get('on')
    if not isinstance(on, bool):
        raise ApiError(400, 'on is true or false')
    try:
        # The normal users it opens for too (1.0.240): '*', a list of names, or none - left out,
        # as they are.
        console_login_ask(h.store, str(b.get('node') or node_name()), on, s['name'],
                          users=b.get('users') if 'users' in b else None)
    except ValueError as e:
        raise ApiError(400, str(e))
    return {'message': 'asked: the console at login is switched on within seconds' if on else
            'asked: the console at login is switched off within seconds'}


@route('GET', '/api/selinux')
def _selinux(h):
    h.me('fulladmin')
    return selinux_view(h.store)


@route('POST', '/api/selinux')
def _selinux_do(h):
    s = h.me('fulladmin')
    b = h.body()
    node = str(b.get('node') or node_name())
    action = str(b.get('action') or '')
    if action == 'download':
        # Every node's report in one archive (1.0.236), from the database - whichever node answers.
        data, missing = selinux_report_bundle(h.store)
        h.store.add_event('settings', '%s took the SELinux report%s' % (
            s['name'], (' - without %s' % ', '.join(m.split(':')[0] for m in missing)) if missing else ''),
            'info', who=s['name'])
        return {'name': 'otp-selinux-report-%s.tar.gz' % time.strftime('%Y%m%d-%H%M'),
                'file': base64.b64encode(data).decode('ascii'), 'mime': 'application/gzip',
                'missing': missing}
    try:
        if action == 'report' and node == '*':
            for n in [node_name()] + [x['name'] for x in ha_nodes(h.store) if x['name'] != node_name()]:
                selinux_ask(h.store, n, 'report', s['name'])
            return {'message': 'asked: every node makes its report within a minute'}
        selinux_ask(h.store, node, action, s['name'])
    except ValueError as e:
        raise ApiError(400, str(e))
    return {'message': {'check': 'asked: %s looks within seconds',
                        'prepare': 'asked: %s makes SELinux ready and permissive within seconds',
                        'enforce': 'asked: %s switches SELinux to enforcing within seconds',
                        'permissive': 'asked: %s switches SELinux to permissive within seconds',
                        'report': 'asked: %s makes its report within a minute'
                        }[action] % node}
