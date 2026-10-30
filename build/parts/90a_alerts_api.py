

# ---- alerts and the report on the pages (1.0.162) --------------------------------------
def _report_span(which):
    """The period asked for: the last one ended, or the one going on so far."""
    since, until, _ = report_period()
    if which == 'now':
        return until, time.time()
    return since, until


@route('GET', '/api/alerts')
def _alerts(h):
    h.me('fulladmin')
    return alerts_view(h.store)


@route('POST', '/api/alerts')
def _alerts_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    lang = alerts_lang()
    try:
        if act == 'check':
            alerts_evaluate(h.store)
            return alerts_view(h.store)
        if act == 'test':
            to = _alerts_to()
            if not to:
                raise ValueError('no address to send it to - Send them to')
            now = alert_problems(h.store, lang)
            msg = alert_mail([], [dict(p, key=k) for k, p in now.items()], [], [], to, lang,
                             test=True)
            entry = alert_send(h.store, msg, to, 'test', [])
            h.store.add_event('settings', '%s sent a test alert to %s%s' % (
                s['name'], ', '.join(to), '' if entry['ok'] else ' - %s' % entry.get('said')),
                'info', who=s['name'])
            if not entry['ok'] and entry.get('queued') != 'waiting':
                raise ValueError('it did not go: %s' % entry.get('said'))
            return dict(alerts_view(h.store), message='a test alert went to %s' % ', '.join(to)
                        if entry['ok'] else 'it waits in the outgoing mail: %s' % entry.get('said'))
        if act == 'preview':
            since, until = _report_span(str(b.get('period') or 'last'))
            subject, page, _ = report_build(h.reader, since, until, report_lang())
            return {'subject': subject, 'html': page}
        if act == 'report':
            since, until = _report_span(str(b.get('period') or 'last'))
            entry = report_send(h.store, since, until, by=s['name'], reader=h.reader)
            if not entry['ok'] and entry.get('queued') != 'waiting':
                raise ValueError('it did not go: %s' % entry.get('said'))
            return dict(alerts_view(h.store), message='the report went to %s' % ', '.join(entry['to'])
                        if entry['ok'] else 'it waits in the outgoing mail: %s' % entry.get('said'))
        if act == 'forget':
            st = _alert_state(h.store)
            st['log'] = []
            h.store.set_meta('alerts:state', json.dumps(st))
            return alerts_view(h.store)
    except (ValueError, MailError) as e:
        raise ApiError(400, str(e))
    raise ApiError(400, 'no such thing to do')


# ---- syslog / SIEM, the proxy, the disks and the logs (1.0.166) -------------------------
def _siem_view(h):
    nodes = [n['name'] for n in ha_nodes(h.store)] if CONFIG.get('ha_mode') else [node_name()]
    me = h.d.siem.state() if getattr(h.d, 'siem', None) else {}
    out = []
    for n in nodes:
        row = _meta_json(h.store, 'host:health:' + n) or {}
        st = me if n == node_name() else (row.get('siem') or {})
        out.append(dict(st, node=n, me=n == node_name(), at=time.time() if n == node_name()
                        else row.get('at')))
    return {'nodes': out, 'on': bool(CONFIG.get('siem'))}


@route('GET', '/api/siem')
def _siem(h):
    h.me('fulladmin')
    return _siem_view(h)


@route('POST', '/api/siem')
def _siem_do(h):
    s = h.me('fulladmin')
    b = h.body()
    if str(b.get('action') or '') != 'test':
        raise ApiError(400, 'no such thing to do')
    if not getattr(h.d, 'siem', None):
        raise ApiError(400, 'this daemon sends nothing')
    try:
        got = h.d.siem.test(s['name'])
    except ValueError as e:
        raise ApiError(400, str(e))
    h.store.add_event('settings', '%s sent a test line to the syslog servers from %s: %s' % (
        s['name'], node_name(), ', '.join('%s %s' % kv for kv in sorted(got.items()))),
        'info', who=s['name'])
    return dict(_siem_view(h), test=got, node=node_name())


@route('POST', '/api/proxy')
def _proxy_do(h):
    h.me('fulladmin')
    b = h.body()
    if str(b.get('action') or '') != 'try':
        raise ApiError(400, 'no such thing to do')
    try:
        return dict(proxy_try(str(b.get('url') or '')), node=node_name())
    except ValueError as e:
        raise ApiError(400, str(e))


@route('GET', '/api/logs')
def _logs(h):
    h.me('fulladmin')
    return logs_view(h.store)


@route('POST', '/api/logs')
def _logs_do(h):
    h.me('fulladmin')
    b = h.body()
    if str(b.get('action') or '') != 'refresh':
        raise ApiError(400, 'no such thing to do')
    # Every node asks its helper again at its next look (a minute at most);
    # this one at once.
    h.store.set_meta('host:logs:again', '%.3f' % time.time())
    try:
        logs_tick(h.d, force=True)
    except Exception as e:                              # noqa: BLE001
        raise ApiError(400, 'it did not go: %s' % e)
    return logs_view(h.store)
