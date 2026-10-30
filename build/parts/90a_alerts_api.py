

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
    act = str(b.get('action') or '')
    if act == 'result':
        return {'nodes': node_ask_results(h.store, 'siem', str(b.get('id') or ''))}
    if act != 'test':
        raise ApiError(400, 'no such thing to do')
    if not CONFIG.get('siem') or not siem_targets(CONFIG.get('siem_targets')):
        raise ApiError(400, 'no syslog server is set')
    # From every node (1.0.169): each sends its own and says how it went.
    h.store.add_event('settings', '%s sent a test line to the syslog servers from every node'
                      % s['name'], 'info', who=s['name'])
    return node_ask(h.d, 'siem', {'by': s['name'], 'only': str(b.get('node') or '')}, s['name'])


@route('POST', '/api/proxy')
def _proxy_do(h):
    h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    try:
        if act == 'try':
            # On every node (1.0.169); 'result' says what each found so far.
            url = str(b.get('url') or '').strip()
            if url and not re.match(r'^https?://[^\s/]+[^\s]*\Z', url):
                raise ValueError('an address starting https:// (or http://)')
            return node_ask(h.d, 'proxy', {'url': url}, h.me('fulladmin')['name'])
        if act == 'result':
            return {'nodes': node_ask_results(h.store, 'proxy', str(b.get('id') or ''))}
    except ValueError as e:
        raise ApiError(400, str(e))
    raise ApiError(400, 'no such thing to do')


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


# ---- certificates by ACME (1.0.169) ---------------------------------------------------
@route('GET', '/api/acme/challenge')
def _acme_challenge(h):
    """What acme.php gives the CA on port 80 - no account: the CA asks."""
    got = acme_challenge(h.store, h.arg('token'))
    if got is None:
        raise ApiError(404, 'no such challenge')
    return {'auth': got}


@route('GET', '/api/acme')
def _acme(h):
    h.me('fulladmin')
    return acme_view(h.store)


@route('POST', '/api/acme')
def _acme_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    try:
        if act == 'order':
            if not CONFIG.get('acme'):
                raise ValueError('certificates by ACME are off - switch them on and save first')
            mine = dict(acme_targets(h.store))
            target = str(b.get('target') or '')
            if target not in mine:
                raise ValueError('%s is not ordered from this node - the web address\'s is ordered '
                                 'by %s, a node\'s by that node' % (target, 'the first node by name'))
            acme_start(h.store, [(target, mine[target])], s['name'])
            return dict(acme_view(h.store), message='the certificate of %s is being ordered' % mine[target])
        if act == 'probe':
            return acme_probe(h.store, str(b.get('target') or ''))
        if act in ('manual_done', 'manual_drop'):
            # The TXT record put in by hand (1.0.169) - or the order given up.
            got = _meta_json(h.store, 'acme:manual') or {}
            if not got.get('id'):
                raise ValueError('no order waits for a TXT record now')
            if act == 'manual_done':
                got['done'] = time.time()
                h.store.set_meta('acme:manual', json.dumps(got))
            else:
                h.store.db.run("DELETE FROM meta WHERE k = 'acme:manual'")
            h.store.add_event('settings', '%s said the TXT record %s %s' % (
                s['name'], got.get('rr'), 'is in DNS' if act == 'manual_done' else
                'will not be put in - the order is given up'), who=s['name'])
            return acme_view(h.store)
        if act == 'forget':
            h.store.db.run("DELETE FROM meta WHERE k = 'acme:account'")
            h.store.add_event('settings', '%s forgot the account at the ACME CA - a new one is '
                              'made at the next order' % s['name'], 'warn', who=s['name'])
            return acme_view(h.store)
    except (ValueError, AcmeError) as e:
        raise ApiError(400, str(e))
    raise ApiError(400, 'no such thing to do')
