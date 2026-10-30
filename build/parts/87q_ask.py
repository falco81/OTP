

# ---- something asked of every node, each answering for itself (1.0.169) ----------------
# A test that only a node itself can make - Proxy → Try it, a test line to
# isemon or to the syslog servers - asked once on the pages and made on every
# node: the ask is kept in the database ('ask:want:KIND'), each node's loop
# sees it within seconds and writes its own answer ('ask:got:KIND:NODE'), the
# page shows every node's as they come. The node the page is on answers at
# once. Each answer is made in a thread of its own.
NODE_ASK = {'do': {}, 'done': set(), 'daemon': [None]}
NODE_ASK_FRESH = 120


def node_ask_kind(kind):
    """Registers what a kind of ask does: fn(daemon, args) -> dict."""
    def put(fn):
        NODE_ASK['do'][kind] = fn
        return fn
    return put


def _node_ask_run(daemon, kind, want):
    key = '%s:%s' % (kind, want.get('id'))
    if key in NODE_ASK['done'] or kind not in NODE_ASK['do']:
        return
    only = (want.get('args') or {}).get('only')
    if only and only != node_name():
        NODE_ASK['done'].add(key)
        return
    NODE_ASK['done'].add(key)
    store = daemon.store

    def go():
        try:
            got = NODE_ASK['do'][kind](daemon, want.get('args') or {})
        except Exception as e:                          # noqa: BLE001
            got = {'ok': False, 'error': str(e)[:300]}
        got = dict(got or {}, id=want['id'], at=time.time(), node=node_name())
        store.set_meta('ask:got:%s:%s' % (kind, node_name()), json.dumps(got, default=str))
    threading.Thread(target=go, name='otp-ask-' + kind, daemon=True).start()


def node_ask(daemon, kind, args, by):
    want = {'id': secrets.token_hex(6), 'args': args or {}, 'at': time.time(), 'by': by}
    daemon.store.set_meta('ask:want:' + kind, json.dumps(want))
    _node_ask_run(daemon, kind, want)
    nodes = [n for n, a in host_alive(daemon.store).items() if a] or [node_name()]
    nodes = sorted(set(nodes) | {node_name()})
    if (args or {}).get('only'):
        nodes = [args['only']]
    return {'id': want['id'], 'nodes': nodes}


def node_ask_tick(daemon):
    NODE_ASK['daemon'][0] = daemon
    for kind in list(NODE_ASK['do']):
        want = _meta_json(daemon.store, 'ask:want:' + kind) or {}
        if want.get('id') and time.time() - float(want.get('at') or 0) < NODE_ASK_FRESH:
            _node_ask_run(daemon, kind, want)


def node_ask_results(store, kind, ident):
    out = {}
    for n in host_nodes(store):
        got = _meta_json(store, 'ask:got:%s:%s' % (kind, n)) or {}
        out[n] = got if got.get('id') == ident else None
    return out


@node_ask_kind('proxy')
def _ask_proxy(daemon, args):
    return proxy_try(args.get('url') or '')


@node_ask_kind('isemon')
def _ask_isemon(daemon, args):
    sh = getattr(daemon, 'shipper', None)
    if not sh:
        raise ValueError('nothing is sent from this process')
    if not CONFIG.get('isemon'):
        raise ValueError('sending to isemon is off')
    before = dict(sh.sent)
    sh.put('otp', 'daemon', 'a test from otp %s on %s, sent by %s - isemon reads nothing from '
           'this line' % (__version__, node_name(), args.get('by') or '?'))
    sh.flush(3)
    time.sleep(0.3)
    st = sh.state()
    went = [k for k, v in st.get('sent', {}).items() if v > before.get(k, 0)]
    return {'ok': bool(went) and not st.get('trouble'), 'went': went, 'state': st}


@node_ask_kind('siem')
def _ask_siem(daemon, args):
    si = getattr(daemon, 'siem', None)
    if not si:
        raise ValueError('nothing is sent from this process')
    got = si.test(args.get('by') or '?')
    return {'ok': all(v == 'sent' for v in got.values()), 'test': got, 'state': si.state()}


@node_ask_kind('dircheck')
def _ask_dircheck(daemon, args):
    ad = daemon.dirs.get(str(args.get('name') or '').lower())
    if not ad:
        raise ValueError('there is no directory called %s here' % args.get('name'))
    c = ad.check()
    ok = any(sv.get('ok') for sv in c.get('servers') or [])
    return {'ok': ok, 'check': c}
