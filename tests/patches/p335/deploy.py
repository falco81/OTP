"""1.0.335 (deploy, OUTDIR): a network change that fails half way on the root side put back; the
VRRP rule of firewalld added without reloading it (runtime bans of fail2ban kept)."""
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
("""    got = subprocess.run(['firewall-cmd', '--permanent',
                          ('--add-rich-rule=' if on else '--remove-rich-rule=') + rule],
                         capture_output=True, text=True)
    rl = subprocess.run(['firewall-cmd', '--reload'], capture_output=True, text=True)
""",
 """    # Kept and in force, each said - no reload (1.0.335): a reload on every change of the pages
    # while the VIP is on threw away what others hold only in force (fail2ban's bans).
    got = subprocess.run(['firewall-cmd', '--permanent',
                          ('--add-rich-rule=' if on else '--remove-rich-rule=') + rule],
                         capture_output=True, text=True)
    rl = subprocess.run(['firewall-cmd', ('--add-rich-rule=' if on else '--remove-rich-rule=') + rule],
                        capture_output=True, text=True)
    if rl.returncode != 0 and ('ALREADY_ENABLED' in (rl.stderr or '') or 'NOT_ENABLED' in (rl.stderr or '')):
        rl = subprocess.CompletedProcess(rl.args, 0, rl.stdout, '')
"""),
("""    run(args, 'nmcli connection modify')
    said.append('NetworkManager: %s - %s via %s, DNS %s%s' % (
""",
 """    run(args, 'nmcli connection modify')
    try:
        return _net_apply_rest(n, said, before, host_was)
    except BaseException:
        # Put back what was changed (1.0.335): /etc/hosts not writable, the reboot not asked -
        # the profile kept the new address with no trial and no reboot, and the next restart (an
        # update) brought the node up where the cluster did not look for it.
        undo = [NMCLI, 'connection', 'modify', n['con']]
        for k in ('ipv4.addresses', 'ipv4.gateway', 'ipv4.dns', 'ipv4.dns-search', 'ipv4.method',
                  'ipv6.addresses', 'ipv6.gateway', 'ipv6.dns', 'ipv6.method'):
            v = before.get(k)
            undo += [k, '' if v in ('--', None) else v]
        try:
            run(undo, 'nmcli connection modify')
        except Exception:                               # noqa: BLE001
            pass
        if n['hostname'] and host_was:
            try:
                run([HOSTNAMECTL, 'set-hostname', host_was], 'hostnamectl set-hostname')
            except Exception:                           # noqa: BLE001
                pass
        if n.get('_hosts_had') is not None:
            try:
                write_root(HOSTS_FILE, n['_hosts_had'], 0o644)
            except Exception:                           # noqa: BLE001
                pass
        raise


def _net_apply_rest(n, said, before, host_was):
    said.append('NetworkManager: %s - %s via %s, DNS %s%s' % (
"""),
("""        write_root(HOSTS_FILE, new, 0o644)
        said.append('%s: this machine\\'s lines' % HOSTS_FILE)
""",
 """        n['_hosts_had'] = had
        write_root(HOSTS_FILE, new, 0o644)
        said.append('%s: this machine\\'s lines' % HOSTS_FILE)
"""),
])
