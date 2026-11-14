#!/usr/bin/python3
"""Round 3 (ops) patch of deploy/otp_web.py (1.0.262), separate from the HA one (r3_otpweb_patch.py):
A. the balancer's own port on an SELinux node: labelled http_port_t before nginx is given it (unless
   http_port_t / http_cache_port_t has it already), refused with a clear message on an enforcing node
   when it cannot be; nginx's reload checked, and the port looked at after it - not listened on, the
   files are put back, nginx reloaded again, and it is said as refused, not done.
B. se_want_checked: a port type the helper does not know is left out with a line in what is said,
   not a refusal of the whole request (the booleans and the other ports with it).
    python3 r3_ops_otpweb_patch.py [path/to/otp_web.py]"""
import sys
path = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/build/out/otp-1.0.262/deploy/otp_web.py'
s = open(path).read()
if 'def lbport_selinux(port' in s:
    print('already patched')
    sys.exit(0)
EDITS = []

# ---- A1: the helpers, before nginx_part --------------------------------------------------------
EDITS.append(("""def nginx_part(r, last):
    \"\"\"This node's server and the web address's, with their TLS.\"\"\"
""", """def lbport_selinux(port):
    \"\"\"The balancer's own port let to nginx where SELinux is on (1.0.262), or Refused on an
    enforcing node where it cannot be: written without it, nginx could not bind it - reloaded,
    the port stayed shut; restarted (an upgrade), nginx did not start at all. A port http_port_t
    or http_cache_port_t has already is left as it is.\"\"\"
    mode = se_mode()
    if mode in ('absent', 'Disabled'):
        return ''
    enforcing = mode == 'Enforcing'
    known = se_ports()
    if known is None:
        if enforcing:
            raise Refused('SELinux is enforcing and semanage is not on this machine, so nginx '
                          'cannot be let listen on the balancer\\'s port %d (dnf install '
                          'policycoreutils-python-utils)' % port)
        return ''
    if se_port_has(known, 'http_port_t', 'tcp', port) or \\
            se_port_has(known, 'http_cache_port_t', 'tcp', port):
        return ''
    got = _se_run(['semanage', 'port', '-a', '-t', 'http_port_t', '-p', 'tcp', str(port)], 300)
    if got is not None and got.returncode == 0:
        return 'SELinux lets nginx listen on the balancer\\'s port %d' % port
    if got is not None and 'already defined' in (got.stderr or ''):
        why = ('port %d/tcp is another service\\'s in the SELinux policy - choose another port for '
               'the balancer (web_proxy_port)' % port)
    else:
        why = 'semanage port %d/tcp: %s' % (port, ((got.stderr or '') if got else '').strip()[-200:])
    if enforcing:
        raise Refused(why)
    return 'SELinux (permissive): %s' % why


def lbport_listening(port, wait=5.0):
    \"\"\"nginx answers on the balancer's own port (a TCP connect to 127.0.0.1 - it listens on
    every address), `wait` seconds at most.\"\"\"
    import socket
    end = time.time() + wait
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            if s.connect_ex(('127.0.0.1', int(port))) == 0:
                return True
        except OSError:
            pass
        finally:
            s.close()
        if time.time() >= end:
            return False
        time.sleep(0.25)


def nginx_part(r, last):
    \"\"\"This node's server and the web address's, with their TLS.\"\"\"
"""))

# ---- A2: the port labelled before the file is written; looked at when it is not listened on ----
EDITS.append(("""        lp = r.get('lbport')
        if lp is not None and lp.get('port'):
            text = LB_HEAD + lbport_server(main[:where[0]] + block + main[where[1]:], lp)
            if snap.get(NGINX_LB) is None or snap[NGINX_LB][0].decode() != text:
                write_root(NGINX_LB, text, 0o644)
                changed = True
                said.append('nginx: the balancer\\'s own port %d - the enrolment pages only, for %s%s'
                            % (lp['port'], ', '.join(lp['from']),
                               ' (the PROXY protocol)' if lp['header'] == 'proxy_protocol' else ''))
""", """        lp = r.get('lbport')
        lb_look = 0
        if lp is not None and lp.get('port'):
            text = LB_HEAD + lbport_server(main[:where[0]] + block + main[where[1]:], lp)
            if snap.get(NGINX_LB) is None or snap[NGINX_LB][0].decode() != text:
                # Let to nginx by SELinux first (1.0.262), or refused before anything is written.
                w = lbport_selinux(int(lp['port']))
                if w:
                    said.append(w)
                write_root(NGINX_LB, text, 0o644)
                changed = True
                lb_look = int(lp['port'])
                said.append('nginx: the balancer\\'s own port %d - the enrolment pages only, for %s%s'
                            % (lp['port'], ', '.join(lp['from']),
                               ' (the PROXY protocol)' if lp['header'] == 'proxy_protocol' else ''))
            elif not NO_SERVICES and not lbport_listening(int(lp['port']), 0):
                # Written by 1.0.259-1.0.261 without its label: nginx never listened there.
                w = lbport_selinux(int(lp['port']))
                if w:
                    said.append(w)
                    changed = True
                    lb_look = int(lp['port'])
"""))

# ---- A3: the reload checked, and the port after it ----------------------------------------------
EDITS.append(("""            subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True)
            said.append('nginx reloaded')
    except BaseException:
        put_back(snap)
        raise
    return said, dh
""", """            rl = subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True, text=True)
            if rl.returncode != 0:
                # Said, not "reloaded" (1.0.262): the files put back (nginx runs what it ran).
                raise Refused('nginx could not be reloaded, so it is as it was: %s'
                              % (((rl.stderr or '').strip().splitlines() or ['?'])[-1][:300]))
            said.append('nginx reloaded')
            if lb_look and not lbport_listening(lb_look):
                # Reloaded, and the balancer's port still shut (SELinux, another program on it):
                # everything put back and nginx read again - refused, not "done".
                put_back(snap)
                subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True)
                raise Refused('nginx does not listen on the balancer\\'s port %d after the reload '
                              '(SELinux: ausearch -m avc -ts recent; or another program has it) - '
                              'nginx is as it was' % lb_look)
    except BaseException:
        put_back(snap)
        raise
    return said, dh
"""))

# ---- B: a port type not known is left out, said -------------------------------------------------
EDITS.append(("""def se_want_checked(r):
    \"\"\"What the daemon says otp needs here: booleans and ports, checked against what may be.\"\"\"
""", """def se_want_checked(r, left_out=None):
    \"\"\"What the daemon says otp needs here: booleans and ports, checked against what may be.
    left_out (1.0.262): a list a port of a type this helper does not set is said in and left
    out - a newer daemon's need refused the whole request, the booleans and the other ports too.\"\"\"
"""))
EDITS.append(("""    for p in (r.get('ports') or [])[:16]:
        if not isinstance(p, dict) or p.get('type') not in SE_PORT_TYPES or \\
                p.get('proto') not in ('tcp', 'udp'):
            raise Refused('a port type otp does not set')
""", """    for p in (r.get('ports') or [])[:16]:
        if left_out is not None and isinstance(p, dict) and p.get('proto') in ('tcp', 'udp') and \\
                p.get('type') not in SE_PORT_TYPES and \\
                re.match(r'^[a-z][a-z0-9_]{0,40}_port_t\\Z', str(p.get('type') or '')):
            left_out.append('port %s/%s (%s) left out: this helper does not set %s - install.sh of '
                            'the daemon\\'s version puts in one that does'
                            % (str(p.get('port'))[:6], p['proto'], str(p.get('why') or '')[:80],
                               p['type']))
            continue
        if not isinstance(p, dict) or p.get('type') not in SE_PORT_TYPES or \\
                p.get('proto') not in ('tcp', 'udp'):
            raise Refused('a port type otp does not set')
"""))
EDITS.append(("""def se_check(r):
    bools, ports = se_want_checked(r)
""", """def se_check(r):
    left = []
    bools, ports = se_want_checked(r, left)
"""))
EDITS.append(("""           'denials': {'tool': False, 'total': 0, 'groups': []}, 'problems': []}
    if mode == 'absent':""", """           'denials': {'tool': False, 'total': 0, 'groups': []}, 'problems': [],
           'left_out': left}
    if mode == 'absent':"""))
EDITS.append(("""def se_do(r):
    do = r.get('do')
    bools, ports = se_want_checked(r)
    said = []
""", """def se_do(r):
    do = r.get('do')
    left = []
    bools, ports = se_want_checked(r, left)
    said = list(left)
"""))

for old, new in EDITS:
    n = s.count(old)
    assert n == 1, 'not found exactly once (%d): %r' % (n, old[:120])
    s = s.replace(old, new)
compile(s, path, 'exec')
open(path, 'w').write(s)
print('patched', path)
