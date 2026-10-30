

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
