

# ---- disks and logs (1.0.166) ------------------------------------------------------
# Settings → Disks and logs: how much systemd's journal may take and for how
# long, and how many of otp's own log files logrotate keeps - the same for
# every node, each node putting it in on its own machine through its root
# helper (logs.ask): journald.conf.d/00-otp.conf and /etc/logrotate.d/otp.
# Asked again when the settings change, and every 6 hours to read how much
# the journal and the logs take now. Done in the alerts' thread: never on
# the way of a sign-in.
LOGS_EVERY = 6 * 3600
LOGS_WORK = {'at': 0.0, 'hash': '', 'again': ''}
LOGS_LOCK = threading.Lock()


def logs_desired():
    return {'journal_mb': int(CONFIG.get('logs_journal_mb') or 0),
            'journal_days': int(CONFIG.get('logs_journal_days') or 0),
            'keep': int(CONFIG.get('logs_keep') or 30),
            'max_mb': int(CONFIG.get('logs_max_mb') or 200)}


def logs_hash(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]


def dir_size(path, most=200000):
    total, n = 0, 0
    for top, _dirs, files in os.walk(str(path)):
        for f in files:
            n += 1
            if n > most:
                return total
            try:
                total += os.lstat(os.path.join(top, f)).st_size
            except OSError:
                pass
    return total


def logs_start(daemon):
    """logs_tick in a thread of its own: the helper may take its time (90 s
    when it does not answer) and the alerts never wait for it."""
    if LOGS_WORK.get('busy'):
        return
    LOGS_WORK['busy'] = True

    def go():
        try:
            logs_tick(daemon)
        except Exception as e:                          # noqa: BLE001
            log_sparing('logs', 'the journal and the logs: %s' % e, 'warn', every=900)
        finally:
            LOGS_WORK['busy'] = False
    threading.Thread(target=go, name='otp-logs', daemon=True).start()


def logs_tick(daemon, force=False):
    """This node's journal and logrotate as the settings say; what they take."""
    with LOGS_LOCK:
        return _logs_tick(daemon, force)


def _logs_tick(daemon, force):
    store = daemon.store
    want = logs_desired()
    h = logs_hash(want)
    again = store.get_meta('host:logs:again') or ''
    k = 'host:logs:' + node_name()
    row = _meta_json(store, k) or {}
    age = time.time() - float(row.get('at') or 0)
    if force or again != LOGS_WORK['again'] or row.get('hash') != h:
        pass
    elif age < (LOGS_EVERY if row.get('ok') else 600):
        return row
    LOGS_WORK['again'] = again
    out = {'at': time.time(), 'hash': h, 'want': want, 'ok': False,
           'logdir': dir_size(LOG_DIR), 'state': dir_size(STATE_DIR)}
    try:
        got = root_ask('logs.ask', 'logs.ans', dict(want, do='apply'), wait=90)
        out.update(ok=True, **{x: got.get(x) for x in ('journal_use', 'journal_conf',
                                                       'rotate_conf', 'said')})
    except ValueError as e:
        out['said'] = str(e)[:300]
    store.set_meta(k, json.dumps(out))
    if row.get('hash') and row.get('hash') != h and out['ok']:
        log('the journal and the logs set as Settings say: %s' % json.dumps(want))
    return out


def logs_view(store):
    nodes = [n['name'] for n in ha_nodes(store)] if CONFIG.get('ha_mode') else [node_name()]
    want = logs_desired()
    h = logs_hash(want)
    out = []
    for n in nodes:
        row = _meta_json(store, 'host:logs:' + n) or {}
        health = _meta_json(store, 'host:health:' + n) or {}
        out.append({'node': n, 'me': n == node_name(), 'disks': health.get('disks') or [],
                    'health_at': health.get('at'), 'at': row.get('at'), 'ok': row.get('ok'),
                    'said': row.get('said') or '', 'current': row.get('hash') == h,
                    'journal_use': row.get('journal_use'), 'logdir': row.get('logdir'),
                    'state': row.get('state'), 'siem': health.get('siem') or {}})
    return {'nodes': out, 'want': want, 'disk_pct': int(CONFIG.get('alerts_disk_pct') or 0)}
