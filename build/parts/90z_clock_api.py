# ---- the card of the clocks (1.0.222): Settings -> Time -> The clocks of the nodes
@route('GET', '/api/clock')
def _clock_get(h):
    h.me()
    return clock_view(h.store)


def _clock_refs_checked(names, refs):
    out = {}
    for n, v in refs.items():
        if n not in names:
            raise ApiError(400, 'there is no node called %s' % n)
        try:
            split_targets_parse(v)
        except ValueError as e:
            raise ApiError(400, '%s: %s' % (n, e))
        out[str(n)] = str(v or '').strip()
    return out


@route('POST', '/api/clock')
def _clock_post(h):
    s = h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    names = [n['name'] for n in ha_nodes(h.store)] or [node_name()]
    refs = _clock_refs_checked(names, b.get('refs') if isinstance(b.get('refs'), dict) else {})
    if act == 'try':
        return node_ask(h.d, 'clock_try', {'refs': refs}, s['name'])
    if act == 'poll':
        return {'nodes': node_ask_results(h.store, 'clock_try', str(b.get('id') or ''))}
    if act != 'save':
        raise ApiError(400, 'save, try or poll')
    conf = b.get('conf') if isinstance(b.get('conf'), dict) else {}
    want = {k: conf[k] for k in CLOCK_KEYS if k in conf}
    if 'clock_mode' in want and want['clock_mode'] not in CLOCK_MODES:
        raise ApiError(400, 'the mode is off, watch or guard')
    for k, (lo, hi) in (('clock_warn_s', (1, 60)), ('clock_aside_s', (5, 600))):
        if k in want:
            try:
                want[k] = int(want[k])
            except (TypeError, ValueError):
                raise ApiError(400, '%s is a number' % k)
            if not lo <= want[k] <= hi:
                raise ApiError(400, '%s is %d-%d' % (k, lo, hi))
    for k in ('clock_codes', 'clock_beat', 'clock_locks', 'health_dir'):
        if k in want:
            want[k] = 1 if want[k] in (1, True, '1', 'on') else 0
    warn = int(want.get('clock_warn_s', CONFIG.get('clock_warn_s') or 2))
    aside = int(want.get('clock_aside_s', CONFIG.get('clock_aside_s') or 20))
    if aside <= warn:
        raise ApiError(400, 'stepping aside comes after the warning: more seconds than it')
    if want.get('clock_mode') == 'guard' and want.get('clock_mode') != CONFIG.get('clock_mode') \
            and b.get('checked') is not True:
        raise ApiError(409, 'try the reference from every node first (Try it): a node that cannot '
                            'ask it is never stepped aside, but you would not know it is unguarded')
    many = len(names) > 1
    if want:
        h.d.save_settings(want, by=s['name'], node='*' if many else None)
    for n, v in refs.items():
        h.d.save_settings({'clock_ref': v}, by=s['name'], node=n)
    CLOCK['measure_now'] = True                         # asked again at the next look, the
    # last measurement kept meanwhile (1.0.224: thrown away, codes went uncorrected for 5 s)
    h.store.add_event('settings', '%s chose what the nodes do about their clocks: %s' % (
        s['name'], ', '.join('%s=%s' % kv for kv in sorted(want.items())) or 'reference servers'),
        'warn', who=s['name'])
    return {'message': 'kept - each node follows it within seconds', 'view': clock_view(h.store)}
