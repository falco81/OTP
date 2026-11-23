"""1.0.318 (parts): a remote backup cut off on the way never kept under a backup's name, its half
file taken away; a folder name past UTF-8 no longer fails every backup over SSH; the other node's old
address taken out of pg_hba until it is; a firewall trial put back each time it runs out; the lockout
list's limit as in force; the balancer's settings reach nginx alone; a VIP interface name as root takes it."""
import sys, pathlib
P = pathlib.Path(sys.argv[1])


def edit(name, pairs):
    p = P / name
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (name, n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit('86b_rbackup.py', [
# FTP: the half file away when the upload broke off
("""    def put(self, local, name):
        with open(local, 'rb') as f:
            self.ftp.storbinary('STOR .%s.part' % name, f, blocksize=262144)
        try:
            self.ftp.delete(name)
        except ftplib.error_perm:
            pass
        self.ftp.rename('.%s.part' % name, name)
""",
 """    def put(self, local, name):
        try:
            with open(local, 'rb') as f:
                self.ftp.storbinary('STOR .%s.part' % name, f, blocksize=262144)
        except BaseException:
            # The half file taken away (1.0.318): under a name no clean-up knows, each one left
            # filled the destination until every backup failed.
            try:
                self.ftp.delete('.%s.part' % name)
            except Exception:                           # noqa: BLE001
                pass
            raise
        try:
            self.ftp.delete(name)
        except ftplib.error_perm:
            pass
        self.ftp.rename('.%s.part' % name, name)
"""),
# SSH: names past UTF-8 in the folder
("""    def _run(self, args, what, stdin=None, timeout=3600):
        got = subprocess.run(rb_capped_argv(args), input=stdin, capture_output=True, text=True,
                             timeout=timeout, env=self.env, start_new_session=True)
""",
 """    def _run(self, args, what, stdin=None, timeout=3600):
        # Not UTF-8 read as such (1.0.318): one file of another encoding in the folder had ls fail
        # every backup there, after it was sent and before the clean-up.
        got = subprocess.run(rb_capped_argv(args), input=stdin, capture_output=True, text=True,
                             encoding='utf-8', errors='replace',
                             timeout=timeout, env=self.env, start_new_session=True)
"""),
# SFTP / SCP: the half file away
("""    def put(self, local, name):
        name = rb_safe_name(name)
        if self.t['kind'] == 'sftp':
            self._sftp(['cd "%s"' % self.dir, 'put "%s" ".%s.part"' % (local, name),
                        '-rm "%s"' % name, 'rename ".%s.part" "%s"' % (name, name)])
        else:
            self._run(['scp'] + self.opts + ['-P', str(int(self.t['port'])), '-q', local,
                                             '%s:%s/.%s.part' % (self.rdest, self.dir, name)],
                      'scp')
            self._ssh('mv -f -- %s %s' % (shlex_quote('%s/.%s.part' % (self.dir, name)),
                                          shlex_quote('%s/%s' % (self.dir, name))))
""",
 """    def put(self, local, name):
        name = rb_safe_name(name)
        try:
            if self.t['kind'] == 'sftp':
                self._sftp(['cd "%s"' % self.dir, 'put "%s" ".%s.part"' % (local, name),
                            '-rm "%s"' % name, 'rename ".%s.part" "%s"' % (name, name)])
            else:
                self._run(['scp'] + self.opts + ['-P', str(int(self.t['port'])), '-q', local,
                                                 '%s:%s/.%s.part' % (self.rdest, self.dir, name)],
                          'scp')
                self._ssh('mv -f -- %s %s' % (shlex_quote('%s/.%s.part' % (self.dir, name)),
                                              shlex_quote('%s/%s' % (self.dir, name))))
        except BaseException:
            # The half file taken away (1.0.318), as the folder's is.
            try:
                if self.t['kind'] == 'sftp':
                    self._sftp(['cd "%s"' % self.dir, '-rm ".%s.part"' % name], timeout=120)
                else:
                    self._ssh('rm -f -- %s' % shlex_quote('%s/.%s.part' % (self.dir, name)))
            except Exception:                           # noqa: BLE001
                pass
            raise
"""),
# SMB: put alone first - smbclient goes on after a failed command
("""    def put(self, local, name):
        name = rb_safe_name(name)
        self._run([self._cd(), 'put "%s" ".%s.part"' % (local, name), 'del "%s"' % name,
                   'rename ".%s.part" "%s"' % (name, name)], ignore=('NT_STATUS_NO_SUCH_FILE',
                                                                   'NT_STATUS_OBJECT_NAME_NOT_FOUND'))
""",
 """    def put(self, local, name):
        name = rb_safe_name(name)
        # The put by itself first (1.0.318): smbclient goes on after a command that failed, and a
        # copy cut off by a full share was renamed to a backup's name - kept, offered to put back.
        try:
            self._run([self._cd(), 'put "%s" ".%s.part"' % (local, name)])
        except BaseException:
            try:
                self._run([self._cd(), 'del ".%s.part"' % name], timeout=120,
                          ignore=('NT_STATUS_NO_SUCH_FILE', 'NT_STATUS_OBJECT_NAME_NOT_FOUND'))
            except Exception:                           # noqa: BLE001
                pass
            raise
        self._run([self._cd(), 'del "%s"' % name, 'rename ".%s.part" "%s"' % (name, name)],
                  ignore=('NT_STATUS_NO_SUCH_FILE', 'NT_STATUS_OBJECT_NAME_NOT_FOUND'))
"""),
])

edit('87x_trial.py', [
("""        try:
            said = _readdress_hba(ask['old'], ask['new'], False, drop_old=True)
            log('the other node kept its new address %s: %s' % (ask['new'], said), 'info')
        except Exception as e:                          # noqa: BLE001
            log('the old address of the other node could not be taken out of pg_hba.conf: %s'
                % e, 'warn')
        store.set_meta(done_key, str(ask.get('id')))
""",
 """        try:
            said = _readdress_hba(ask['old'], ask['new'], False, drop_old=True)
            log('the other node kept its new address %s: %s' % (ask['new'], said), 'info')
        except Exception as e:                          # noqa: BLE001
            # Asked again at the next look (1.0.318): written down as done, a root helper away at
            # that moment left the old address let in to the database for good.
            log_sparing('readdress-dropold', 'the old address of the other node could not be taken '
                        'out of pg_hba.conf (asked again): %s' % e, 'warn')
            continue
        store.set_meta(done_key, str(ask.get('id')))
"""),
("""    # One node puts it back (both would write the same rows at once).
    if claim_once(store, 'fw_trial_back', trial.get('id')):
""",
 """    # One node puts it back (both would write the same rows at once) - claimed by its id and its
    # end (1.0.318): by the id alone, a trial put back once and kept open again (a change on the
    # other node at that moment, a put-back that failed) was never claimed again, never put back.
    if claim_once(store, 'fw_trial_back', '%s:%s' % (trial.get('id'), fnum(trial.get('until')))):
"""),
])

edit('90_api.py', [
("""    after = int(CONFIG.get('lockout_after') or 0)
    for r in store.db.rows('SELECT name, locked_until, failures, fail_times, last_from FROM '
""",
 """    after = split_limit('lockout_after')            # as in force, halved while apart (1.0.318)
    for r in store.db.rows('SELECT name, locked_until, failures, fail_times, last_from FROM '
"""),
])

edit('88w_web.py', [
("""            'fw' not in desired and 'access' not in desired and 'acme' not in desired and \\
            'lbport' not in desired and 'certlogin' not in desired:
        return
""",
 """            'fw' not in desired and 'access' not in desired and 'acme' not in desired and \\
            'lbport' not in desired and 'certlogin' not in desired and \\
            'realip' not in desired and 'sso_peer' not in desired:
        # The balancer's address and its sign-in too (1.0.318): switched on alone, on a node never
        # asked anything before, they never reached nginx.
        return
"""),
("""        if val and not re.match(r'^[A-Za-z0-9_.:-]{1,15}\\Z', val):
            raise ValueError('%r is not the name of a network interface' % val)
""",
 """        # As root takes it (1.0.318): one it refused (-x, a dot alone) held back the node's whole part.
        if val and not re.match(r'^(?!\\.+\\Z)[A-Za-z0-9_][A-Za-z0-9_.:-]{0,14}\\Z', val):
            raise ValueError('%r is not the name of a network interface' % val)
"""),
])
