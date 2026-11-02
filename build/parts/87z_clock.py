# ---- the clocks and the health of the nodes (1.0.222) ------------------------------------
# Codes from the app are worked out from the clock: a node whose clock is off refuses every
# right code - an answer, so the VPN does not ask the other node - and its heartbeat, its
# lockouts and its "newer wins" stamps are off with it. A node that cannot reach the
# directory refuses every password the same way. Chosen on Settings -> Time -> The clocks of
# the nodes (docs/clock-guard.md says all of it):
#
#   clock_mode     off    as until now: nothing of this runs
#                  watch  each node measures its clock against a reference (SNTP to the time
#                         servers of Settings -> Time, or its own) and against the other node
#                         (its database server's clock), says it on the card, warns
#                  guard  and a node whose clock is off (or that cannot reach the directory,
#                         with health_dir) steps aside - only while the other node is well
#   clock_warn_s   off by more than this: a warning
#   clock_aside_s  off by more than this: guard steps the node aside
#   clock_ref      each node's own reference servers (empty: the time servers of Settings -> Time)
#   clock_codes    codes worked out from the corrected time (the clock + its measured offset)
#   clock_beat     the other node's heartbeat judged with the measured difference of the clocks
#   clock_locks    pauses and lockouts on the corrected time
#   health_dir     guard: step aside when this node cannot reach the directory and the other can
CLOCK_MODES = ('off', 'watch', 'guard')
CLOCK_LOCK = threading.Lock()
CLOCK = {'thread': None, 'ref': None, 'ref_src': '', 'ref_err': '', 'ref_at': 0.0, 'refs': [],
         'ref_mono': 0.0, 'ref_wall': 0.0,
         'skew': None, 'skew_err': '', 'skew_at': 0.0, 'skew_of': '', 'dir_ok': None, 'dir_err': '',
         'dir_at': 0.0, 'dirs': [], 'role': 'serve', 'why': '', 'written': 0.0}
CLOCK_STEP_S = 5.0
CLOCK_REF_EVERY_S = 30.0
CLOCK_DIR_EVERY_S = 15.0
CLOCK_FRESH_S = 120.0


def clock_mode():
    m = str(CONFIG.get('clock_mode') or 'off')
    return m if m in CLOCK_MODES else 'off'


def clock_engaged():
    """Anything of it at all. "As until now" (off) runs nothing: exactly as before 1.0.222."""
    return clock_mode() != 'off'


# ---- the reference: SNTP (RFC 4330), one question each -----------------------------------------
NTP_EPOCH = 2208988800


def sntp_offset(server, timeout=1.5):
    """(offset, delay) of one server: offset > 0 when this machine's clock is behind it.
    Raises OSError / ValueError."""
    got = split_targets_parse(server)
    if len(got) != 1:
        raise ValueError('one server: a name or address, name:port')
    host, port = got[0][0], got[0][1] or 123
    infos = socket.getaddrinfo(host, port, 0, socket.SOCK_DGRAM)
    fam, addr = infos[0][0], infos[0][4]
    s = socket.socket(fam, socket.SOCK_DGRAM)
    try:
        s.settimeout(timeout)
        pkt = bytearray(48)
        pkt[0] = 0x23                                   # LI 0, version 4, mode 3 (client)
        t0 = time.time()
        sec = int(t0) + NTP_EPOCH
        frac = int((t0 - int(t0)) * (1 << 32))
        pkt[40:48] = struct.pack('!II', sec, frac)      # our transmit time, echoed back
        s.sendto(bytes(pkt), addr)
        while True:
            data, _a = s.recvfrom(512)
            t3 = time.time()
            if len(data) >= 48 and data[24:32] == bytes(pkt[40:48]):
                break
        mode, stratum = data[0] & 7, data[1]
        if mode not in (4, 5) or stratum == 0 or stratum > 15:
            raise ValueError('the server is not synchronised itself (stratum %d)' % stratum)

        def ts(off):
            a, b = struct.unpack('!II', data[off:off + 8])
            return a - NTP_EPOCH + b / float(1 << 32)
        t1, t2 = ts(32), ts(40)
        return ((t1 - t0) + (t2 - t3)) / 2.0, (t3 - t0) - (t2 - t1)
    finally:
        s.close()


def clock_ref_servers(value=None, store=None):
    """This node's reference servers: its own (clock_ref), else the time servers of Settings ->
    Time."""
    given = CONFIG.get('clock_ref') if value is None else value
    out = [w for w in re.split(r'[\s,;]+', str(given or '').strip()) if w]
    if not out and store is not None:
        try:
            out = [str(x.get('host') if isinstance(x, dict) else x) for x in
                   (ntp_conf(store).get('servers') or [])]
        except Exception:                               # noqa: BLE001
            out = []
    return [x for x in out if x][:5]


def clock_ref_check(servers):
    """[(server, offset or None, words)], and the median offset of those that answered (or None)."""
    got = []
    for srv in servers:
        try:
            try:
                off, delay = sntp_offset(srv)
            except socket.timeout:
                off, delay = sntp_offset(srv)           # one packet lost: asked again (1.0.224)
            got.append((srv, off, 'delay %.0f ms' % (delay * 1000)))
        except (OSError, ValueError, struct.error, UnicodeError) as e:
            got.append((srv, None, str(e)[:160] or 'no answer'))
    offs = sorted(o for _s, o, _w in got if o is not None)
    if not offs:
        return got, None
    mid = len(offs) // 2
    return got, (offs[mid] if len(offs) % 2 else (offs[mid - 1] + offs[mid]) / 2.0)


# ---- the other node: its database server's clock ---------------------------------------------
def clock_peer_skew(store):
    """(name, skew) - the other side's clock minus this one's, from its database server: the
    other node's own PostgreSQL in a replicated pair (on that machine, so its clock), the shared
    database server otherwise ('the database server'). (None, None) when there is no other side
    to ask. Asked in a thread of its own, 3.5 s at most. Raises RuntimeError."""
    if CONFIG.get('ha_mode') == 'replicated' and CONFIG.get('ha_peer'):
        conf = ha_peer_conf(timeout=2)
        name = next((n['name'] for n in ha_nodes(store) if not n.get('me')), 'the other node')
    elif store.db.engine in ('postgres', 'mariadb') and in_cluster(store):
        conf = {k: CONFIG.get(k) for k in DB_KEYS}
        name = CLOCK_DB_SERVER
    else:
        return None, None
    got = {}

    def ask():
        db = None
        try:
            db = db_open(conf, statement_s=2)
            sql = ("SELECT extract(epoch from clock_timestamp())" if db.engine == 'postgres'
                   else "SELECT UNIX_TIMESTAMP(NOW(6))")
            db.value('SELECT 1')                        # connected before the clock is read
            best = None
            for _ in range(3):                          # the shortest of three round trips
                t0 = time.time()
                there = float(db.value(RawSql(sql)))
                t1 = time.time()
                if best is None or t1 - t0 < best[0]:
                    best = (t1 - t0, there - (t0 + t1) / 2.0)
            got['skew'] = best[1]
        except Exception as e:                          # noqa: BLE001
            got['e'] = str(e).split('\n')[0][:160] or 'no answer'
        finally:
            try:
                if db is not None:
                    db.close()
            except Exception:                           # noqa: BLE001
                pass
    t = threading.Thread(target=ask, name='otp-clock-peer', daemon=True)
    t.start()
    t.join(3.5)
    if 'skew' in got:
        return name, got['skew']
    raise RuntimeError(got.get('e') or 'no answer within 3.5 s')


CLOCK_DB_SERVER = 'the database server'


# ---- the directory -----------------------------------------------------------------------------
def clock_dir_check(store):
    """(True | False | None, [(directory, reached, words)]): every directory a realm signs in
    against, reached on one of its servers - connected, its TLS made, and its reading account
    let in (1.0.224: a TCP connect alone took a server that takes the connection and never
    answers, or that refuses the reading account, for well - and the other node was then
    left the sign-ins it could not answer either). None: no realm uses one."""
    used = set()
    try:
        for r in store.realms():
            if r.get('directory'):                      # its passwords, its groups
                used.add(str(r['directory']).lower())
    except Exception:                                   # noqa: BLE001
        return None, []
    out = []
    for row in store.directories(with_secret=True):
        if str(row.get('name') or '').lower() not in used or not row.get('enabled', 1):
            continue
        try:
            ad = Directory(row)
            ad.timeout = min(float(ad.timeout or 10), 3.0)
            ad.DEAD = {}                                # its own: RADIUS's passed-over list untouched
            link = ad.link()
            try:
                words = str(getattr(link, 'otp_host', '') or 'reached')
            finally:
                link.close()
            out.append((row['name'], True, words))
        except (LdapError, OSError, ValueError) as e:
            out.append((row['name'], False, str(e)[:160]))
    if not out:
        return None, out
    return all(x[1] for x in out), out


# ---- the decision ----------------------------------------------------------------------------
def clock_decide(mode, ref, aside_s, codes_fixed, dir_ok, health_dir, peer, aside_now=False,
                 back_s=None, peer_newer=True):
    """('serve' | 'aside', why). `peer`: the other node's state row as known here (None when
    not heard from) - a node steps aside only for one that is well: fresh, serving, its clock
    within aside_s of the reference, and (for the directory) reaching it."""
    if mode != 'guard':
        return 'serve', ''
    peer_well = bool(peer) and peer.get('fresh') and peer.get('role') == 'serve' and \
        not peer.get('maintenance')
    # Back only below aside_s less the warning (1.0.224): a clock wobbling about the limit
    # moved the VIP address eight times in four minutes.
    limit = (back_s if back_s is not None else aside_s) if aside_now else aside_s
    clock_bad = ref is not None and abs(ref) > limit and not codes_fixed
    if clock_bad:
        pr = (peer or {}).get('ref')
        # The other node's word measured after this node's own (1.0.224), or already aside:
        # both clocks off alike, the first to measure stepped aside on the other's old word.
        if peer_well and pr is not None and abs(pr) <= aside_s and (peer_newer or aside_now):
            return 'aside', 'this node\'s clock is %+.1f s off the time servers - the other node answers' % (-ref)
        return 'serve', 'this node\'s clock is off, but the other node cannot take over - it answers'
    if health_dir and dir_ok is False:
        if peer_well and (peer or {}).get('dir_ok') is True:
            return 'aside', 'this node cannot reach the directory - the other node answers'
        return 'serve', 'the directory cannot be reached, but neither can the other node take over'
    return 'serve', ''


def clock_dir_failover(store):
    """Why a request that met the directory unreachable is left to the other node, or ''
    (1.0.223): only with "Step aside when the directory cannot be reached" (mode guard), and
    only while the other node is well - fresh, serving, not in maintenance, not known to be
    without the directory itself. Else it is refused, as before."""
    if clock_mode() != 'guard' or not CONFIG.get('health_dir'):
        return ''
    try:
        p = clock_peer_row(store)
    except Exception:                                   # noqa: BLE001
        return ''
    # The other node known to reach it (1.0.224), not only "not known not to": both nodes
    # without it, neither should leave the sign-ins to the other.
    if not p or not p.get('fresh') or p.get('role') != 'serve' or p.get('maintenance') or \
            p.get('dir_ok') is not True:
        return ''
    return 'the directory cannot be reached from this node - the other node answers'


def clock_aside():
    return clock_engaged() and CLOCK['role'] == 'aside'


def clock_correction():
    """Seconds to add to this machine's clock, by the reference - 0 when not known, not fresh,
    or within clock_warn_s."""
    ref = CLOCK['ref']
    # Aged by the monotonic clock (1.0.224), and dropped when the machine's clock was stepped
    # since it was measured: put right (chronyc makestep, by hand), the old correction was
    # added to a clock right again - every code refused for minutes.
    if ref is None or time.monotonic() - CLOCK['ref_mono'] > CLOCK_FRESH_S * 2 or clock_stepped():
        return 0.0
    if abs(ref) <= float(CONFIG.get('clock_warn_s') or 2):
        return 0.0
    return ref


def clock_stepped():
    """Whether the machine's clock moved by more than a second, against the monotonic one,
    since the reference was measured."""
    if not CLOCK['ref_mono']:
        return False
    return abs((time.time() - time.monotonic()) - CLOCK['ref_wall']) > 1.0


def clock_ref_noted():
    CLOCK['ref_mono'] = time.monotonic()
    CLOCK['ref_wall'] = time.time() - CLOCK['ref_mono']


def clock_now(kind='codes'):
    """The time codes (kind 'codes') or pauses and lockouts (kind 'locks') are worked out
    with: the machine's clock, corrected by the reference with clock_codes / clock_locks."""
    t = time.time()
    if not clock_engaged():
        return t
    if (kind == 'codes' and CONFIG.get('clock_codes')) or (kind == 'locks' and CONFIG.get('clock_locks')):
        return t + clock_correction()
    return t


def clock_skew_of(store, name):
    """The other node's clock minus this one's, as measured here (or as this node's own row
    says, from a process that does not watch): None when not known. With one shared database
    server both nodes measure against it: the other's minus this one's is the difference of
    the two."""
    def mine():
        if CLOCK['skew'] is not None and time.time() - CLOCK['skew_at'] < CLOCK_FRESH_S:
            return CLOCK['skew_of'], CLOCK['skew']
        row = _meta_json(store, 'clock:state:' + node_name()) or {}
        if row.get('skew') is not None and time.time() - float(row.get('at') or 0) < CLOCK_FRESH_S:
            return row.get('skew_of'), float(row['skew'])
        return None, None
    of, sk = mine()
    if sk is None:
        return None
    if of == name:
        return sk
    if of == CLOCK_DB_SERVER:
        row = _meta_json(store, 'clock:state:' + name) or {}
        if row.get('skew_of') == CLOCK_DB_SERVER and row.get('skew') is not None:
            return sk - float(row['skew'])
    return None


def clock_beat_age(store, name, at, now):
    """A heartbeat's age with clock_beat: judged by the measured difference of the clocks, not
    by the sender's clock alone - a node 10 min behind looked dead, one ahead lived for ever."""
    if not (clock_engaged() and CONFIG.get('clock_beat')) or name == node_name():
        return now - at
    sk = clock_skew_of(store, name)
    return now - at if sk is None else now - (at - sk)


# ---- the watch -------------------------------------------------------------------------------
def clock_tick(daemon):
    with CLOCK_LOCK:
        t = CLOCK['thread']
        if t is not None and t.is_alive():
            return
        t = threading.Thread(target=_clock_loop, args=(daemon,), name='otp-clock', daemon=True)
        CLOCK['thread'] = t
    t.start()


def _clock_loop(daemon):
    while True:
        try:
            clock_step(daemon.store)
        except Exception as e:                          # noqa: BLE001
            log_sparing('clock', 'watching the clocks: %s' % e, 'warn', every=600)
        time.sleep(CLOCK_STEP_S)


def clock_watching():
    t = CLOCK['thread']
    return t is not None and t.is_alive()


def clock_peer_row(store, now=None):
    """The other node's row, with 'fresh' worked out by the measured difference of the clocks."""
    now = time.time() if now is None else now
    for n in ha_nodes(store):
        if n.get('me'):
            continue
        row = _meta_json(store, 'clock:state:' + n['name']) or {}
        if not row:
            return None
        sk = clock_skew_of(store, n['name'])
        at = float(row.get('at') or 0) - (sk or 0.0)
        # Its row is written every 10 s (1.0.224: 60 s, and a node aside for its clock stayed
        # silent a minute after the other died), and its heartbeat alive.
        row['fresh'] = now - at < 25 and bool(n.get('alive'))
        row['maintenance'] = bool(n.get('maintenance'))
        if row.get('ref_at') != CLOCK.get('peer_ref_at'):
            CLOCK['peer_ref_at'], CLOCK['peer_ref_seen'] = row.get('ref_at'), time.monotonic()
        return row
    return None


def clock_step(store, now=None, ref=None, skew=None, dir_ok=None, peer=None):
    """One look. `ref`, `skew`, `dir_ok`, `peer` given only by the tests."""
    now = time.time() if now is None else now
    if not clock_engaged():
        if CLOCK['role'] != 'serve':
            CLOCK.update(role='serve', why='')
            MAINT_CACHE['at'] = 0
        # Nothing kept from the time it ran (1.0.223): switched off, the card showed the last
        # measurements as if they were now.
        if CLOCK['ref_at'] or CLOCK['skew_at'] or CLOCK['dir_at']:
            CLOCK.update(ref=None, ref_at=0.0, ref_mono=0.0, ref_wall=0.0, ref_src='', ref_err='', refs=[], skew=None,
                         skew_at=0.0, skew_of='', skew_err='', dir_ok=None, dirs=[], dir_at=0.0)
        return
    if ref is not None:
        CLOCK.update(ref=None if ref == 'none' else ref, ref_at=now, ref_src='test', ref_err='')
        clock_ref_noted()
    elif time.monotonic() - CLOCK['ref_mono'] > CLOCK_REF_EVERY_S or not CLOCK['ref_mono'] or \
            clock_stepped() or CLOCK.pop('measure_now', False):
        servers = clock_ref_servers(store=store)
        got, med = clock_ref_check(servers) if servers else ([], None)
        if med is None and servers and CLOCK['ref'] is not None and not clock_stepped() and \
                time.monotonic() - CLOCK['ref_mono'] < CLOCK_FRESH_S * 2:
            # One answer lost (1.0.224): the last measurement kept until it is too old - not
            # thrown away at once, the node serving again with a clock it knew was off.
            CLOCK.update(refs=got, ref_err='no time server answered just now - the last '
                                           'measurement is used')
            CLOCK['ref_tried'] = time.monotonic()
        else:
            CLOCK.update(refs=got, ref=med, ref_at=now, ref_src=', '.join(servers),
                         ref_err='' if med is not None else (
                             'no time server given (Settings -> Time, or this node\'s own)' if not servers
                             else 'no time server answered'))
            clock_ref_noted()
    if skew is not None:
        of, val = skew if isinstance(skew, tuple) else ('test-peer', skew)
        CLOCK.update(skew=None if val == 'none' else val, skew_at=now, skew_of=of, skew_err='')
    else:
        try:
            name, sk = clock_peer_skew(store)
            if name is not None:
                CLOCK.update(skew=sk, skew_at=now, skew_of=name, skew_err='')
        except Exception as e:                          # noqa: BLE001
            CLOCK.update(skew_err=str(e).split('\n')[0][:160])
    if dir_ok is not None:
        CLOCK.update(dir_ok=None if dir_ok == 'none' else dir_ok, dir_at=now)
    elif CONFIG.get('health_dir') and now - CLOCK['dir_at'] > CLOCK_DIR_EVERY_S:
        ok, dirs = clock_dir_check(store)
        CLOCK.update(dir_ok=ok, dirs=dirs, dir_at=now)
    p = clock_peer_row(store, now) if peer is None else (None if peer == 'none' else peer)
    aside_s = float(CONFIG.get('clock_aside_s') or 20)
    role, why = clock_decide(clock_mode(), CLOCK['ref'], aside_s,
                             bool(CONFIG.get('clock_codes')) and CLOCK['ref'] is not None,
                             CLOCK['dir_ok'], bool(CONFIG.get('health_dir')), p,
                             aside_now=CLOCK['role'] == 'aside',
                             back_s=max(1.0, aside_s - float(CONFIG.get('clock_warn_s') or 2)),
                             peer_newer=peer is not None or
                             CLOCK.get('peer_ref_seen', 0.0) >= CLOCK['ref_mono'])
    if role != CLOCK['role']:
        CLOCK['role'], CLOCK['why'] = role, why
        MAINT_CACHE['at'] = 0
        if role == 'aside':
            log('time: this node steps aside - %s' % why, 'warn')
            _clock_event(store, 'bad', 'this node steps aside: %s - RADIUS is answered by the other '
                         'node, the VIP address goes to it' % why)
        else:
            log('time: this node answers again', 'info')
            _clock_event(store, 'good', 'this node answers again%s' % (' - ' + why if why else ''))
    else:
        CLOCK['why'] = why
    if now - CLOCK['written'] > 10:
        CLOCK['written'] = now
        try:
            store.set_meta('clock:state:' + node_name(), json.dumps(clock_state_here(now)))
        except Exception:                               # noqa: BLE001
            pass


def clock_state_here(now=None):
    now = time.time() if now is None else now
    return {'at': now, 'node': node_name(), 'engaged': clock_engaged(), 'mode': clock_mode(),
            'ref': CLOCK['ref'], 'ref_at': CLOCK['ref_at'], 'ref_src': CLOCK['ref_src'],
            'ref_err': CLOCK['ref_err'],
            'refs': [{'server': s, 'offset': o, 'words': w} for s, o, w in CLOCK['refs']],
            'skew': CLOCK['skew'], 'skew_of': CLOCK['skew_of'], 'skew_err': CLOCK['skew_err'],
            'dir_ok': CLOCK['dir_ok'], 'dirs': [{'name': n, 'ok': ok, 'words': w} for n, ok, w in CLOCK['dirs']],
            'role': CLOCK['role'], 'why': CLOCK['why'],
            'codes_fixed': bool(CONFIG.get('clock_codes')) and clock_correction() != 0.0,
            'correction': clock_correction()}


def clock_state_of(store, name):
    if name == node_name() and (clock_watching() or CLOCK['ref_at'] > 0):
        return clock_state_here()                       # measured in this process
    return _meta_json(store, 'clock:state:' + name) or {}


def _clock_event(store, level, words):
    try:
        store.add_event('time', words, 'warn' if level == 'bad' else 'info', who='otp (clock)')
    except Exception:                                   # noqa: BLE001
        pass


@node_ask_kind('clock_try')
def _ask_clock_try(daemon, args):
    """Try it on the card: each node asks its own reference servers (as written in the form),
    the other side's clock and its directory."""
    mine = (args.get('refs') or {}).get(node_name())
    servers = clock_ref_servers(mine, daemon.store) if mine is not None else clock_ref_servers(store=daemon.store)
    got, med = clock_ref_check(servers) if servers else ([], None)
    try:
        name, sk = clock_peer_skew(daemon.store)
    except Exception as e:                              # noqa: BLE001
        name, sk = 'the other node', None
        skerr = str(e).split('\n')[0][:160]
    else:
        skerr = ''
    ok, dirs = clock_dir_check(daemon.store)
    return {'ok': med is not None, 'ref': med, 'servers': servers,
            'refs': [{'server': s, 'offset': o, 'words': w} for s, o, w in got],
            'skew': sk, 'skew_of': name, 'skew_err': skerr,
            'dir_ok': ok, 'dirs': [{'name': n, 'ok': o, 'words': w} for n, o, w in dirs]}


CLOCK_KEYS = ('clock_mode', 'clock_warn_s', 'clock_aside_s', 'clock_codes', 'clock_beat',
              'clock_locks', 'health_dir')


def clock_view(store):
    nodes = []
    saved = store.settings_saved()
    on = clock_engaged()
    for n in ha_nodes(store):
        # Switched off (1.0.223): nothing measured is shown - a row of the time it ran is old.
        st = clock_state_of(store, n['name']) if on else {}
        if n.get('me') and not st:
            st = clock_state_here()
        nodes.append({'name': n['name'], 'me': bool(n.get('me')), 'alive': bool(n.get('alive')),
                      'state': st, 'ref': str(saved.get('clock_ref@' + n['name'])
                                              or (CONFIG.get('clock_ref') if n.get('me') else '') or ''),
                      'fresh': bool(st) and time.time() - float(st.get('at') or 0) < 60})
    if not nodes:
        nodes = [{'name': node_name(), 'me': True, 'alive': True, 'state': clock_state_here(),
                  'ref': str(CONFIG.get('clock_ref') or ''), 'fresh': True}]
    try:
        common = [str(x.get('host') if isinstance(x, dict) else x) for x in
                  (ntp_conf(store).get('servers') or [])]
    except Exception:                                   # noqa: BLE001
        common = []
    return {'engaged': clock_engaged(), 'ha_mode': CONFIG.get('ha_mode') or '',
            'cluster': in_cluster(store), 'conf': {k: CONFIG.get(k, DEFAULTS.get(k)) for k in CLOCK_KEYS},
            'me': node_name(), 'nodes': nodes, 'common': [c for c in common if c][:5]}
