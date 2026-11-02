# ---- when the two nodes lose each other: split brain (1.0.218) --------------------------
# Two replicating nodes that cannot reach each other each take the other for gone and go on
# alone: a code may be let in on both halves, the wrong tries are counted on each half apart,
# and what the administrators change on each half goes its own way. With no third machine
# this cannot be ruled out; what can be done, chosen on Settings -> High availability ->
# When the nodes lose each other (docs/split-brain.md says it all):
#
#   split_mode      who answers while they are apart:
#                     off       both nodes, as before
#                     arbiter   a node that cannot reach its arbiter either (its default
#                               gateway, or addresses given - each node its own) is the one
#                               cut off: it steps aside
#                     priority  the preferred node alone; the other steps aside
#   split_prefer    the preferred node (empty: the first node of the cluster, ha_slot 1)
#   split_arbiter   each node's arbiter: addresses (ping) or host:port (TCP), empty = its gateway
#   split_after_s   how long the other node's database must not answer before they are apart
#   split_scratch   recovery codes only while the other node can be asked
#   split_halve     the pause and the lockout at half their tries while apart
#   split_freeze    changes on the pages only on the preferred node while apart
#   split_report    a warning while apart, and a report when they are together again
#
# "Apart" is told by the other node's database: asked every two seconds on a connection of
# its own - the very database whose rows say whether a code was used there. Stepping aside
# is maintenance that nobody asked for and that ends by itself: RADIUS is not answered, the
# VIP address goes to the other node, the pages stay. It ends as soon as the other node's
# database answers again, or when this node can reach its arbiter again.
SPLIT_MODES = ('off', 'arbiter', 'priority')
SPLIT_LOCK = threading.Lock()
SPLIT = {'thread': None, 'peer_ok_at': 0.0, 'peer_err': '', 'peer_db': None, 'apart_since': 0.0,
         'role': 'serve', 'why': '', 'arb': [], 'arb_state': None, 'arb_at': 0.0,
         'together_at': 0.0, 'report_due': 0.0, 'written': 0.0, 'started': 0.0, 'gen': 0,
         'last_apart_since': 0.0, 'tidied': 0.0}
SPLIT_STEP_S = 2.0
SPLIT_SAY_SCRATCH = ('A recovery code cannot be used while the two servers cannot reach each '
                     'other - use the code of the app')


def split_active():
    """Only two replicating nodes can be split: with one shared database (or one node) the
    database itself decides what was used."""
    return CONFIG.get('ha_mode') == 'replicated' and bool(CONFIG.get('ha_peer'))


def split_engaged():
    """Whether anything of this runs at all. "As until now" - both nodes go on, every
    switch off - runs nothing: no question to the other node, no arbiter, nothing written,
    nothing changed. Exactly as before 1.0.218."""
    return split_active() and (split_mode() != 'off' or any(
        CONFIG.get(k) for k in ('split_scratch', 'split_halve', 'split_freeze', 'split_report')))


def split_mode():
    m = str(CONFIG.get('split_mode') or 'off')
    return m if m in SPLIT_MODES else 'off'


def split_preferred_name(store=None):
    """The preferred node's name: the one chosen, else the first node (ha_slot 1)."""
    want = str(CONFIG.get('split_prefer') or '').strip()
    if want:
        return want
    if int(CONFIG.get('ha_slot') or 1) == 1:
        return node_name()
    if store is not None:
        for n in ha_nodes(store):
            if not n.get('me'):
                return n['name']
    return ''


def split_me_preferred():
    want = str(CONFIG.get('split_prefer') or '').strip()
    if want:
        return want == node_name()
    return int(CONFIG.get('ha_slot') or 1) == 1


def split_decide(mode, apart, arbiter, preferred):
    """('serve' | 'aside', why). `arbiter`: True reached, False not reached, None cannot be
    told (no way to ask) - never a reason to step aside."""
    if not apart:
        return 'serve', ''
    if mode == 'priority':
        if preferred:
            return 'serve', 'the preferred node answers while the nodes are apart'
        return 'aside', 'the nodes cannot reach each other and this is not the preferred node'
    if mode == 'arbiter':
        if arbiter is False:
            return 'aside', 'neither the other node nor the arbiter can be reached - this node is the one cut off'
        if arbiter is None:
            return 'serve', 'the arbiter cannot be asked from here - this node answers'
        return 'serve', 'the arbiter is reached - this node answers'
    return 'serve', 'both nodes answer while they are apart (no rule chosen)'


# ---- the arbiter ----------------------------------------------------------------------
def default_gateway():
    """This machine's default gateway (IPv4), from /proc/net/route - '' when none."""
    try:
        with open('/proc/net/route') as f:
            for line in f.readlines()[1:]:
                p = line.split()
                if len(p) > 3 and p[1] == '00000000' and int(p[3], 16) & 2:
                    g = int(p[2], 16)
                    return '%d.%d.%d.%d' % (g & 255, (g >> 8) & 255, (g >> 16) & 255, g >> 24)
    except (OSError, ValueError):
        pass
    return ''


SPLIT_TARGET_RE = re.compile(r'^(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.:-]{1,253}?)(?::(\d{1,5}))?\Z')


def split_targets_parse(text):
    """'192.0.2.1, gw.example.cz:443, [2001:db8::1]:53' -> [(host, port or None)]; ValueError."""
    out = []
    for one in [w for w in re.split(r'[\s,;]+', str(text or '').strip()) if w]:
        if one.count(':') > 1 and not one.startswith('['):
            out.append((one, None))                     # a bare IPv6 address
            continue
        m = SPLIT_TARGET_RE.match(one)
        if not m:
            raise ValueError('%s is not an address, a name or name:port' % one[:80])
        host, port = m.group(1).strip('[]'), m.group(2)
        if port is not None and not 0 < int(port) < 65536:
            raise ValueError('%s: the port is 1-65535' % one[:80])
        out.append((host, int(port) if port else None))
    if len(out) > 5:
        raise ValueError('five arbiters at most')
    return out


def split_targets(value=None):
    """This node's arbiters: given, or its default gateway."""
    given = CONFIG.get('split_arbiter') if value is None else value
    try:
        got = split_targets_parse(given)
    except ValueError:
        got = []
    if got:
        return got
    gw = default_gateway()
    return [(gw, None)] if gw else []


def _icmp_sum(data):
    if len(data) % 2:
        data += b'\x00'
    s = sum(int.from_bytes(data[i:i + 2], 'big') for i in range(0, len(data), 2))
    s = (s >> 16) + (s & 0xffff)
    s += s >> 16
    return (~s) & 0xffff


def split_ping(host, timeout=1.0):
    """(True | False | None, how, words): one echo request. A datagram ICMP socket (any user
    in ping_group_range - RHEL's default), else a raw one (root), else /usr/bin/ping. None:
    this machine cannot send one at all - not "unreachable"."""
    try:
        infos = socket.getaddrinfo(host, None, 0, socket.SOCK_DGRAM)
    except (socket.gaierror, UnicodeError) as e:
        return False, 'dns', 'the name does not resolve: %s' % e
    fam, addr = infos[0][0], infos[0][4]
    v6 = fam == socket.AF_INET6
    proto = socket.IPPROTO_ICMPV6 if v6 else socket.IPPROTO_ICMP
    ident = os.getpid() & 0xffff
    payload = b'otp-split' + os.urandom(8)
    for kind in (socket.SOCK_DGRAM, socket.SOCK_RAW):
        try:
            s = socket.socket(fam, kind, proto)
        except (PermissionError, OSError):
            continue
        try:
            s.settimeout(timeout)
            hdr = struct.pack('!BBHHH', 128 if v6 else 8, 0, 0, ident, 1)
            pkt = hdr + payload
            if not v6:
                pkt = struct.pack('!BBHHH', 8, 0, _icmp_sum(pkt), ident, 1) + payload
            s.sendto(pkt, addr)
            end = time.time() + timeout
            while time.time() < end:
                s.settimeout(max(0.05, end - time.time()))
                data = s.recv(2048)
                if kind == socket.SOCK_RAW and not v6:
                    data = data[(data[0] & 15) * 4:]          # the IP header first
                if data[:1] in (b'\x00', b'\x81') and payload in data:
                    return True, 'ping', ''
            return False, 'ping', 'no answer to ping within %.1f s' % timeout
        except socket.timeout:
            return False, 'ping', 'no answer to ping within %.1f s' % timeout
        except OSError as e:
            return False, 'ping', str(e)[:200]
        finally:
            s.close()
    tool = shutil.which('ping')
    if tool:
        try:
            r = subprocess.run([tool, '-c', '1', '-W', str(max(1, int(timeout))), str(host)],
                               capture_output=True, timeout=timeout + 2)
            return r.returncode == 0, 'ping', '' if r.returncode == 0 else 'no answer to ping'
        except (OSError, subprocess.SubprocessError) as e:
            return None, 'ping', str(e)[:200]
    return None, 'none', ('this machine lets nobody send a ping (net.ipv4.ping_group_range) - '
                          'give the arbiter as host:port, checked over TCP')


def split_tcp(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, 'tcp', ''
    except ConnectionRefusedError:
        return True, 'tcp', 'refused, but it answered - it is there'
    except (OSError, socket.timeout) as e:
        return False, 'tcp', str(e)[:200]


def split_arbiter_check(targets=None):
    """[(target words, True | False | None, how, words)] and the verdict: True when any one
    answers, False when every one could be asked and none answered, None when none could
    be asked at all (or there is none)."""
    out = []
    for host, port in (split_targets() if targets is None else targets):
        if port:
            ok, how, words = split_tcp(host, port)
        else:
            ok, how, words = split_ping(host)
        out.append(('%s:%s' % (host, port) if port else host, ok, how, words))
    if any(x[1] is True for x in out):
        verdict = True
    elif out and all(x[1] is False for x in out):
        verdict = False
    else:
        verdict = None
    return out, verdict


@node_ask_kind('split_arbiter')
def _ask_split_arbiter(daemon, args):
    """Try it on the card: each node asks its own arbiter, as written in the form."""
    mine = (args.get('targets') or {}).get(node_name())
    try:
        targets = split_targets(mine if mine is not None else None) if mine is not None else \
            split_targets()
    except ValueError as e:
        return {'ok': False, 'error': str(e)}
    got, verdict = split_arbiter_check(targets)
    return {'ok': verdict is not False, 'verdict': verdict, 'gateway': default_gateway(),
            'targets': [{'target': t, 'ok': ok, 'how': how, 'words': w} for t, ok, how, w in got]}


# ---- the other node's database ------------------------------------------------------------
def _split_peer_probe():
    """Whether the other node's database answers now: True, or the words why not."""
    got = {}

    def ask():
        try:
            db = SPLIT['peer_db']
            if db is None or SPLIT.get('peer_gen') != ONCE_PEER.get('gen'):
                if db is not None:
                    try:
                        db.close()
                    except Exception:                   # noqa: BLE001
                        pass
                db = db_open(ha_peer_conf(timeout=2), statement_s=2)
                SPLIT['peer_db'], SPLIT['peer_gen'] = db, ONCE_PEER.get('gen')
            db.value('SELECT 1')
            got['ok'] = True
        except Exception as e:                          # noqa: BLE001
            got['e'] = str(e).split('\n')[0][:200]
            try:
                if SPLIT['peer_db'] is not None:
                    SPLIT['peer_db'].close()
            except Exception:                           # noqa: BLE001
                pass
            SPLIT['peer_db'] = None
    t = threading.Thread(target=ask, name='otp-split-peer', daemon=True)
    t.start()
    t.join(3.5)
    if got.get('ok'):
        return True
    if t.is_alive():
        SPLIT['peer_db'] = None                         # left to time out by itself
        return 'no answer within 3.5 s'
    return got.get('e') or 'no answer'


# ---- the watch ---------------------------------------------------------------------------
def split_tick(daemon):
    """Started once from the daemon's loop: the watch runs in a thread of its own, so a
    peer that does not answer holds nothing else."""
    with SPLIT_LOCK:
        t = SPLIT['thread']
        if t is not None and t.is_alive():
            return
        SPLIT['started'] = time.time()
        SPLIT['peer_ok_at'] = time.time()           # given its time from the start
        t = threading.Thread(target=_split_loop, args=(daemon,), name='otp-split', daemon=True)
        SPLIT['thread'] = t
    t.start()


def _split_loop(daemon):
    while True:
        try:
            split_step(daemon.store)
        except Exception as e:                          # noqa: BLE001
            log_sparing('split', 'watching the other node: %s' % e, 'warn', every=600)
        time.sleep(SPLIT_STEP_S)


def split_watching():
    """Whether this process runs the watch (the daemon does; a command line does not - it
    reads the daemon's row instead)."""
    t = SPLIT['thread']
    return t is not None and t.is_alive()


def split_state_of(store, name):
    """A node's state: this node's own live where the watch runs here, else its row."""
    if name == node_name() and split_watching():
        return split_state_here()
    return _meta_json(store, 'split:state:' + name) or {}


def split_apart():
    return bool(SPLIT['apart_since']) and split_engaged()


def split_aside():
    return split_engaged() and SPLIT['role'] == 'aside'


def split_step(store, now=None, peer=None, arbiter=None):
    """One look: the other node's database, the arbiter, what this node does. `peer` and
    `arbiter` given only by the tests."""
    now = time.time() if now is None else now
    if not split_engaged():
        if SPLIT['apart_since'] or SPLIT['role'] != 'serve':
            SPLIT.update(apart_since=0.0, role='serve', why='')
            MAINT_CACHE['at'] = 0
        SPLIT['peer_ok_at'] = now
        # Whatever is chosen here (1.0.224): while the question before a code is let in is
        # held off - the other node's database did not answer, 20 s to 5 min - it is asked
        # every 2 s whether it answers again, and the hold is lifted at once. As until now, it
        # waited out its back-off after the link was back: a code used there was let in here
        # again for up to 40 s, until the replication caught up. Nothing is asked otherwise.
        if CONFIG.get('ha_mode') == 'replicated' and CONFIG.get('ha_peer') and \
                ONCE_PEER['down_until'] > time.time():
            p = _split_peer_probe() if peer is None else peer
            if p is True:
                once_peer_forget()
        return
    p = _split_peer_probe() if peer is None else peer
    if p is True:
        SPLIT['peer_ok_at'], SPLIT['peer_err'] = now, ''
        # The other node's database answers: the question before a code is let in is asked
        # again at once - not after its back-off of up to five minutes, while recovery codes
        # would be refused and codes written down as let in unasked.
        if ONCE_PEER['down_until'] > time.time():
            # Its connections from before closed too (1.0.224): one dead with the link put
            # the other node down again at its first use.
            once_peer_forget() if peer is None else ONCE_PEER.update(down_until=0.0, fails=0)
    else:
        SPLIT['peer_err'] = str(p)
    mode = split_mode()
    if arbiter is not None:
        SPLIT.update(arb=[], arb_state=arbiter, arb_at=now)
    elif mode == 'arbiter' or now - SPLIT['arb_at'] > 30:
        got, verdict = split_arbiter_check()
        SPLIT.update(arb=got, arb_state=verdict, arb_at=now)
    after = max(5, int(CONFIG.get('split_after_s') or 20))
    apart = now - SPLIT['peer_ok_at'] > after
    was_apart = bool(SPLIT['apart_since'])
    if apart and not was_apart:
        SPLIT['apart_since'] = SPLIT['peer_ok_at'] or now
        log('ha: the other node\'s database has not answered for %d s (%s) - the nodes are '
            'apart' % (now - SPLIT['peer_ok_at'], SPLIT['peer_err']), 'warn')
        _split_event(store, 'bad', 'the nodes lost each other: the other node\'s database has not '
                     'answered for %d s (%s)' % (now - SPLIT['peer_ok_at'], SPLIT['peer_err']))
    elif not apart and was_apart:
        took = now - SPLIT['apart_since']
        SPLIT.update(apart_since=0.0, together_at=now, report_due=now + 30,
                     last_apart_since=SPLIT['apart_since'])
        # The connections from before closed (1.0.222): the first question on one dead with
        # the link put the other node down for 20 s more, just after it came back - and codes
        # used there meanwhile were let in here again.
        if peer is None:
            once_peer_forget()
        log('ha: the other node\'s database answers again - the nodes are together after %s'
            % human_span(took), 'info')
        _split_event(store, 'good', 'the nodes reach each other again, after %s apart' % human_span(took))
    if p is not True:
        # Known gone (1.0.222): the sign-ins do not wait 1.5 s each to find it out again -
        # one with a NAS's timeout of 1.5 s went to the other node, which had stepped aside.
        # From the first probe that did not answer (1.0.224), not only once apart.
        with ONCE_PEER_LOCK:
            ONCE_PEER['down_until'] = max(ONCE_PEER['down_until'], time.time() + 5)
    preferred = split_me_preferred()
    if mode == 'priority' and apart and not preferred:
        # The preferred node not serving when last heard from (1.0.224) - stepped aside for
        # its clock, or in maintenance: this node goes on, or nobody answers at all.
        why_not = split_preferred_unable(store)
        if why_not:
            preferred = True
    role, why = split_decide(mode, apart, SPLIT['arb_state'], preferred)
    if role != SPLIT['role']:
        SPLIT['role'], SPLIT['why'] = role, why
        MAINT_CACHE['at'] = 0                           # RADIUS and the VIP told at once
        if role == 'aside':
            log('ha: this node steps aside - %s' % why, 'warn')
            _split_event(store, 'bad', 'this node steps aside: %s - RADIUS is answered by the other '
                         'node, the VIP address goes to it' % why)
        else:
            log('ha: this node answers again%s' % (' - ' + why if why else ''), 'info')
            _split_event(store, 'good', 'this node answers again%s' % (' - ' + why if why else ''))
    else:
        SPLIT['why'] = why
    if now - SPLIT['written'] > 10 or apart != was_apart:
        SPLIT['written'] = now
        try:
            store.set_meta('split:state:' + node_name(), json.dumps(split_state_here(now)))
        except Exception:                               # noqa: BLE001
            pass
    if not apart and not SPLIT['report_due'] and now - SPLIT['tidied'] > 600:
        # Codes let in unasked in a short outage, never apart (1.0.224): gone after an hour.
        SPLIT['tidied'] = now
        try:
            for r in store.db.rows("SELECT k, v FROM meta WHERE k LIKE ?",
                                   ('split:took:%s:%%' % node_name(),)):
                try:
                    at = float(json.loads(r['v'] or '{}').get('at') or 0)
                except ValueError:
                    at = 0
                if at < now - 3600:
                    store.db.run('DELETE FROM meta WHERE k = ? AND v = ?', (r['k'], r['v']))
        except Exception:                               # noqa: BLE001
            pass
    if SPLIT['report_due'] and now >= SPLIT['report_due'] and not apart and \
            (peer is not None or split_peer_caught_up(store) or now > SPLIT['report_due'] + 600):
        # Only once the other node's rows are here (1.0.224): made 30 s after, the
        # replication was still catching up and the codes let in on both were not found.
        SPLIT['report_due'] = 0.0
        try:
            split_report(store, now)
        except Exception as e:                          # noqa: BLE001
            log('ha: the report of the time apart could not be made: %s' % e, 'warn')


def split_preferred_unable(store):
    """Why the preferred node is known not to serve, or ''."""
    name = split_preferred_name(store)
    if not name or name == node_name():
        return ''
    try:
        if (clock_state_of(store, name) or {}).get('role') == 'aside':
            return 'the preferred node stepped aside for its clock'
        for n in ha_nodes(store):
            if n['name'] == name and n.get('maintenance'):
                return 'the preferred node is in maintenance'
    except Exception:                                   # noqa: BLE001
        pass
    return ''


def split_peer_caught_up(store):
    """Whether the other node's word written after the nodes found each other again is here
    - its rows written before it came over before it."""
    for n in ha_nodes(store):
        if n.get('me'):
            continue
        st = _meta_json(store, 'split:state:' + n['name']) or {}
        if st and not st.get('apart') and float(st.get('at') or 0) > SPLIT['together_at']:
            return True
    return False


def split_state_here(now=None):
    now = time.time() if now is None else now
    return {'at': now, 'node': node_name(), 'active': split_active(), 'engaged': split_engaged(),
            'mode': split_mode(),
            'apart': split_apart(), 'since': SPLIT['apart_since'],
            'peer_ok_at': SPLIT['peer_ok_at'], 'peer_err': SPLIT['peer_err'],
            'role': SPLIT['role'], 'why': SPLIT['why'], 'preferred': split_me_preferred(),
            'arbiter': SPLIT['arb_state'], 'arbiter_at': SPLIT['arb_at'],
            'arbiters': [{'target': t, 'ok': ok, 'how': how, 'words': w}
                         for t, ok, how, w in SPLIT['arb']],
            'gateway': default_gateway(), 'frozen': split_frozen(),
            'halved': bool(CONFIG.get('split_halve')) and split_apart()}


def _split_event(store, level, words):
    try:
        store.add_event('ha', words, 'warn' if level == 'bad' else 'info', who='otp (split)')
    except Exception:                                   # noqa: BLE001
        pass


# ---- what changes while apart ---------------------------------------------------------------
def split_limit(key):
    """rate_limit_tries / lockout_after as in force now: half (rounded up) while apart, with
    split_halve on - both halves together then allow what one did."""
    v = int(CONFIG.get(key) or 0)
    if v > 0 and CONFIG.get('split_halve') and split_apart():
        return max(1, (v + 1) // 2)
    return v


def split_frozen():
    """Whether changes on the pages wait here: apart, split_freeze on, and this node is not
    the preferred one answering."""
    if not (CONFIG.get('split_freeze') and split_apart()):
        return False
    return SPLIT['role'] == 'aside' or not split_me_preferred()


# The pages' requests that go on while frozen: signing in and out, looking at the cluster,
# the card of this itself (to switch it off), maintenance, restarts, acme's own.
SPLIT_FREE = ('/api/auth/', '/api/split', '/api/ha', '/api/power', '/api/maintenance',
              '/api/acme-push/', '/api/health', '/api/alerts', '/api/logs')


def split_refuses(method, path):
    if method != 'POST' or not split_frozen():
        return ''
    if any(path == p.rstrip('/') or path.startswith(p) for p in SPLIT_FREE):
        return ''
    other = split_preferred_name() or 'the preferred node'
    return ('the two nodes cannot reach each other: changes are made on %s only until they '
            'do (Settings -> High availability -> When the nodes lose each other)' % other)


def split_scratch_refused(store, kind, name, value):
    """With split_scratch on: a recovery code only when the other node can be asked now -
    True means refuse."""
    if not (CONFIG.get('split_scratch') and split_active()):
        return False
    if split_apart():
        return True
    return once_peer_state(store, kind, name, value) is None


def split_took(store, kind, name, k):
    """A code taken while the other node could not be asked: written down for the report."""
    if not (split_engaged() and CONFIG.get('split_report')):
        # Written from the first code the other node could not be asked about (1.0.224: only
        # once apart, the first 20 s were missing); the report takes only those of its own
        # time apart, older ones go.
        return
    try:
        store.set_meta('split:took:%s:%s' % (node_name(), k),
                       json.dumps({'name': str(name)[:190], 'kind': kind, 'at': time.time()}))
    except Exception:                                   # noqa: BLE001
        pass


def split_report(store, now=None):
    """Once together again: what was let in on both halves - the same code, the same
    recovery code, the same answer. Made by the preferred node (both have every row by now)."""
    now = time.time() if now is None else now
    rows = store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'split:took:%'")
    if not rows:
        return None
    if not split_me_preferred():
        return None
    by_key, per_node = {}, {}
    since = float(SPLIT.get('last_apart_since') or 0) - max(5, int(CONFIG.get('split_after_s') or 20)) - 10
    for r in rows:
        parts = r['k'].split(':', 3)
        if len(parts) < 4:
            continue
        node, k = parts[2], parts[3]
        try:
            v = json.loads(r['v'] or '{}')
        except ValueError:
            v = {}
        if float(v.get('at') or 0) < since or str(v.get('name') or '').startswith('#'):
            continue        # a short outage before, or the same code by its token's id
        by_key.setdefault(k, {})[node] = v
        per_node[node] = per_node.get(node, 0) + 1
    twice = []
    for k, nodes in by_key.items():
        if len(nodes) > 1:
            one = list(nodes.values())[0]
            twice.append({'name': one.get('name') or '?', 'kind': one.get('kind') or '?',
                          'nodes': sorted(nodes), 'at': min(float(v.get('at') or 0)
                                                           for v in nodes.values())})
    twice.sort(key=lambda x: x['at'])
    rep = {'at': now, 'taken': per_node, 'twice': twice[:200], 'twice_n': len(twice),
           'since': min((float(v.get('at') or now) for n in by_key.values() for v in n.values()),
                        default=now)}
    store.set_meta('split:report', json.dumps(rep))
    for r in rows:
        store.db.run('DELETE FROM meta WHERE k = ? AND v = ?', (r['k'], r['v']))
    if twice:
        _split_event(store, 'bad', 'while the nodes were apart, %d code(s) were let in on both: %s'
                     % (len(twice), ', '.join('%s (%s)' % (x['name'], x['kind'])
                                              for x in twice[:20])))
    else:
        _split_event(store, 'good', 'while the nodes were apart, %s code(s) were let in without '
                     'the other node asked, none of them twice'
                     % ', '.join('%d on %s' % (v, n) for n, v in sorted(per_node.items())))
    return rep


# ---- the card ----------------------------------------------------------------------------
SPLIT_KEYS = ('split_mode', 'split_prefer', 'split_after_s', 'split_scratch', 'split_halve',
              'split_freeze', 'split_report')


def split_view(store):
    nodes = []
    for n in ha_nodes(store):
        st = split_state_of(store, n['name'])
        if n.get('me') and not st:
            st = split_state_here()
        saved = store.settings_saved()
        nodes.append({'name': n['name'], 'me': bool(n.get('me')), 'alive': bool(n.get('alive')),
                      'state': st, 'arbiter': str(saved.get('split_arbiter@' + n['name'])
                                                  or (CONFIG.get('split_arbiter') if n.get('me') else '')
                                                  or ''),
                      'fresh': bool(st) and time.time() - float(st.get('at') or 0) < 60})
    if not nodes:
        nodes = [{'name': node_name(), 'me': True, 'alive': True, 'state': split_state_here(),
                  'arbiter': str(CONFIG.get('split_arbiter') or ''), 'fresh': True}]
    return {'active': split_active(), 'engaged': split_engaged(), 'ha_mode': CONFIG.get('ha_mode') or '',
            'conf': {k: CONFIG.get(k, DEFAULTS.get(k)) for k in SPLIT_KEYS},
            'preferred': split_preferred_name(store), 'me': node_name(), 'nodes': nodes,
            'report': _meta_json(store, 'split:report')}
