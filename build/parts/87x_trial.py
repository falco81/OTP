# ---- changes that could cut the server off: kept, or taken back (1.0.137) -------------
# A node's new network and a change of the firewall (or of who may reach the
# pages) are put in on trial: unless somebody presses Keep it - on the pages
# of either node, `otp --change-keep`, or the console - within net_confirm_min
# / fw_confirm_min minutes, what was there before comes back by itself. A typo
# in a gateway, a prefix, or a DROP rule in front of SSH no longer leaves the
# machine to be put right at its console.
#
# The network: the node keeps what it had (its NetworkManager settings, its
# host name) in its job; back up after the reboot the job waits as 'trial'.
# Not kept in time - or come up without the new address at all - the node
# asks itself for the old network, which is the same job the other way round
# (a reboot, the other node told the old address again). So that the other
# node can still be told, its pg_hba.conf keeps letting the old address in
# while the new one is on trial; kept, it lets only the new one in again.
# Who asks to keep or to go back writes 'net:keep:NODE' / 'net:back:NODE'; the
# node itself writes its job, as before.
#
# The firewall: what was set before the first change of a trial is kept in
# 'fw:trial'; later changes in the same trial move its deadline on. Not kept in
# time, one node (claim_once) puts it back; every node puts that in as usual.

def net_back_want(now):
    """What the node has now, as a request for the network page would say it -
    what it goes back to. None (and why) where it cannot be said so. The root
    helper keeps the network itself whole as well (1.0.139) and puts that back;
    this is what the other node is told, and what is asked where nothing was
    kept."""
    d = (now or {}).get('data') or {}
    conf = d.get('conf') or {}
    live = d.get('live') or {}
    addr = net_current_ip(now or {})
    if not addr or '/' not in addr:
        return None, 'what the node has now could not be read (%s) - it cannot be put back ' \
                     'by itself' % (conf.get('ipv4_method') or '?')
    m6 = conf.get('ipv6_method')
    on6 = m6 not in (None, '', 'disabled', 'ignore')
    manual = conf.get('ipv4_method') == 'manual'
    return {'con': d.get('con') or '',
            'ipv4': {'addr': addr, 'gw': conf.get('ipv4_gateway') or ('' if manual else
                                                                       live.get('gw4') or ''),
                     'dns': list(conf.get('ipv4_dns') or [x for x in live.get('dns') or []
                                                          if ':' not in x][:4]),
                     'search': list(conf.get('ipv4_search') or [])},
            'ipv6': {'on': on6, 'mode': 'manual' if m6 == 'manual' else 'auto',
                     'addr': (conf.get('ipv6_addresses') or [''])[0] if m6 == 'manual' else '',
                     'gw': conf.get('ipv6_gateway') or '', 'dns': list(conf.get('ipv6_dns') or [])},
            'hostname': str(d.get('hostname') or ''), 'vip_elsewhere': True}, ''


def net_trial_min():
    return int(CONFIG.get('net_confirm_min') or 0)


def net_trial_start(store, job, by):
    """Back up after the reboot, all well: the job waits to be kept."""
    n = int(job.get('trial_min') or 0)
    job['trial_until'] = time.time() + n * 60
    _job_put(store, job, 'it waits to be kept: Keep it within %d min (Settings - Network, '
             'the banner on every page, or  otp --change-keep net --node %s), or the old '
             'network comes back by itself at %s' % (
                 n, node_name(), time.strftime('%H:%M', time.localtime(job['trial_until']))),
             99, state='trial')
    store.add_event('settings', 'the new network of %s is on trial: kept within %d min, or it '
                    'goes back to %s' % (node_name(), n, odict(job.get('want')).get('old_ip')),
                    'warn', who=by)


def net_go_back(daemon, job, why):
    """The old network asked for, on this node - the same job the other way."""
    store = daemon.store
    me = node_name()
    back = job.get('back')
    job['back_asked'] = time.time()
    if not back:
        _job_put(store, job, 'not kept (%s), and it cannot go back by itself: %s' % (
            why, job.get('back_why') or '?'), job.get('pct'), ok=False, state='failed')
        store.add_event('settings', 'the old network of %s could not be put back: not kept (%s), and '
                        'it cannot go back by itself' % (me, why), 'bad')      # mailed (1.0.242)
        return
    # The network as it is now read first: going back is planned from what
    # the node has (the new address), so the other node is told the old one.
    try:
        net_publish(store)
    except Exception as e:                              # noqa: BLE001
        log('network: read before going back: %s' % e, 'warn')
    _job_put(store, job, 'not kept: %s - the old network (%s) comes back' % (
        why, odict(back.get('ipv4')).get('addr')), job.get('pct'), ok=False,
        state='going back')
    # In the events too (1.0.242): mailed, as the firewall's and the SSH server's are.
    store.add_event('settings', '%s went back to the network it had before (%s): %s'
                    % (me, odict(back.get('ipv4')).get('addr') or '?', why), 'warn')

    try:
        net_ask(store, me, back, 'otp (%s)' % why, rollback=True, maint=bool(job.get('maint')),
                snap=job.get('snap') or '')
    except Exception as e:                              # noqa: BLE001
        _job_put(store, job, 'the old network could not be asked for: %s' % e, job.get('pct'),
                 ok=False, state='failed')
        store.add_event('settings', 'the old network of %s could not be put back: %s' % (me, e),
                        'bad')


def net_trial_tick(daemon, job):
    """A job on trial: kept, asked to go back, or out of time."""
    store = daemon.store
    me = node_name()
    keep = _meta_json(store, 'net:keep:' + me) or {}
    back = _meta_json(store, 'net:back:' + me) or {}
    if keep.get('id') == job.get('id'):
        job['kept'] = keep.get('by')
        _job_put(store, job, 'kept by %s' % keep.get('by'), 100, state='done')
        store.add_event('settings', '%s kept the new network of %s' % (keep.get('by'), me),
                        who=keep.get('by'))
        w = job.get('want') or {}
        # Only where the other node was told the new address beside the old one, and the
        # address did change (1.0.262): a Keep of a new gateway, DNS or name - or replication on
        # another address - asked it to take out "the old" one, its own line, and replication
        # from this node was refused.
        if job.get('keep_old') and job.get('told') and w.get('ip_changed') and \
                w.get('old_ip') and w.get('new_ip') and w['old_ip'] != w['new_ip']:
            # The other node may let only the new address in again.
            store.set_meta('readdress:dropold:' + me, json.dumps({
                'id': job.get('id'), 'from': me, 'old': w['old_ip'], 'new': w['new_ip'],
                'at': time.time()}))
        return
    if back.get('id') == job.get('id'):
        net_go_back(daemon, job, 'put back by %s' % back.get('by'))
        return
    if time.time() > fnum(job.get('trial_until')):
        wait = net_trial_back_wait(store, job)
        if wait:
            if job.get('back_wait') != wait:
                job['back_wait'] = wait
                _job_put(store, job, 'not kept in time - going back waits (at most %d min more): '
                         '%s' % (NET_TRIAL_BACK_WAIT_S // 60, wait), job.get('pct'), ok=False)
            return
        net_go_back(daemon, job, 'not kept within %d min' % int(job.get('trial_min') or 0))


# Going back after the time ran out waits this long at most for another node to answer
# (1.0.262).
NET_TRIAL_BACK_WAIT_S = 30 * 60


def net_trial_back_wait(store, job):
    """Why going back (it restarts this node) waits now, or '' (1.0.262): run out while no other
    node answers - one heard from but out of service, or none heard from at all - both nodes
    were down at once. Only on time-out, and for 30 minutes at most: a network that cut this node
    off goes back all the same, later."""
    if not in_cluster(store):
        return ''
    if time.time() > fnum(job.get('trial_until')) + NET_TRIAL_BACK_WAIT_S:
        return ''
    held = net_others_held(store, node_name())
    if held:
        return held
    if not others_in_service(store):
        return 'no other node answers now - going back restarts this one'
    return ''


def net_trial_answer(store, node, act, by):
    """The pages (of either node) or the command line: keep it, or go back."""
    job = _meta_json(store, 'net:job:' + node) or {}
    if job.get('state') != 'trial':
        raise ValueError('the network of %s is not waiting to be kept' % node)
    store.set_meta('net:%s:%s' % ('keep' if act == 'keep' else 'back', node),
                   json.dumps({'id': job.get('id'), 'by': by, 'at': time.time()}))
    return ('kept - %s says so within a few seconds' % node if act == 'keep' else
            'the old network comes back - %s restarts with it' % node)


def readdress_dropold_tick(store):
    """The other node's new address kept: its old one no longer let in."""
    me = node_name()
    for r in dbguard_rows(store.db, store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'readdress:dropold:%'")):
        ask = json_obj(r['v'])
        if ask is None:
            continue
        if not isinstance(ask, dict) or ask.get('from') in (me, None):
            continue
        done_key = 'readdress:dropold:done:' + me
        if (store.get_meta(done_key) or '') == str(ask.get('id')):
            continue
        try:
            said = _readdress_hba(ask['old'], ask['new'], False, drop_old=True)
            log('the other node kept its new address %s: %s' % (ask['new'], said), 'info')
        except Exception as e:                          # noqa: BLE001
            log('the old address of the other node could not be taken out of pg_hba.conf: %s'
                % e, 'warn')
        store.set_meta(done_key, str(ask.get('id')))


# ---- the firewall --------------------------------------------------------------------
def fw_trial_min():
    return int(CONFIG.get('fw_confirm_min') or 0)


ACCESS_INSTALLED = ('192.168.0.0/16', '172.16.0.0/12', '10.0.0.0/8')


def access_in_nginx():
    """Who may reach the pages as nginx has it now (root reads it): kept for a
    trial's put-back when otp never set the lists itself (1.0.209)."""
    try:
        now = web_status().get('access') or {}
    except Exception:                                   # noqa: BLE001
        now = {}
    out = {}
    for k in ACCESS_WORDS:
        one = now.get(k)
        if not isinstance(one, dict):
            return {}
        out[k] = {'any': bool(one.get('any')), 'from': [str(x) for x in one.get('from') or []]}
    return out


def fw_trial_begin(store, by):
    """Before a change of the firewall or of who may reach the pages: what is
    there now kept, for going back to."""
    n = fw_trial_min()
    if not n:
        return None
    t = time.time()
    trial = _meta_json(store, 'fw:trial') or {}
    if not trial or trial.get('done'):
        trial = {'id': secrets.token_hex(6), 'was': fw_conf(store),
                 'access': access_conf(store) or access_in_nginx(), 'at': t, 'by': by}
    trial.update(until=t + n * 60, last_by=by, min=n)
    store.set_meta('fw:trial', json.dumps(trial))
    # The key the put-back is claimed by made now, by this node alone (1.0.139):
    # made by both at the moment it ran out, it came over to each as a second
    # row with the same key, and replication stopped.
    if store.get_meta('fw_trial_back') is None:
        store.set_meta('fw_trial_back', '')
    return trial


def fw_trial_answer(store, act, by):
    trial = _meta_json(store, 'fw:trial') or {}
    if not trial or trial.get('done'):
        raise ValueError('no change of the firewall waits to be kept')
    if act == 'keep':
        if time.time() > fnum(trial.get('until')):
            # Its time over (1.0.271): the other node may be putting it back this very moment -
            # "kept" said here, and what was there before came back all the same.
            raise ValueError('the time to keep it is over - it is being put back; make the change '
                             'again if it is wanted')
        trial.update(done='kept', done_by=by, done_at=time.time())
        store.set_meta('fw:trial', json.dumps(trial))
        store.add_event('settings', '%s kept the change of the firewall and access' % by,
                        who=by)
        return 'kept'
    fw_put_back(store, trial, 'put back by %s' % by)
    return 'what was there before comes back - each node puts it in within a few seconds'


def fw_put_back(store, trial, why):
    was = trial.get('was') or {}
    # Put back as something said (1.0.146): a firewall never set before went
    # back as "not set", which root reads as "leave it as it is" - and the
    # rules of the trial stayed; so did the lists of who may reach the pages.
    store.set_meta('fw:conf', json.dumps(dict(was, set=True, at=time.time(),
                                              by='otp (%s)' % why)))
    # Never "everybody" when nothing was known (1.0.209): the lists never saved
    # here were nginx's own - the private networks of the install - and the
    # put-back opened the administration to the internet.
    store.set_meta('web:access', json.dumps(trial.get('access') or {
        k: {'any': k not in ('admin', 'portal'), 'from': [] if k not in ('admin', 'portal')
            else list(ACCESS_INSTALLED)} for k in ACCESS_WORDS}))
    trial.update(done='back', done_by=why, done_at=time.time())
    store.set_meta('fw:trial', json.dumps(trial))
    store.add_event('settings', 'the firewall and access went back to what they were before '
                    '%s: %s' % (time.strftime('%H:%M', time.localtime(trial.get('at') or 0)),
                                why), 'warn')
    log('the firewall went back: %s' % why, 'warn')


def fw_trial_tick(store):
    trial = _meta_json(store, 'fw:trial') or {}
    if not trial or trial.get('done') or time.time() <= fnum(trial.get('until')):
        return
    # One node puts it back (both would write the same rows at once).
    if claim_once(store, 'fw_trial_back', trial.get('id')):
        fw_put_back(store, trial, 'not kept within %d min' % int(trial.get('min') or 0))


def trials_view(store):
    """What waits to be kept, for the banner of every page and --status."""
    out = []
    t = time.time()
    for r in dbguard_rows(store.db, store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'net:job:%'")):
        job = json_obj(r['v'])
        if job is None:
            continue
        if isinstance(job, dict) and job.get('state') == 'trial':
            w = job.get('want') if isinstance(job.get('want'), dict) else {}
            out.append({'kind': 'net', 'node': job.get('node') or r['k'][8:],
                        'until': fnum(job.get('trial_until')), 'by': job.get('by'),
                        'words': 'the new network of %s (%s)' % (
                            job.get('node') or r['k'][8:], w.get('new_ip') or '?'),
                        'back': (w.get('old_ip') or '')})
    trial = _meta_json(store, 'fw:trial') or {}
    if trial and not trial.get('done') and fnum(trial.get('until')) > t - 60:
        out.append({'kind': 'fw', 'node': '', 'until': fnum(trial.get('until')),
                    'by': trial.get('last_by') or trial.get('by'),
                    'words': 'the change of the firewall and access', 'back': ''})
    return out


def trial_problem_words(trials):
    return ['%s waits to be kept: %d min left, then it goes back by itself (Keep it on the '
            'banner, or  otp --change-keep %s%s)' % (
                x['words'], max(0, int((x['until'] - time.time()) // 60)), x['kind'],
                (' --node %s' % x['node']) if x.get('node') else '') for x in trials]
