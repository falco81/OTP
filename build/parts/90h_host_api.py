

# ---- root's SSH keys and the updates of the system on the pages (1.0.158) ------------
@route('GET', '/api/sshkeys')
def _sshkeys(h):
    h.me('fulladmin')
    return sshkeys_view(h.store)


@route('POST', '/api/sshkeys')
def _sshkeys_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    nodes = b.get('nodes') or [node_name()]
    if not isinstance(nodes, list):
        raise ApiError(400, 'nodes is a list')
    try:
        if act == 'refresh':
            sshkeys_ask(h.store, nodes, 'list', s['name'])
            return {'message': 'asked again'}
        if act == 'add':
            line = str(b.get('line') or '').strip()
            sshkeys_ask(h.store, nodes, 'add', s['name'], line=line)
            return {'message': 'the key goes onto %s within a few seconds' % ', '.join(nodes)}
        if act == 'drop':
            sshkeys_ask(h.store, nodes, 'drop', s['name'], fp=str(b.get('fp') or ''),
                        last_ok=bool(b.get('last_ok')))
            return {'message': 'the key is taken away on %s within a few seconds'
                               % ', '.join(nodes)}
        if act == 'make':
            # The private half goes to this page once and is kept nowhere; the
            # public half onto the nodes asked for.
            private, public, fp = sshkey_make(str(b.get('kind') or 'ed25519'),
                                              str(b.get('comment') or ''))
            sshkeys_ask(h.store, nodes, 'add', s['name'], line=public)
            h.store.add_event('settings', '%s made a new SSH key for root (%s, %s) - its '
                              'private half handed to the page once' % (s['name'], fp, ', '.join(nodes)),
                              'warn', who=s['name'])
            return {'private': private, 'public': public, 'fp': fp, 'nodes': nodes,
                    'file': 'otp-root-%s-%s' % (re.sub(r'[^A-Za-z0-9-]', '', node_name()),
                                                time.strftime('%Y%m%d')),
                    'message': 'made - keep the private half now, it is not shown again'}
    except ValueError as e:
        raise ApiError(400, str(e))
    raise ApiError(400, 'no such thing to do')


@route('GET', '/api/osup')
def _osup(h):
    h.me('fulladmin')
    return osup_view(h.store)


@route('POST', '/api/osup')
def _osup_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    try:
        if act == 'check':
            nodes = osup_check_ask(h.store, b.get('nodes') or host_nodes(h.store), s['name'])
            return {'message': 'looking for updates on %s' % ', '.join(nodes)}
        if act == 'start':
            plan = osup_start(h.store, b.get('nodes') or None, str(b.get('reboot') or 'ask'),
                              s['name'])
            return {'message': 'the update starts: %s, one at a time' % ', '.join(plan['order']),
                    'plan': plan}
        if act == 'cancel':
            osup_cancel(h.store, s['name'])
            return {'message': 'stopped - a node being updated finishes'}
        if act == 'hide':
            plan = osup_plan(h.store)
            if plan.get('state') == 'running':
                raise ValueError('it is still going on')
            if plan.get('id'):
                h.store.set_meta('host:osup:seen', str(plan['id']))
            return osup_view(h.store)
        if act == 'reboot':
            nodes = [n for n in host_nodes(h.store) if n in (b.get('nodes') or [])]
            plan = power_ask(h.store, 'reboot', nodes, 'rolling' if len(nodes) > 1 else 'one',
                             s['name'])
            return {'message': 'restarting %s, one at a time' % ', '.join(nodes), 'plan': plan}
    except ValueError as e:
        raise ApiError(400, str(e))
    raise ApiError(400, 'no such thing to do')
