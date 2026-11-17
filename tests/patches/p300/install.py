# 1.0.300: otp's module - the programs the daemon runs under NoNewPrivileges; an uninstall takes
# otp's local module (otp_local) away too.   python3 install.py OUTDIR
import sys
D = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(D + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(D + f, 'w').write(s)


edit('install.sh', [
("""        run semodule -r otp_server 2>/dev/null || warn "SELinux: semodule -r otp_server did not go"
""",
 """        run semodule -r otp_server 2>/dev/null || warn "SELinux: semodule -r otp_server did not go"
    fi
    # otp's local rules too (1.0.300): put in from Settings → High security → SELinux.
    if command -v semodule >/dev/null 2>&1 && semodule -l 2>/dev/null | awk '$1=="otp_local"{f=1} END{exit !f}'; then
        run semodule -r otp_local 2>/dev/null || warn "SELinux: semodule -r otp_local did not go"
"""),
])
s = open(D + 'deploy/otp_server.cil').read()
assert 'nnp_transition' not in s
s = s.rstrip('\n') + """

; otp.service runs with NoNewPrivileges=yes (1.0.300). A program the daemon runs that has a domain of
; its own is started in it by a transition - which NoNewPrivileges forbids unless the policy says
; the transition may go (nnp_transition): under enforcing it would not run at all. The daemon runs
; hostname (the node's name), ip (the network on Settings → Network), ssh-keygen (SSH keys, the
; backups' host keys), ssh, scp and sftp (backups to SFTP/SCP), ping (the nodes apart) - and chronyc
; where a newer daemon reads the clock with it. Only the transition, only into these domains, each in
; a block of its own: a policy without one of the types still takes the rest.
(optional otp_server_nnp_hostname
    (allow unconfined_service_t hostname_t (process2 (nnp_transition nosuid_transition))))
(optional otp_server_nnp_ifconfig
    (allow unconfined_service_t ifconfig_t (process2 (nnp_transition nosuid_transition))))
(optional otp_server_nnp_ssh_keygen
    (allow unconfined_service_t ssh_keygen_t (process2 (nnp_transition nosuid_transition))))
(optional otp_server_nnp_ssh
    (allow unconfined_service_t ssh_t (process2 (nnp_transition nosuid_transition))))
(optional otp_server_nnp_ping
    (allow unconfined_service_t ping_t (process2 (nnp_transition nosuid_transition))))
(optional otp_server_nnp_chronyc
    (allow unconfined_service_t chronyc_t (process2 (nnp_transition nosuid_transition))))
"""
open(D + 'deploy/otp_server.cil', 'w').write(s)
print('ok')
