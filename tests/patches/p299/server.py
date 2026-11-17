# 1.0.299: the upgrade at a glance in every page's status - the band under the header follows it
# on every node, behind the VIP address too.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('88_upgrade.py', [
("""    plan = {'id': ident, 'version': meta['version'], 'sha': meta['sha'], 'order': order,
            'by': by, 'at': time.time(), 'from': me, 'downgrade': bool(meta.get('downgrade'))}""",
 """    plan = {'id': ident, 'version': meta['version'], 'sha': meta['sha'], 'order': order,
            'by': by, 'at': time.time(), 'from': me, 'downgrade': bool(meta.get('downgrade')),
            'was': __version__}"""),
("""def upgrade_cancel(store, by):""",
 """UPG_BRIEF = {'at': -10.0, 'v': None}


def upgrade_brief(store):
    \"\"\"The upgrade at a glance, for the band every page shows under its header (1.0.299): while
    it runs, and for 10 min after it ended (a page asking a moment later still sees how it
    ended) - not a cancelled one. Read at most every 2 s; never in the way of the status.\"\"\"
    now = time.monotonic()
    if now - UPG_BRIEF['at'] < 2:
        return UPG_BRIEF['v']
    UPG_BRIEF['at'] = now
    v = None
    try:
        plan = upgrade_plan(store)
        # One ended and hidden on Settings → Upgrades (Hide this) is not shown in the band either.
        if plan and plan.get('state') != 'running' and \
                store.get_meta('upgrade:seen') == str(plan.get('id') or plan.get('at')):
            plan = None
        if plan and plan.get('state') in ('running', 'done', 'failed'):
            steps = plan.get('steps') or []
            last = max([fnum(s.get('at')) for s in steps] + [fnum(plan.get('at'))])
            if plan['state'] == 'running' or time.time() - last < 600:
                keep = ('name', 'state', 'part', 'part_words', 'at', 'asked', 'began')
                rows = []
                for s in steps:
                    row = {k: s.get(k) for k in keep if s.get(k) is not None}
                    if s.get('said'):
                        row['said'] = str(s.get('said'))[:300]
                    rows.append(row)
                v = {'id': str(plan.get('id') or ''), 'version': str(plan.get('version') or ''),
                     'from': str(plan.get('was') or ''), 'by': str(plan.get('by') or '')[:100],
                     'at': fnum(plan.get('at')), 'state': plan['state'],
                     'downgrade': bool(plan.get('downgrade')), 'drain_s': UPGRADE_DRAIN_S,
                     'ended': 0 if plan['state'] == 'running' else last, 'steps': rows}
    except Exception:                                   # noqa: BLE001
        v = UPG_BRIEF['v']
    UPG_BRIEF['v'] = v
    return v


def upgrade_cancel(store, by):"""),
])
edit('90_api.py', [
("""    try:
        a = after_summary(h.store)
        out['after'] = {'n': a['n'], 'level': a['level']}
    except Exception:                                   # noqa: BLE001
        out['after'] = {'n': 0, 'level': ''}
    return out
""",
 """    try:
        a = after_summary(h.store)
        out['after'] = {'n': a['n'], 'level': a['level']}
    except Exception:                                   # noqa: BLE001
        out['after'] = {'n': 0, 'level': ''}
    # The upgrade at a glance (1.0.299): the band under every page's header.
    out['upgrading'] = upgrade_brief(h.store)
    return out
"""),
])
print('ok')
