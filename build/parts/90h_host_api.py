

# ---- root's SSH keys and the updates of the system on the pages (1.0.158) ------------
def sshotp_accounts(store):
    """root and the users who may sign in on the nodes, as they said (1.0.242); None while no node
    said yet (an older one): then the name is taken as until now."""
    out, said = {'root'}, False
    for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'host:sshkeys:now:%'"):
        row = json_obj(r['v'])
        if row is None:
            continue
        if isinstance(row, dict) and isinstance(row.get('users'), list):
            said = True
            out.update(str(u.get('name')) for u in row['users'] if isinstance(u, dict) and u.get('name'))
    return out if said else None


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
    # Whose keys (1.0.240): root's as until now, or a normal user's of the nodes.
    user = str(b.get('user') or 'root')
    try:
        if act == 'refresh':
            sshkeys_ask(h.store, nodes, 'list', s['name'], user=user)
            return {'message': 'asked again'}
        if act == 'add':
            # A public line, or a private key of which only the public half
            # is used and nothing else kept (1.0.161).
            line, was_private = rootkey_public(b.get('line'), str(b.get('passphrase') or ''))
            sshkeys_ask(h.store, nodes, 'add', s['name'], line=line, user=user)
            return {'message': 'the key goes onto %s within a few seconds%s' % (
                ', '.join(nodes), ' - the private half was not kept' if was_private else '')}
        if act == 'drop':
            sshkeys_ask(h.store, nodes, 'drop', s['name'], fp=str(b.get('fp') or ''),
                        last_ok=bool(b.get('last_ok')), user=user)
            return {'message': 'the key is taken away on %s within a few seconds'
                               % ', '.join(nodes)}
        if act == 'uk_make':
            # A key made for a normal user (1.0.240): its private half to the page once, its
            # public half onto the nodes asked - remembered nowhere.
            if user == 'root':
                raise ValueError('root\'s key is made with the card above')
            if b.get('kind', 'ed25519') not in ('ed25519', 'rsa4096'):
                raise ValueError('ed25519 or rsa4096')
            private, public, fp = sshkey_pair(str(b.get('kind') or 'ed25519'),
                                              '%s@%s %s' % (user, node_name(), time.strftime('%Y-%m-%d')))
            done = sshkeys_ask(h.store, nodes, 'add', s['name'], line=public, user=user)
            h.store.add_event('settings', '%s made a new SSH key for %s on %s (%s) - its private '
                              'half handed to the page once, kept nowhere' % (
                                  s['name'], user, ', '.join(done), fp), 'warn', who=s['name'])
            return {'private': private, 'pub': public, 'fp': fp, 'nodes': done,
                    'file': 'otp-%s-%s' % (re.sub(r'[^A-Za-z0-9-]', '', user), time.strftime('%Y%m%d')),
                    'message': 'made - keep the private half now, it is not shown again'}
        # Root's key made or given here (1.0.159): its private half kept nowhere.
        scope = str(b.get('scope') or 'all')
        if act == 'rk_make':
            if b.get('kind', 'ed25519') not in ('ed25519', 'rsa4096'):
                raise ValueError('ed25519 or rsa4096')
            private, public, _ = sshkey_pair(str(b.get('kind') or 'ed25519'),
                                             'root@%s %s' % (scope if scope != 'all' else node_name(),
                                                             time.strftime('%Y-%m-%d')))
            x = rootkey_put(h.store, scope, public, s['name'], 'made')
            h.store.add_event('settings', '%s made a new SSH key for root on %s (%s) - its private '
                              'half handed to the page once, kept nowhere' % (
                                  s['name'], ', '.join(x['nodes']), x['fp']), 'warn', who=s['name'])
            return dict(x, private=private,
                        file='otp-root-%s-%s' % (re.sub(r'[^A-Za-z0-9-]', '', scope),
                                                 time.strftime('%Y%m%d')),
                        message='made - keep the private half now, it is not shown again')
        if act == 'rk_given':
            public, was_private = rootkey_public(b.get('key'), str(b.get('passphrase') or ''))
            x = rootkey_put(h.store, scope, public, s['name'], 'given')
            return dict(x, message='the public half goes onto %s%s' % (
                ', '.join(x['nodes']), ' - the private half was not kept' if was_private else ''))
        if act == 'rk_again':
            nodes = rootkey_again(h.store, scope, s['name'])
            return {'message': 'the key goes onto %s again' % ', '.join(nodes)}
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
                              s['name'], security=bool(b.get('security')))
            return {'message': 'the update starts: %s, one at a time' % ', '.join(plan['order']),
                    'plan': plan}
        if act == 'cancel':
            osup_cancel(h.store, s['name'])
            return {'message': 'stopped - a node being updated finishes'}
        if act == 'clear':
            osup_clear(h.store, s['name'])
            return osup_view(h.store)
        if act == 'hide':
            plan = osup_plan(h.store)
            if plan.get('state') == 'running':
                raise ValueError('it is still going on')
            if plan.get('id'):
                h.store.set_meta('host:osup:seen', str(plan['id']))
            return osup_view(h.store)
        if act == 'reboot':
            nodes = [n for n in host_nodes(h.store) if n in node_list(b.get('nodes'))]
            plan = power_ask(h.store, 'reboot', nodes, 'rolling' if len(nodes) > 1 else 'one',
                             s['name'])
            return {'message': 'restarting %s, one at a time' % ', '.join(nodes), 'plan': plan}
    except ValueError as e:
        raise ApiError(400, str(e))
    raise ApiError(400, 'no such thing to do')


@route('GET', '/api/sshd')
def _sshd(h):
    h.me('fulladmin')
    return sshd_view(h.store)


@route('POST', '/api/sshd')
def _sshd_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    try:
        if act == 'save':
            c = sshd_save(h.store, b.get('conf') or {}, s['name'])
            return dict(sshd_view(h.store), message='put in on every node within a few seconds' +
                        (' - on trial: Keep it within %d min, or it goes back' % c['trial_min']
                         if c['manage'] and c['trial_min'] else ''))
        if act == 'keep':
            c = sshd_conf(h.store)
            h.store.set_meta('host:sshd:keep', json.dumps({'hash': c.get('hash'), 'at': time.time(),
                                                           'by': s['name']}))
            h.store.add_event('settings', '%s kept the change of the SSH server' % s['name'],
                              'info', who=s['name'])
            return dict(sshd_view(h.store), message='kept')
        if act == 'back':
            h.store.set_meta('host:sshd:back', json.dumps({'id': secrets.token_hex(6),
                                                           'at': time.time(), 'by': s['name']}))
            h.store.add_event('settings', '%s put the SSH server back as it was' % s['name'],
                              'warn', who=s['name'])
            return dict(sshd_view(h.store), message='it goes back within a few seconds')
        if act == 'refresh':
            HOST_WORK['sshd_read'] = 0.0
            return sshd_view(h.store)
        # SSH tokens of their own (1.0.181): the app's QR shown once, when made.
        if act == 'sshotp_add':
            # Only an account of the nodes (1.0.242): root, or a user who may sign in there, as the
            # nodes said - never a name typed that is nobody's. A new one in its place: as it is.
            if not b.get('replace'):
                known = sshotp_accounts(h.store)
                if known is not None and str(b.get('name') or '').strip() not in known:
                    raise ValueError('%s is not an account of the nodes - pick one of the list '
                                     '(root, or a user who may sign in there)'
                                     % str(b.get('name') or '')[:40])
            got = sshotp_make(h.store, b.get('name'), s['name'], b.get('note') or '',
                              replace=bool(b.get('replace')), kind=str(b.get('kind') or 'app'),
                              dest=str(b.get('dest') or ''), lang=str(b.get('lang') or ''))
            return dict(sshd_view(h.store), made=got, message=(
                'the SSH token of %s is made - scan it now, it is not shown again' % got['name']
                if got['kind'] == 'app' else 'the SSH token of %s is made - its codes go to %s'
                % (got['name'], got['dest'])))
        if act == 'sshotp_remove':
            sshotp_remove(h.store, b.get('name'), s['name'])
            return dict(sshd_view(h.store), message='removed')
    except ValueError as e:
        raise ApiError(400, str(e))
    raise ApiError(400, 'no such thing to do')
