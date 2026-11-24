"""1.0.327 (deploy, OUTDIR): the system's list of trusted authorities made again until its tool
ran through; MariaDB's TLS files in a folder MariaDB reaches, and MariaDB started again when it
was put back; the database agent and MariaDB of a new database server on IPv6 as well."""
import sys, pathlib
OUT = pathlib.Path(sys.argv[1])


def edit(path, pairs):
    p = pathlib.Path(path)
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (str(p), n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit(OUT / 'deploy/otp_web.py', [
("""    tool_said = ''
    if not changed and not force and want:
""",
 """    tool_said = ''
    # The tool's run before did not end well (1.0.327): a certificate taken away stayed in the
    # system's list - the files as wanted, nothing "changed", and the pages said it was done.
    pending = os.path.join(ROOT_STATE_DIR, OSROOTS_PENDING)
    if not changed and os.path.exists(pending):
        said.append('the system\\'s list was not made again the last time - made now')
        changed = True
    if not changed and not force and want:
"""),
("""        got = subprocess.run(w['tool'], capture_output=True, text=True, timeout=300)
        if got.returncode != 0:
            raise Refused('%s ended with %d: %s' % (' '.join(w['tool']), got.returncode,
                                                    ((got.stderr or got.stdout).strip() or '-')[-300:]))
        tool_said = ' '.join(w['tool'])
""",
 """        root_state_write(OSROOTS_PENDING, '%d\\n' % int(time.time()))
        got = subprocess.run(w['tool'], capture_output=True, text=True, timeout=300)
        if got.returncode != 0:
            raise Refused('%s ended with %d: %s' % (' '.join(w['tool']), got.returncode,
                                                    ((got.stderr or got.stdout).strip() or '-')[-300:]))
        try:
            os.unlink(pending)
        except OSError:
            pass
        tool_said = ' '.join(w['tool'])
"""),
("""def osroots_sync(w, certs, force=False):
""",
 """OSROOTS_PENDING = 'osroots-pending'


def osroots_sync(w, certs, force=False):
"""),
])

edit(OUT / 'deploy/otp_pg_ops.py', [
("""    folder = str(conf.get('my_tls_dir') or '/etc/otp-db-agent/mariadb')
    os.makedirs(folder, mode=0o750, exist_ok=True)
""",
 """    cnf_dir = _my_cnf_dir(conf)
    cnf = os.path.join(cnf_dir, MY_CNF_NAME)
    try:
        cnf_was = W.pg_file_read(cnf)
    except (OSError, Refused):
        cnf_was = None
    # A folder MariaDB reaches (1.0.327): /etc/otp-db-agent is root's alone (0700), and the one
    # in it was made 0700 by the agent's umask - MariaDB started without TLS, every try put it
    # back with one restart more. One a hand made work with the old folder keeps it.
    old = '/etc/otp-db-agent/mariadb'
    folder = str(conf.get('my_tls_dir') or (old if cnf_was and (old + '/') in cnf_was
                                            else '/etc/otp-db-agent-mariadb'))
    os.makedirs(folder, mode=0o750, exist_ok=True)
    os.chmod(folder, 0o750)
"""),
("""    cnf_dir = _my_cnf_dir(conf)
    cnf = os.path.join(cnf_dir, MY_CNF_NAME)
    body = ('# written by otp-db-agent""",
 """    body = ('# written by otp-db-agent"""),
("""    try:
        cnf_was = W.pg_file_read(cnf)
    except (OSError, Refused):
        cnf_was = None
    how = ''
    try:
""",
 """    how = ''
    restarted = []
    try:
"""),
("""            W.write_root(cnf, body, 0o644)
            how = op_my_restart({}, conf)['said']
""",
 """            W.write_root(cnf, body, 0o644)
            restarted.append(1)
            how = op_my_restart({}, conf)['said']
"""),
("""        else:
            W.write_root(cnf, cnf_was, 0o644)
        raise
""",
 """        else:
            W.write_root(cnf, cnf_was, 0o644)
        if restarted:
            # Started again with what it had (1.0.327): left as the failed start left it.
            try:
                op_my_restart({}, conf)
            except Exception:                           # noqa: BLE001
                pass
        raise
"""),
])

edit(OUT / 'deploy/otp_db_agent.py', [
("""    fam = socket.AF_INET6 if ':' in c['listen'] else socket.AF_INET
    s = socket.socket(fam, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((c['listen'], int(c['port'])))
    s.listen(128)
    return s
""",
 """    fam = socket.AF_INET6 if ':' in c['listen'] else socket.AF_INET
    s = None
    try:
        s = socket.socket(fam, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if fam == socket.AF_INET6 and c['listen'] == '::':
            # IPv4 and IPv6 both (1.0.327): an otp node on IPv6 was taken but got no answer.
            try:
                s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except OSError:
                pass
        s.bind((c['listen'], int(c['port'])))
    except OSError:
        if c['listen'] != '::':
            raise
        # A machine without IPv6 (no AF_INET6 at all, or no address): IPv4 alone, as before.
        if s is not None:
            s.close()
        c['listen'] = '0.0.0.0'
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((c['listen'], int(c['port'])))
    s.listen(128)
    return s
"""),
])

edit(OUT / 'deploy/db-server.sh', [
("""c = {'listen': '0.0.0.0', 'port': aport, 'engine': eng, 'user': 'otp-db-agent',
""",
 """import socket
try:                                    # IPv6 too where the machine has it (1.0.327)
    _s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM); _s.bind(('::', 0)); _s.close(); lis = '::'
except OSError:
    lis = '0.0.0.0'
c = {'listen': lis, 'port': aport, 'engine': eng, 'user': 'otp-db-agent',
"""),
("""        printf '# written by install.sh --db-server mariadb (otp)\\n[mariadb]\\nbind-address = 0.0.0.0\\n' | write_file "$cnf" 0644
""",
 """        # IPv6 too where the machine has it (1.0.327): an otp node on IPv6 got no answer.
        bind=0.0.0.0
        python3 -I -c 'import socket; s = socket.socket(socket.AF_INET6); s.bind(("::", 0))' 2>/dev/null && bind=::
        printf '# written by install.sh --db-server mariadb (otp)\\n[mariadb]\\nbind-address = %s\\n' "$bind" | write_file "$cnf" 0644
"""),
])
