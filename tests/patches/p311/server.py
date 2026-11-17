# 1.0.311: (hunt round 10) a node the other one marked failed that comes back on the new version is
# checked and put back in service (it stayed in maintenance for good); the token of another spelling
# whose directory cannot be asked now is "the directory is away" (an answer for the other node), not
# "no token" counted as a guess.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('88_upgrade.py', [
("""    if plan and plan['state'] == 'failed':
        _back_after_marked(store, plan)""",
 """    if plan and plan['state'] == 'failed':
        _back_after_marked(store, plan, daemon)"""),
("""def _back_after_marked(store, plan):
    \"\"\"A node the other one marked failed while it drained, come back on
    its old version (1.0.61): taken out of the maintenance the upgrade put
    it in, once - nothing else would.\"\"\"
    me = node_name()
    row = _meta_json(store, 'upgrade:node:' + me) or {}
    if row.get('id') != plan.get('id') or row.get('state') != 'failed' or \\
            not row.get('marked_by') or row.get('back') or __version__ == plan.get('version'):
        return""",
 """def _back_after_marked(store, plan, daemon=None):
    \"\"\"A node the other one marked failed while it drained, come back on
    its old version (1.0.61): taken out of the maintenance the upgrade put
    it in, once - nothing else would. Come back on the new version (1.0.311):
    checked as the step "checking" does, and back in service if it passes -
    it stayed in maintenance for good, RADIUS silent, the VIP never there.\"\"\"
    me = node_name()
    row = _meta_json(store, 'upgrade:node:' + me) or {}
    if row.get('id') != plan.get('id') or row.get('state') != 'failed' or \\
            not row.get('marked_by') or row.get('back'):
        return
    if __version__ == plan.get('version'):
        trouble = []
        try:
            store.db.value('SELECT 1')
        except Exception as e:                          # noqa: BLE001
            trouble.append('the database: %s' % e)
        if daemon is not None and not getattr(getattr(daemon, 'radius', None), 'bound', None):
            trouble.append('RADIUS is not listening')
        if trouble:
            return                      # tried again at the next tick; kept out meanwhile
        if not row.get('was_maint'):
            try:
                maintenance_set(store, False, by=plan.get('by') or '')
            except Exception:                           # noqa: BLE001
                return
        row.update(back=True, state='done', at=time.time(),
                   said='%s - came back as %s after %s marked it failed; checked, back in service'
                        % (__version__, __version__, row.get('marked_by')))
        try:
            _row_write(store, 'upgrade:node:' + me, row, mine=False)
        except Exception:                               # noqa: BLE001
            pass
        log('back in service as %s: the upgrade had been marked failed by %s while this node was away'
            % (__version__, row.get('marked_by')), 'warn')
        return"""),
])

edit('70_radius_server.py', [
("""            return ''
        if not entry or entry.get('many'):
            return ''
        return self.same_entry(realm, entry)""",
 """            return ''
        if not entry or entry.get('many'):
            return ''
        return self.same_entry(realm, entry, gone=gone)"""),
("""    def same_entry(self, realm, entry, unproven=False):""",
 """    def same_entry(self, realm, entry, unproven=False, gone=None):"""),
("""            other = self.find_person(ad2, cand, how2, r2)
        except LdapError:
            # Not proven either way: RADIUS lets nobody in on it; the enrolment pages
            # (unproven=True) keep the token as the person's, and make no second one.
            return cand if unproven else ''""",
 """            other = self.find_person(ad2, cand, how2, r2)
        except LdapError as e:
            # Not proven either way: RADIUS lets nobody in on it; the enrolment pages
            # (unproven=True) keep the token as the person's, and make no second one.
            # The directory not reached (1.0.311): said so by the caller - "no token", a refusal
            # counted as a guess, sent the VPN nowhere else.
            if gone is not None and isinstance(e, LdapUnreachable) and not unproven:
                gone.append(e)
            return cand if unproven else ''"""),
])
print('ok')
