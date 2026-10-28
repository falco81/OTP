# ---- RADIUS: guessing from one place held back (1.0.137) -----------------------------
# Every token counts its own wrong codes and locks itself (lockout_after), and
# that is all there was: from one place - one address behind the VPN - a
# guesser could try every user's code a few times a day, or lock every token
# out on purpose. Switched on (radius_guard), the place each request comes
# from is counted too: the Calling-Station-Id the VPN sends (the address the
# person connects from; a MAC address on Wi-Fi). Too many refusals from one
# place in the window - or too many different names refused from it - and the
# place is blocked for a while: its requests are refused at once, nothing of
# them checked, so they neither guess further nor count against anybody's
# token. Counted in each node's memory, as the pages' sign-ins are, and shown
# with them (Settings - Sign-in protection), each cleared by hand or all.
GUARD_KIND = 'radius-src'
# Refusals that are this server's trouble, not somebody's guess: never counted.
GUARD_NOT_GUESSES = ('gone away', 'could not decide', 'cannot be built', 'is not set up',
                     'cannot be sent', 'does not decode', 'too many codes sent',
                     'has no directory', 'nowhere to send', 'too many answers at once',
                     'longer than a RADIUS packet', 'no realm takes', 'may not use the realm',
                     'carries no', 'already been used')


def guard_on():
    return bool(CONFIG.get('radius_guard'))


def guard_source(w):
    """Where a request comes from, as the VPN says it: an address (IPv6 by its
    /64 - one machine's to choose from), or what else it sends (a MAC)."""
    raw = str((w or {}).get('Calling-Station-Id') or '').strip()
    if not raw:
        return ''
    # An address with its port (1.0.139): 203.0.113.5:51234 or [2001:db8::5]:51234
    # was a new place at every connection, and never blocked.
    m = re.match(r'^\[([^\]]+)\](?::\d+)?\Z', raw) or \
        re.match(r'^(\d{1,3}(?:\.\d{1,3}){3}):\d+\Z', raw)
    if m:
        raw = m.group(1)
    try:
        a = ipaddress.ip_address(raw.split('%')[0].strip('[]'))
        if a.version == 6:
            if a.ipv4_mapped:
                return str(a.ipv4_mapped)
            return str(ipaddress.ip_network('%s/64' % a, strict=False))
        return str(a)
    except ValueError:
        return re.sub(r'[^0-9A-Za-z:._-]', '', raw).lower()[:64]


def guard_trusted(src):
    """A place never blocked: radius_guard_trusted (an office behind one
    address, a monitor that signs in)."""
    raw = str(CONFIG.get('radius_guard_trusted') or '')
    if not raw.strip() or not src:
        return False
    try:
        a = ipaddress.ip_network(src, strict=False)
    except ValueError:
        return src in [x.strip().lower() for x in re.split(r'[\s,;]+', raw) if x.strip()]
    for x in re.split(r'[\s,;]+', raw):
        if not x.strip():
            continue
        try:
            net = ipaddress.ip_network(x.strip(), strict=False)
        except ValueError:
            continue
        if net.version == a.version and a.prefixlen >= net.prefixlen and a.subnet_of(net):
            return True
    return False


def guard_blocked(daemon, src):
    """(until, why) while the place is blocked, else None."""
    if not src:
        return None
    info = daemon.login_info.get((GUARD_KIND, src))
    if not info:
        return None
    until = float(info.get('blocked_until') or 0)
    if until > time.time():
        return until, info.get('blocked_why') or 'too many wrong sign-ins'
    return None


def guard_is_guess(d):
    if d.result != 'reject':
        return False
    reason = str(d.reason or '')
    return not any(w in reason for w in GUARD_NOT_GUESSES)


def guard_count(daemon, src, name):
    """One refusal from `src` for `name`: counted; blocked at the limit."""
    t = time.time()
    tries = int(CONFIG.get('radius_guard_tries') or 20)
    nlimit = int(CONFIG.get('radius_guard_names') or 0)
    span = 60 * int(CONFIG.get('radius_guard_window_min') or 15)
    block = 60 * int(CONFIG.get('radius_guard_block_min') or 30)
    key = (GUARD_KIND, src)
    name = str(name or '').strip().lower()[:120]
    newly = None
    with ApiHandler.THROTTLE_LOCK:
        fails = [x for x in daemon.login_fails[key] if t - x < span] + [t]
        # Kept to the limits set (1.0.139): tries up to 10000, names up to 1000.
        daemon.login_fails[key] = fails[-max(1000, tries):]
        info = daemon.login_info.setdefault(key, {'others': []})
        names = {n: ts for n, ts in (info.get('names') or {}).items() if t - ts < span}
        if name:
            names[name] = t
            cap = max(500, nlimit)
            if len(names) > cap:
                names = dict(sorted(names.items(), key=lambda kv: kv[1])[-cap:])
            others = [x for x in info.get('others') or [] if x != name]
            info['others'] = (others + [name])[-6:]
        info.update(limit=tries, span=span, what='wrong sign-ins', at=t, names=names,
                    names_limit=nlimit, guard=True)
        if float(info.get('blocked_until') or 0) <= t:
            why = None
            if len(fails) >= tries:
                why = '%d wrong sign-ins in %d min' % (len(fails), span // 60)
            elif nlimit and len(names) >= nlimit:
                why = '%d different names refused in %d min' % (len(names), span // 60)
            if why:
                info['blocked_until'] = t + block
                info['blocked_why'] = why
                info['blocked_at'] = t
                newly = why
    if newly:
        try:
            daemon.store.add_event('radius', '%s is blocked for %d min - %s; the names: %s'
                                   % (src, block // 60, newly, ', '.join(
                                       (daemon.login_info.get(key) or {}).get('others') or [])),
                                   'warn')
        except Exception:                               # noqa: BLE001
            pass
        LOCKOUTS_SENT['sig'] = None


def guard_left(until):
    left = max(0, int(until - time.time()))
    return '%d min' % ((left + 59) // 60) if left >= 60 else '%d s' % left
