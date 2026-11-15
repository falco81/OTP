# 1.0.281: SNMP - every thing the application can tell, typed (for Zabbix and the like): python3 snmp.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('90s_snmp.py', [(
"""    # Every sample Prometheus gets, as a table (name, labels, value) - nothing
    # it has is missing here.""",
"""    # The rest the application can tell, typed (1.0.281): each part by itself - one that fails
    # leaves the others answered.
    for part in (snmp_mib_radius, snmp_mib_host, snmp_mib_dirs, snmp_mib_ha, snmp_mib_backup,
                 snmp_mib_mail, snmp_mib_signin, snmp_mib_clock, snmp_mib_logs):
        try:
            rows += part(daemon, store, db_ok)
        except Exception as e:                          # noqa: BLE001
            log_sparing('snmp-' + part.__name__, 'SNMP, %s: %s' % (part.__name__[9:], e), 'warn', every=600)
    # Every sample Prometheus gets, as a table (name, labels, value) - nothing
    # it has is missing here."""), (
"""# -- the agent -------------------------------------------------------------------------------
class SnmpAgent(object):""",
"""# -- the rest of the MIB (1.0.281): OTP-MIB.txt in deploy/ names every one ------------------------
SNMP_MIB_GAUGE_MAX = 4294967295


def _sn_g(v):
    \"\"\"A Gauge32 never past its end (a value of more is said as the most).\"\"\"
    try:
        v = int(v)
    except (TypeError, ValueError):
        return 0
    return max(0, min(v, SNMP_MIB_GAUGE_MAX))


def snmp_mib_radius(daemon, store, db_ok):
    \"\"\".2.15- : the clients, realms and directories set; the Access-Requests of the last day by result.\"\"\"
    B = SNMP_BASE
    if not db_ok:
        return []
    rows = [(B + (2, 15, 0), 'gauge', _sn_g(len(store.clients()))),
            (B + (2, 16, 0), 'gauge', _sn_g(len(store.realms()))),
            (B + (2, 17, 0), 'gauge', _sn_g(len(getattr(daemon, 'dirs', None) or {})))]
    try:
        rd = daemon.reader()
    except Exception:                                   # noqa: BLE001
        rd = store
    got = {str(x['result'] or '?'): int(x['n']) for x in rd.db.rows(
        "SELECT result, COUNT(*) AS n FROM radius_log WHERE ts >= ? AND packet = 'Access-Request' "
        "GROUP BY result", (time.time() - 86400,))}
    for i, k in enumerate(('accept', 'reject', 'challenge'), 18):
        rows.append((B + (2, i, 0), 'gauge', _sn_g(sum(v for r, v in got.items() if r.lower().startswith(k)))))
    for i, (k, v) in enumerate(sorted(got.items()), 1):
        rows += [(B + (2, 30, 1, 1, i), 'int', i), (B + (2, 30, 1, 2, i), 'str', k[:64]),
                 (B + (2, 30, 1, 3, i), 'gauge', _sn_g(v))]
    return rows


def snmp_mib_host(daemon, store, db_ok):
    \"\"\".10: this node's machine - CPU, memory, disks, network as counters (a rate is the
    monitor's to make), the load, the file systems otp lives on.\"\"\"
    B = SNMP_BASE + (10,)
    raw = _load_raw()
    try:
        cores = os.cpu_count() or 1
    except Exception:                                   # noqa: BLE001
        cores = 1
    try:
        l1, l5, l15 = os.getloadavg()
    except OSError:
        l1 = l5 = l15 = 0.0
    try:
        with open('/proc/uptime') as fh:
            os_up = int(float(fh.read().split()[0]))
    except (OSError, ValueError, IndexError):
        os_up = 0
    rows = [(B + (1, 0), 'counter64', int(raw.get('cpu_idle') or 0)),
            (B + (2, 0), 'counter64', int(raw.get('cpu_all') or 0)),
            (B + (3, 0), 'int', cores),
            (B + (4, 0), 'gauge', _sn_g(round(l1 * 100))),
            (B + (5, 0), 'gauge', _sn_g(round(l5 * 100))),
            (B + (6, 0), 'gauge', _sn_g(round(l15 * 100))),
            (B + (7, 0), 'gauge', _sn_g(int(raw.get('mem_total') or 0) // 1024)),
            (B + (8, 0), 'gauge', _sn_g(int(raw.get('mem_used') or 0) // 1024)),
            (B + (9, 0), 'gauge', _sn_g(int(raw.get('swap_used') or 0) // 1024)),
            (B + (10, 0), 'counter64', int(raw.get('disk_rd') or 0)),
            (B + (11, 0), 'counter64', int(raw.get('disk_wr') or 0)),
            (B + (12, 0), 'counter64', int(raw.get('net_rx') or 0)),
            (B + (13, 0), 'counter64', int(raw.get('net_tx') or 0)),
            (B + (14, 0), 'gauge', _sn_g(os_up))]
    for i, d in enumerate(disks_now(), 1):
        rows += [(B + (20, 1, 1, i), 'int', i), (B + (20, 1, 2, i), 'str', d['path']),
                 (B + (20, 1, 3, i), 'gauge', _sn_g(d['total'] // 1024)),
                 (B + (20, 1, 4, i), 'gauge', _sn_g(d['used'] // 1024)),
                 (B + (20, 1, 5, i), 'gauge', _sn_g(d['free'] // 1024)),
                 (B + (20, 1, 6, i), 'gauge', _sn_g(round(d['pct']))),
                 (B + (20, 1, 7, i), 'gauge', _sn_g(round(d['inodes'])))]
    return rows


def snmp_mib_dirs(daemon, store, db_ok):
    \"\"\".11: each directory (Active Directory) and whether a server of it answers this node.\"\"\"
    B = SNMP_BASE + (11, 1, 1)
    rows, now = [], time.time()
    for i, (name, d) in enumerate(sorted((getattr(daemon, 'dirs', None) or {}).items()), 1):
        hosts = [h.lower() for h in (getattr(d, 'hosts', None) or [])]
        on = 1 if int(d.row.get('enabled') if d.row.get('enabled') is not None else 1) else 0
        with Directory.DEAD_LOCK:
            dead = bool(hosts) and all(float(Directory.DEAD.get(h) or 0) > now for h in hosts)
        rows += [(B + (1, i), 'int', i), (B + (2, i), 'str', str(name)[:64]),
                 (B + (3, i), 'int', on), (B + (4, i), 'int', 0 if (dead or not hosts) else 1),
                 (B + (5, i), 'str', ', '.join(hosts)[:255])]
    return rows


def snmp_mib_ha(daemon, store, db_ok):
    \"\"\".12: the cluster - whether this node holds the VIP address, the replication both ways.\"\"\"
    B = SNMP_BASE + (12,)
    if not db_ok:
        return []
    v = vip_conf(store) or {}
    on = bool(v.get('on'))
    here = 1 if on and vip_here(v.get('address')) else 0
    rows = [(B + (1, 0), 'int', 1 if in_cluster(store) else 0), (B + (2, 0), 'int', 1 if on else 0),
            (B + (3, 0), 'int', here), (B + (4, 0), 'str', str(v.get('address') or '') if on else '')]
    if CONFIG.get('ha_mode') == 'replicated' and store.db.engine == 'postgres':
        rep = ha_repl_state(store)
        for i, x in enumerate(rep.get('incoming') or [], 1):
            rows += [(B + (10, 1, 1, i), 'int', i), (B + (10, 1, 2, i), 'str', str(x.get('name') or '')[:64]),
                     (B + (10, 1, 3, i), 'int', 1 if x.get('running') else 0),
                     (B + (10, 1, 4, i), 'counter', _sn_g(int(x.get('apply_errors') or 0) + int(x.get('sync_errors') or 0)))]
        for i, x in enumerate(rep.get('outgoing') or [], 1):
            rows += [(B + (11, 1, 1, i), 'int', i), (B + (11, 1, 2, i), 'str', str(x.get('name') or '')[:64]),
                     (B + (11, 1, 3, i), 'gauge', _sn_g(int(x.get('behind') or 0))),
                     (B + (11, 1, 4, i), 'str', str(x.get('wal_status') or '')[:32])]
    return rows


def snmp_mib_backup(daemon, store, db_ok):
    \"\"\".13: this node's nightly copy and the backups sent away.\"\"\"
    B = SNMP_BASE + (13,)
    now = time.time()
    last = 0.0
    try:
        kept = backups()
        try:
            kept = kept + kept_dumps(store.db.engine)
        except Exception:                               # noqa: BLE001
            pass
        last = max([float(b.get('at') or b.get('mtime') or 0) for b in kept] or [0])
    except Exception:                                   # noqa: BLE001
        last = 0.0
    rows = [(B + (1, 0), 'int', 1 if CONFIG.get('backup_daily') else 0),
            (B + (2, 0), 'int', int(last)), (B + (3, 0), 'gauge', _sn_g(now - last) if last else SNMP_MIB_GAUGE_MAX),
            (B + (4, 0), 'int', 1 if CONFIG.get('rbackup') else 0)]
    mine = [r for r in rb_history(store) if r.get('node') == node_name()] if db_ok and CONFIG.get('rbackup') else []
    ok = [r for r in mine if r.get('ok')]
    # Answered with backups sent away off too (1.0.281): a monitor asking for them gets "none", not nothing.
    rows += [(B + (5, 0), 'int', (1 if mine[0].get('ok') else 0) if mine else 1),
             (B + (6, 0), 'int', int(fnum(ok[0].get('at'))) if ok else 0),
             (B + (7, 0), 'gauge', _sn_g(now - fnum(ok[0].get('at'))) if ok else SNMP_MIB_GAUGE_MAX)]
    return rows


def snmp_mib_mail(daemon, store, db_ok):
    \"\"\".14: the mail waiting to go, by state.\"\"\"
    if not db_ok:
        return []
    q = mailq_counts(store)
    return [(SNMP_BASE + (14, i, 0), 'gauge', _sn_g(q.get(k, 0))) for i, k in enumerate(MAILQ_STATES, 1)]


def snmp_mib_signin(daemon, store, db_ok):
    \"\"\".15: the ways of signing in to the administration, and the revocation of certificates.\"\"\"
    B = SNMP_BASE + (15,)
    crls = crls_now()
    answers = ocsp_now()
    now = time.time()
    return [(B + (1, 0), 'int', 1 if _setting_on(CONFIG.get('admin_kerberos')) else 0),
            (B + (2, 0), 'int', 1 if _setting_on(CONFIG.get('admin_cert')) else 0),
            (B + (3, 0), 'int', 1 if _setting_on(CONFIG.get('admin_password_off')) else 0),
            (B + (4, 0), 'int', 1 if _setting_on(CONFIG.get('admin_2fa')) else 0),
            (B + (5, 0), 'gauge', _sn_g(len(crls))),
            (B + (6, 0), 'gauge', _sn_g(sum(1 for c in crls if not c.get('ok') or (c.get('next') and float(c['next']) <= now)))),
            (B + (7, 0), 'str', ocsp_mode()),
            (B + (8, 0), 'gauge', _sn_g(len(answers))),
            (B + (9, 0), 'gauge', _sn_g(sum(1 for c in answers if c.get('status') != 'good' or (c.get('next') and float(c['next']) <= now))))]


def snmp_mib_clock(daemon, store, db_ok):
    \"\"\".16: the clock guard - engaged, how far this node is from the reference (ms).\"\"\"
    B = SNMP_BASE + (16,)
    c = clock_state_here()
    ref = c.get('ref')
    skew = c.get('skew')
    return [(B + (1, 0), 'int', 1 if c.get('engaged') else 0),
            (B + (2, 0), 'str', str(c.get('mode') or '')),
            (B + (3, 0), 'int', int(round(float(ref) * 1000)) if isinstance(ref, (int, float)) else 0),
            (B + (4, 0), 'int', int(round(float(skew) * 1000)) if isinstance(skew, (int, float)) else 0),
            (B + (5, 0), 'int', int(round(float(c.get('correction') or 0) * 1000)))]


def snmp_mib_logs(daemon, store, db_ok):
    \"\"\".17: the logs sent away (isemon, a SIEM): on, in trouble, lines sent and dropped.\"\"\"
    B = SNMP_BASE + (17,)
    rows = []
    for i, what in enumerate(('isemon', 'siem'), 1):
        obj = getattr(daemon, 'shipper' if what == 'isemon' else 'siem', None)
        st = obj.state() if obj else {}
        rows += [(B + (i, 1, 0), 'int', 1 if st.get('on') else 0),
                 (B + (i, 2, 0), 'int', 1 if odict(st.get('trouble')) else 0),
                 (B + (i, 3, 0), 'counter64', sum(int(v or 0) for v in odict(st.get('sent')).values())),
                 (B + (i, 4, 0), 'counter64', int(st.get('dropped') or 0))]
    return rows


# -- the agent -------------------------------------------------------------------------------
class SnmpAgent(object):""")])
print('snmp patched')

# the files for the monitoring, from the SNMP card: OTP-MIB and the Zabbix 7.0 template
edit('90s_snmp.py', [(
"""@node_ask_kind('snmp')
def _ask_snmp(daemon, args):""",
"""SNMP_FILES = {'mib': ('OTP-MIB.txt', 'OTP-MIB.txt'),
              'zabbix': (os.path.join('zabbix', 'otp_by_snmp_zabbix7.yaml'), 'otp_by_snmp_zabbix7.yaml')}


@route('GET', '/api/snmpfile')
def _snmp_file(h):
    \"\"\"OTP-MIB or the Zabbix 7.0 template, as the package has them (1.0.281) - nothing of this server's
    own is in them: the user and its passphrases are set on the host in Zabbix.\"\"\"
    h.me()
    what = str(h.arg('what') or '')
    if what not in SNMP_FILES:
        raise ApiError(404, 'no such file')
    rel, name = SNMP_FILES[what]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deploy', rel)
    try:
        with open(path, encoding='utf-8') as fh:
            text = fh.read(4 << 20)
    except OSError:
        raise ApiError(404, '%s is not in this installation (deploy/%s)' % (name, rel))
    return {'name': name, 'text': text}


@node_ask_kind('snmp')
def _ask_snmp(daemon, args):""")])
print('snmp files patched')
