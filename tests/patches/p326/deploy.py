"""1.0.326 (deploy, OUTDIR): otp's SELinux rule never written off while semodule does not answer;
a host name of more than 64 characters refused before anything is touched; a restart said needed
only when dnf says so; the database agent takes over no role that is a member of another."""
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
("""    if not rules:
        if se_local_in():
            got = _se_run(['semodule', '-r', SE_LOCAL], 300)
""",
 """    if not rules:
        loaded = se_local_in()
        if loaded is None:
            # Not known (1.0.326): its store held by dnf, semodule -l failed - taken as not loaded,
            # the list was emptied and the rule stayed in the policy, never to be taken out.
            raise Refused('semodule -l did not answer (its store busy - an update?): nothing was '
                          'taken out - try again in a moment')
        if loaded:
            got = _se_run(['semodule', '-r', SE_LOCAL], 300)
"""),
("""        raise Refused('the host name is the whole name: otp1.example.cz')
    out['hostname'] = host
""",
 """        raise Refused('the host name is the whole name: otp1.example.cz')
    if host and len(host) > 64 and host != net_static_hostname():
        # As hostnamectl takes it (1.0.326): refused by it after nmcli had changed the profile -
        # the new address came at the next restart, whatever it was for.
        raise Refused('the host name is the whole name, 64 characters at most')
    out['hostname'] = host
"""),
("""        if nr.returncode == 1 and say:
            say(nr.stdout.strip().splitlines()[0] if nr.stdout.strip() else 'a restart is needed')
        return nr.returncode == 1
""",
 """        # Said by dnf (1.0.326): without dnf-plugins-core the command is not there, exits 1 - and
        # every node was restarted after every update.
        needed = nr.returncode == 1 and 'reboot' in (nr.stdout or '').lower()
        if needed and say:
            say(nr.stdout.strip().splitlines()[0] if nr.stdout.strip() else 'a restart is needed')
        return needed
"""),
])

edit(OUT / 'deploy/otp_pg_ops.py', [
("""        raise Refused('the account %s is there with rights over the whole server - not taken '
                      'over; choose another name' % user)
""",
 """        raise Refused('the account %s is there with rights over the whole server - not taken '
                      'over; choose another name' % user)
    # Nor one given the rights of another role (1.0.326): pg_execute_server_program, the
    # reading of files or of every database - a node would run programs as postgres.
    if have and sql(conf, "SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member "
                    "JOIN pg_roles g ON g.oid = m.roleid WHERE r.rolname = %s AND "
                    "g.rolname <> 'pg_create_subscription' LIMIT 1" % W.pg_lit(user)) == '1':
        raise Refused('the account %s is there as a member of other roles - not taken over; '
                      'choose another name' % user)
"""),
])
