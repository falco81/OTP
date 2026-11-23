"""1.0.320 (parts): root's keys never from the pages whoever is named; high security looks at
isemon's targets; SSH root with a code only as its check takes it; config.json put back as it is on
disk; a certificate after a short name became a full one; an update waits for a network on trial;
every SSH port labelled for SELinux."""
import sys, pathlib
P = pathlib.Path(sys.argv[1])


def edit(name, pairs):
    p = P / name
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (name, n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit('90h_host_api.py', [
("""    if act in ('add', 'drop', 'rk_make', 'rk_given', 'rk_again') and user == 'root':
""",
 """    # Root's whoever is named (1.0.320): rk_* work on root's keys alone, and "user": "alice"
    # had a key put into /root/.ssh/authorized_keys from the pages.
    if act in ('rk_make', 'rk_given', 'rk_again') or (act in ('add', 'drop') and user == 'root'):
"""),
])

edit('88h_hisec.py', [
("""            if key in checked or any(k in checked for k in ('mail_mode', 'sms_mode', 'siem',
                                                            'admin_2fa', 'portal', 'proxy')):
""",
 """            # isemon's too (1.0.320): its targets or isemon itself saved alone were never looked at.
            if key in checked or any(k in checked for k in ('mail_mode', 'sms_mode', 'siem',
                                                            'admin_2fa', 'portal', 'proxy',
                                                            'isemon', 'isemon_targets')):
"""),
("""    if c.get('permit_root') == 'yes':
        hisec_refuse('root over SSH with a password', 'sshd:root')
""",
 """    # With the code from otp and no password to fall back on, root comes in with a key and the
    # code - as the findings take it (1.0.320): high security went on, then refused every save.
    if c.get('permit_root') == 'yes' and not (c.get('radius') and not c.get('radius_fallback')):
        hisec_refuse('root over SSH with a password', 'sshd:root')
"""),
])

edit('87e_selinux.py', [
("""        sp = int(odict(now.get('values')).get('port') or 22)
        if sp != 22:
            ports.append({'port': sp, 'proto': 'tcp', 'type': 'ssh_port_t',
                          'why': 'the SSH server listens on it'})
""",
 """        # Each port (1.0.320): sshd on 22 and 2222 reads "22 2222" - no number, none labelled.
        for one in str(odict(now.get('values')).get('port') or '22').replace(',', ' ').split():
            sp = int(one)
            if sp != 22 and 0 < sp < 65536:
                ports.append({'port': sp, 'proto': 'tcp', 'type': 'ssh_port_t',
                              'why': 'the SSH server listens on it'})
"""),
])

edit('87n_net.py', [
("""def cluster_busy(store, skip=()):
""",
 """def _net_file_now():
    \"\"\"config.json as it is on disk (1.0.320): write_file_settings leaves FILE_CONFIG as it was
    loaded, and a job that failed compared with that - db_host it had written stayed.\"\"\"
    try:
        got = json.loads(Path(CONFIG_FILE).read_text(encoding='utf-8'))
        return got if isinstance(got, dict) else dict(FILE_CONFIG)
    except Exception:                                   # noqa: BLE001
        return dict(FILE_CONFIG)


def _net_file_differs(undo):
    now = _net_file_now()
    return {k: v for k, v in odict(undo.get('file')).items()
            if str(now.get(k) or '') != str(v or '')}


def cluster_busy(store, skip=()):
"""),
("""                if net_job_active(_meta_json(store, 'net:job:' + n)):
                    return '%s is changing its network' % n
""",
 """                if net_job_active(_meta_json(store, 'net:job:' + n)):
                    return '%s is changing its network' % n
                # A network on trial too (1.0.320): an update drained the other node meanwhile,
                # the trial ran out and went back with a restart - both nodes down.
                if 'trial' not in skip and net_job_on_trial(_meta_json(store, 'net:job:' + n)):
                    return '%s has a new network on trial - keep it or put it back first' % n
"""),
("""    busy = cluster_busy(store, skip=('power',) + (('osup',) if from_osup else ()))
""",
 """    busy = cluster_busy(store, skip=('power', 'trial') + (('osup',) if from_osup else ()))  # its own words below
"""),
("""    if not rollback:
        busy = cluster_busy(store, skip=('power',))
""",
 """    if not rollback:
        busy = cluster_busy(store, skip=('power', 'trial'))
"""),
("""    files = {k: v for k, v in odict(undo.get('file')).items()
             if str(FILE_CONFIG.get(k) or '') != str(v or '')}
    if files:
        write_file_settings(files)
        CONFIG.update(files)
        said.append('config.json: ' + ', '.join('%s = %s' % kv for kv in sorted(files.items())))
""",
 """    files = _net_file_differs(undo)
    if files:
        write_file_settings(files)
        CONFIG.update(files)
        said.append('config.json: ' + ', '.join('%s = %s' % kv for kv in sorted(files.items())))
"""),
("""            files = {k: v for k, v in odict(undo.get('file')).items()
                     if str(FILE_CONFIG.get(k) or '') != str(v or '')}
            if files:
                write_file_settings(files)
""",
 """            files = _net_file_differs(undo)
            if files:
                write_file_settings(files)
"""),
("""        swap[w['old_hostname']] = w['hostname']
        swap[w['old_hostname'].split('.')[0]] = w['hostname'].split('.')[0]
""",
 """        swap[w['old_hostname']] = w['hostname']
        # The short names only of full ones (1.0.320): otp1 to otp2.example.cz swapped otp1 for
        # otp2 over the full name just set - the certificate never named the full one.
        if '.' in w['old_hostname'] and w['old_hostname'].split('.')[0] not in swap:
            swap[w['old_hostname'].split('.')[0]] = w['hostname'].split('.')[0]
"""),
("""    new_names = _cert_names_swap(names, swap)
    if new6 and _cert_name_key(new6) not in set(_cert_name_key(x) for x in new_names):
        new_names.append(new6)
""",
 """    new_names = _cert_names_swap(names, swap)
    if new6 and _cert_name_key(new6) not in set(_cert_name_key(x) for x in new_names):
        new_names.append(new6)
    if w['hostname'] and _cert_name_key(w['hostname']) not in set(_cert_name_key(x) for x in new_names):
        new_names.append(w['hostname'])
"""),
])

edit('88z_alerts.py', [
("""    msg = _al_msg(subject, page, text, to)
    entry = alert_send(store, msg, to, 'report', [])
""",
 """    try:
        msg = _al_msg(subject, page, text, to)
    except MailError as e:
        # Not sent at all (1.0.320): no sender set - the period was kept as sent, never tried again.
        raise ValueError(str(e))
    entry = alert_send(store, msg, to, 'report', [])
"""),
("""                    except Exception as e:      # noqa: BLE001
                        # The period given back (1.0.207): claimed before it was
                        # made, a report that failed to be made was never tried again.
                        if not isinstance(e, MailError):
""",
 """                    except Exception as e:      # noqa: BLE001
                        # The period given back (1.0.207): claimed before it was
                        # made, a report that failed to be made was never tried again.
                        # In 30 min, not each minute (1.0.320): a report too big for the reader's
                        # time, or no address, was made again every minute.
                        ALERT_WORK['report_fail'] = time.monotonic()
                        if not isinstance(e, MailError):
"""),
("""    nodes = [n['name'] for n in ha_nodes(store)] if CONFIG.get('ha_mode') else [node_name()]
    since, until, pid = report_period()
""",
 """    # Both nodes of one shared database too (1.0.320), as the mails say them.
    nodes = [n['name'] for n in ha_nodes(store)] if in_cluster(store) else [node_name()]
    since, until, pid = report_period()
"""),
])

edit('90a_alerts_api.py', [
("""    nodes = [n['name'] for n in ha_nodes(h.store)] if CONFIG.get('ha_mode') else [node_name()]
    me = h.d.siem.state() if getattr(h.d, 'siem', None) else {}
""",
 """    nodes = [n['name'] for n in ha_nodes(h.store)] if in_cluster(h.store) else [node_name()]
    me = h.d.siem.state() if getattr(h.d, 'siem', None) else {}
"""),
])

edit('90_api.py', [
("""    h.me()
    nodes = [n['name'] for n in ha_nodes(h.store)] if CONFIG.get('ha_mode') else [node_name()]
    out = []
    for n in sorted(set(nodes) | {node_name()}):
""",
 """    h.me()
    nodes = [n['name'] for n in ha_nodes(h.store)] if in_cluster(h.store) else [node_name()]
    out = []
    for n in sorted(set(nodes) | {node_name()}):
"""),
])
