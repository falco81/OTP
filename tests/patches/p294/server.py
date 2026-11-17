# 1.0.294: bug fixes - the RADIUS test against a server it cannot reach (400, not 500), a /32
# range in the list search, the test's link to a log row only for this machine.
#   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('40_radius_proto.py', [
("""    family = socket.AF_INET6 if ':' in str(server) else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.settimeout(float(timeout))
    began = time.time()
    try:
        bad = False
""", """    family = socket.AF_INET6 if ':' in str(server) else socket.AF_INET
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise RadiusError('the port is a number')
    if not 0 < port < 65536:
        raise RadiusError('the port is 1 to 65535')
    try:
        sock = socket.socket(family, socket.SOCK_DGRAM)
    except OSError as e:
        raise RadiusError('cannot ask %s:%s: %s' % (server, port, e))
    sock.settimeout(float(timeout))
    began = time.time()
    try:
        bad = False
"""),
("""        for _ in range(max(1, int(tries))):
            sock.sendto(data, (server, int(port)))
""", """        for _ in range(max(1, int(tries))):
            # A name that does not resolve, or no route to it (1.0.294): said as the answer, it
            # was an error of the page.
            try:
                sock.sendto(data, (server, port))
            except OSError as e:
                raise RadiusError('cannot reach %s:%s: %s' % (server, port, e))
"""),
("""                try:
                    got, src = sock.recvfrom(4096)
                except socket.timeout:
                    break
""", """                try:
                    got, src = sock.recvfrom(4096)
                except socket.timeout:
                    break
                except OSError as e:
                    # An ICMP "port unreachable" comes back as a refusal (1.0.294).
                    raise RadiusError('%s:%s refused it: %s' % (server, port, e))
"""),
])

edit('90_api.py', [
("""    row = store.db.row("SELECT id FROM radius_log WHERE username = ? ORDER BY id DESC "
                       "LIMIT 1", (Authenticator.full_name(
                           user, (store.client_for('127.0.0.1') or {}).get('realm', '')),))
""", """    # The row of the log only for a test of this machine (1.0.294): another server's answer is
    # in that server's log, and the newest row of the name here was some other request.
    row = store.db.row("SELECT id FROM radius_log WHERE username = ? ORDER BY id DESC "
                       "LIMIT 1", (Authenticator.full_name(
                           user, (store.client_for('127.0.0.1') or {}).get('realm', '')),)) \\
        if server in ('127.0.0.1', '::1', 'localhost') else None
"""),
])

edit('50_storage.py', [
("""            if net.version == 4 and net.prefixlen % 8 == 0:
                keep =""", """            if net.version == 4 and net.prefixlen == 32:
                # One address (1.0.294): its pattern was "a.b.c.d.%" and found nothing.
                one = str(net.network_address)
                c = "LOWER(COALESCE(%s, ''))" % col
                return ("(%s = ? OR %s LIKE ? ESCAPE '!')" % (c, c), [one, like_pattern(one) + ':%'])
            if net.version == 4 and net.prefixlen % 8 == 0:
                keep ="""),
])
print('ok')

edit('50_storage.py', [
("""    TOKEN_SORTS = {'name': 'name', 'created': 'created', 'last_used': 'last_used',
                   'state': 'state', 'failures': 'failures', 'scratch_left': 'scratch_left'}""",
 """    TOKEN_SORTS = {'name': 'name', 'created': 'created', 'last_used': 'last_used',
                   'state': 'state', 'failures': 'failures', 'scratch_left': 'scratch_left',
                   'locked_until': 'locked_until'}   # 1.0.294: the quick view's locked ones"""),
])
print('ok2')

edit('90d_dbagent.py', [
("""def db_agent_call(op, args=None, timeout=90, conf=None, _ack=True):""",
 """def db_agent_call(op, args=None, timeout=90, conf=None, _ack=True, retry=True):"""),
("""            if attempt == 0 and (op in ('status', 'load') or isinstance(e, DbAgentNotSent)):""",
 """            if attempt == 0 and retry and (op in ('status', 'load') or
                                           isinstance(e, DbAgentNotSent)):"""),
("""def db_agent_load(fresh=False, timeout=10):
    \"\"\"This node's database server, in the shape of server_load() (and its database's own).\"\"\"
    now = time.time()
    if not fresh and DBAGENT_STATE['load'] and now - DBAGENT_STATE['load_at'] < 2.5:
        return DBAGENT_STATE['load']
    got = db_agent_call('load', {'db': CONFIG.get('db_name') or 'otp'}, timeout=timeout)""",
 """def db_agent_load(fresh=False, timeout=10, retry=True):
    \"\"\"This node's database server, in the shape of server_load() (and its database's own).\"\"\"
    now = time.time()
    if not fresh and DBAGENT_STATE['load'] and now - DBAGENT_STATE['load_at'] < 2.5:
        return DBAGENT_STATE['load']
    got = db_agent_call('load', {'db': CONFIG.get('db_name') or 'otp'}, timeout=timeout,
                        retry=retry)"""),
("""            try:
                v = dict(db_agent_load(timeout=4))
            except ValueError as e:
                DBAGENT_STATE.update(load_fail_at=now, load_said=str(e)[:200])""",
 """            try:
                # Once, not tried again (1.0.294): the meter waited 4 + 1.5 + 4 s, and the pause
                # counted from before it was spent; it counts from the failure now.
                v = dict(db_agent_load(timeout=4, retry=False))
            except ValueError as e:
                DBAGENT_STATE.update(load_fail_at=time.time(), load_said=str(e)[:200])"""),
("""    if addr:
        m = re.fullmatch(r'\\[?([^\\]]+?)\\]?(?::(\\d{1,5}))?', str(addr).strip())
        if not m:
            raise ValueError('the agent\\'s address is HOST or HOST:PORT')
        host, port = m.group(1), int(m.group(2) or port)""",
 """    if addr:
        a = str(addr).strip()
        if a.count(':') > 1 and not a.startswith('['):
            # A bare IPv6 address (1.0.294): its last group was taken for the port.
            host = a
        else:
            m = re.fullmatch(r'\\[?([^\\]]+?)\\]?(?::(\\d{1,5}))?', a)
            if not m:
                raise ValueError('the agent\\'s address is HOST or HOST:PORT')
            host, port = m.group(1), int(m.group(2) or port)"""),
])
print('ok3')
