

# ---- root's SSH keys and the updates of the system (1.0.158) ------------------------
# Both done by each node's root helper (otp_web.py), asked through the
# database so a page on either node reaches both. One writer a row, as
# replication wants: what is asked of a node is in a row of the asking node's
# own ('host:sshkeys:want:NODE@@ASKER', node_key) and the node answers in rows
# of its own ('host:sshkeys:now:NODE', 'host:osup:node:NODE').
HOST_WORK = {'ssh': False, 'ssh_seen': 0.0, 'ssh_since': 0.0, 'osup': False, 'osup_read': 0.0}


def host_nodes(store):
    return [node_name()] + [n['name'] for n in ha_nodes(store) if n['name'] != node_name()]


def host_alive(store):
    """{node: whether it is heard from}."""
    out = {node_name(): True}
    for n in ha_nodes(store):
        if n['name'] != node_name():
            out[n['name']] = bool(n.get('alive'))
    return out


# -- the keys --------------------------------------------------------------------------
def sshkeys_view(store):
    alive = host_alive(store)
    nodes = []
    for n in host_nodes(store):
        now = _meta_json(store, 'host:sshkeys:now:' + n) or {}
        done = set(now.get('done') or [])
        pending = late = 0
        for r in node_key_rows(store, 'host:sshkeys:want', n):
            try:
                asks = json.loads(r['v'] or '[]')
            except ValueError:
                continue
            for a in asks if isinstance(asks, list) else [asks]:
                # A change still to be written - a read again is no change,
                # and one not done in five minutes is not still coming (1.0.159).
                if isinstance(a, dict) and a.get('id') and a['id'] not in done and \
                        a.get('do') in ('add', 'drop') and time.time() - float(a.get('at') or 0) < 300:
                    pending += 1
                elif isinstance(a, dict) and a.get('id') and a['id'] not in done and \
                        a.get('do') in ('add', 'drop') and time.time() - float(a.get('at') or 0) < 3600:
                    late += 1
        nodes.append({'name': n, 'me': n == node_name(), 'alive': alive.get(n, False),
                      'keys': now.get('keys') or [], 'sshd': now.get('sshd') or {},
                      'file': now.get('file') or '', 'at': now.get('at'),
                      'error': now.get('error') or ('%d change(s) asked of it more than five minutes ago '
                                                    'are not written - is otp-web.path running there?' % late
                                                    if late else ''),
                      'pending': pending})
    return {'nodes': nodes, 'keygen': bool(shutil.which('ssh-keygen')),
            'cluster': len(nodes) > 1,
            'kept': rootkey_view(store, {n['name']: n['keys'] for n in nodes})}


def sshkeys_ask(store, nodes, do, by, line='', fp='', last_ok=False):
    known = host_nodes(store)
    nodes = [n for n in known if n in (nodes or [])]
    if not nodes:
        raise ValueError('which node?')
    if do not in ('list', 'add', 'drop'):
        raise ValueError('list, add or drop')
    line = str(line or '').strip()
    if do == 'add' and (len(line) > 16500 or '\n' in line):
        raise ValueError('one public key line')
    for n in nodes:
        # One row per asked node and asking node, kept to the last few asks.
        k = node_key('host:sshkeys:want', n)
        try:
            had = json.loads(store.get_meta(k) or '[]')
        except ValueError:
            had = []
        if isinstance(had, dict):
            had = [had]
        had = [x for x in had if isinstance(x, dict) and time.time() - float(x.get('at') or 0) < 3600]
        had.append({'id': secrets.token_hex(6), 'do': do, 'line': line, 'fp': str(fp or '')[:80],
                    'last_ok': bool(last_ok), 'by': by, 'at': time.time()})
        store.set_meta(k, json.dumps(had[-10:]))
    if do != 'list':
        what = 'added the SSH key %s' % (line.split(' ', 2)[2] if line.count(' ') >= 2 else
                                         line[:40]) if do == 'add' else 'took away the SSH key %s' % fp
        store.add_event('settings', '%s %s for root on %s' % (by, what, ', '.join(nodes)),
                        'warn', who=by)
    return nodes


def sshkeys_tick(daemon):
    store = daemon.store
    me = node_name()
    if HOST_WORK['ssh'] and time.time() - HOST_WORK.get('ssh_since', 0) < 900:
        return
    now = _meta_json(store, 'host:sshkeys:now:' + me) or {}
    done = list(now.get('done') or [])
    todo = []
    for r in node_key_rows(store, 'host:sshkeys:want', me):
        try:
            asks = json.loads(r['v'] or '[]')
        except ValueError:
            continue
        for a in asks if isinstance(asks, list) else [asks]:
            if isinstance(a, dict) and a.get('id') and a['id'] not in done and \
                    time.time() - float(a.get('at') or 0) < 3600:
                todo.append(a)
    todo.sort(key=lambda a: float(a.get('at') or 0))
    stale = time.time() - HOST_WORK['ssh_seen'] > 300 or not now
    if not todo and not stale:
        return
    HOST_WORK['ssh'] = True
    HOST_WORK['ssh_since'] = time.time()
    # Reads asked again and again are one read (1.0.159).
    lists = [a for a in todo if a.get('do') == 'list']
    todo = [a for a in todo if a.get('do') != 'list'] + lists[-1:]

    def go():
        row = dict(now)
        changed_err = ''
        try:
            for a in todo or [{'id': '', 'do': 'list'}]:
                err, got = '', None
                try:
                    got = root_ask('sshkeys.ask', 'sshkeys.json', {
                        'do': a.get('do'), 'line': a.get('line') or '', 'fp': a.get('fp') or '',
                        'last_ok': bool(a.get('last_ok'))}, 60)
                except Exception as e:                  # noqa: BLE001
                    err = str(e)[:300] or e.__class__.__name__
                    log('root\'s SSH keys: %s' % err, 'warn')
                if a.get('id'):
                    done.append(a['id'])
                done.extend(x['id'] for x in lists if x.get('id') and x['id'] not in done)
                # Written after each, so what is done shows as it is done.
                # A change refused stays said over the read after it.
                if err or a.get('do') != 'list' or not changed_err:
                    row['error'] = err
                if a.get('do') != 'list':
                    changed_err = err
                row.update(at=time.time(), done=done[-200:])
                if got:
                    row.update(keys=got.get('keys') or [], sshd=got.get('sshd') or {},
                               file=got.get('file') or '')
                store.set_meta('host:sshkeys:now:' + me, json.dumps(row))
            HOST_WORK['ssh_seen'] = time.time()
        except Exception as e:                          # noqa: BLE001
            log_sparing('sshkeys', 'root\'s SSH keys: %s' % e)
        finally:
            HOST_WORK['ssh'] = False
    threading.Thread(target=go, name='otp-sshkeys', daemon=True).start()


# -- root's key, made or given here (1.0.159) -------------------------------------------
# Drawn as isemon draws a router's key, but kept nowhere: otp never signs in
# as root itself, so a private half in the database would only be one more
# way to root on every node. A key made here is handed to the page once; one
# given has its public half worked out and its private half dropped. What is
# remembered of each - for every node ('all') or for one node - is its public
# half, to show it and put it on again where it is missing.


SSH_KEY_KINDS = {'ed25519': ['-t', 'ed25519'], 'rsa4096': ['-t', 'rsa', '-b', '4096']}


def sshkey_pair(kind, comment):
    """A new key pair made by ssh-keygen in a folder of its own, taken away
    after: (private, public, fingerprint)."""
    if kind not in SSH_KEY_KINDS:
        raise ValueError('ed25519 or rsa4096')
    if not shutil.which('ssh-keygen'):
        raise ValueError('ssh-keygen is not on this machine (dnf install openssh-clients)')
    comment = re.sub(r'[^A-Za-z0-9@._ -]', '', str(comment or ''))[:80].strip() or 'root'
    with tempfile.TemporaryDirectory(prefix='.otp-key-') as work:
        path = os.path.join(work, 'k')
        got = subprocess.run(['ssh-keygen', '-q'] + SSH_KEY_KINDS[kind] +
                             ['-a', '100', '-N', '', '-C', comment, '-f', path],
                             capture_output=True, text=True, timeout=120)
        if got.returncode != 0:
            raise ValueError('ssh-keygen: %s' % (got.stderr or got.stdout).strip()[:200])
        with open(path) as f:
            private = f.read()
        with open(path + '.pub') as f:
            public = f.read().strip()
    return private, public, ssh_fp_of(public)[0]


def rootkey_scopes(store):
    return ['all'] + (host_nodes(store) if CONFIG.get('ha_mode') or len(host_nodes(store)) > 1 else [])


def rootkey_nodes(store, scope):
    return host_nodes(store) if scope == 'all' else [scope]


def rootkey_row(store, scope):
    return _meta_json(store, 'host:rootkey:' + scope) or {}


def _rootkey_scope(store, scope):
    scope = str(scope or 'all')
    if scope not in rootkey_scopes(store):
        raise ValueError('for every node, or for one of them')
    return scope


def ssh_fp_of(public):
    got = subprocess.run(['ssh-keygen', '-l', '-E', 'sha256', '-f', '-'], input=public + '\n',
                         capture_output=True, text=True, timeout=20)
    bits = got.stdout.split()
    if got.returncode != 0 or len(bits) < 2:
        raise ValueError('ssh-keygen does not read that key')
    return bits[1], bits[-1].strip('()') if bits[-1].startswith('(') else ''


def rootkey_view(store, keys_on):
    out = []
    for sc in rootkey_scopes(store):
        r = rootkey_row(store, sc)
        on = {n: any(k.get('fp') == r.get('fp') for k in keys_on.get(n, [])) if r.get('fp') else False
              for n in rootkey_nodes(store, sc)}
        out.append({'scope': sc, 'has': bool(r.get('pub')), 'pub': r.get('pub') or '',
                    'fp': r.get('fp') or '', 'kind': r.get('kind') or '', 'how': r.get('how') or '',
                    'by': r.get('by') or '', 'at': r.get('at'), 'on': on})
    return out


def rootkey_put(store, scope, public, by, how):
    """A public half onto the nodes of a scope, remembered for it. The key put
    there before stays - it is taken away in the list, if it should go."""
    scope = _rootkey_scope(store, scope)
    fp, kind = ssh_fp_of(public)
    nodes = rootkey_nodes(store, scope)
    sshkeys_ask(store, nodes, 'add', by, line=public)
    store.set_meta('host:rootkey:' + scope, json.dumps({
        'scope': scope, 'pub': public, 'fp': fp, 'kind': kind, 'how': how, 'by': by,
        'at': time.time()}))
    return {'pub': public, 'fp': fp, 'nodes': nodes}


def rootkey_public(text, passphrase=''):
    """What the page was given: a public key line as it is, or a private key's
    public half - the private half dropped."""
    text = str(text or '').strip()
    if 'PRIVATE KEY-----' in text:
        _, public = ssh_public_of(text, passphrase)
        return public, True
    line = text.splitlines()[0].strip() if text else ''
    if not re.match(r'(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521)|sk-ssh-ed25519@openssh\.com|'
                    r'sk-ecdsa-sha2-nistp256@openssh\.com) [A-Za-z0-9+/=]{20,}( [^\r\n]{0,200})?$', line):
        raise ValueError('that is not a public key line (ssh-ed25519 AAAA… comment) nor a private key')
    return line, False


def rootkey_again(store, scope, by):
    scope = _rootkey_scope(store, scope)
    r = rootkey_row(store, scope)
    if not r.get('pub'):
        raise ValueError('there is no key made or given for that')
    return sshkeys_ask(store, rootkey_nodes(store, scope), 'add', by, line=r['pub'])


# -- the updates -----------------------------------------------------------------------
OSUP_STATES = ('waiting', 'draining', 'updating', 'rebooting', 'done', 'failed', 'skipped')


def osup_plan(store):
    return _meta_json(store, 'host:osup:plan') or {}


def osup_row(store, name):
    return _meta_json(store, 'host:osup:node:' + name) or {}


def osup_put(store, row, **kw):
    row.update(kw, at=time.time())
    store.set_meta('host:osup:node:' + node_name(), json.dumps(row))
    return row


def osup_view(store):
    plan = osup_plan(store)
    seen = store.get_meta('host:osup:seen')
    alive = host_alive(store)
    nodes = []
    for n in host_nodes(store):
        row = osup_row(store, n)
        chk = _meta_json(store, 'host:osup:check:' + n) or {}
        nodes.append({'name': n, 'me': n == node_name(), 'alive': alive.get(n, False),
                      'row': row if row.get('plan') == plan.get('id') else {},
                      'check': chk, 'reboot': bool(row.get('reboot') and not row.get('rebooted')) or
                      bool(chk.get('reboot_now') and chk.get('state') == 'done'),
                      'started': (_meta_json(store, 'node:' + n) or {}).get('started')})
    hidden = bool(plan) and seen == plan.get('id') and plan.get('state') != 'running'
    return {'plan': {} if hidden else plan, 'nodes': nodes, 'now': time.time(),
            'cluster': bool(CONFIG.get('ha_mode')), 'helper': WEB_DIR.is_dir(),
            'power': power_plan(store) if power_busy(store) else {}}


def osup_check_ask(store, nodes, by):
    nodes = [n for n in host_nodes(store) if n in (nodes or [])]
    if not nodes:
        raise ValueError('which node?')
    for n in nodes:
        store.set_meta(node_key('host:osup:checkwant', n),
                       json.dumps({'id': secrets.token_hex(6), 'by': by, 'at': time.time()}))
    return nodes


def osup_start(store, nodes, reboot, by):
    plan = osup_plan(store)
    if plan.get('state') == 'running':
        raise ValueError('an update is going on already')
    if upgrade_plan(store) and upgrade_plan(store).get('state') == 'running':
        raise ValueError('an upgrade of otp is going on - wait for it to end')
    if power_busy(store):
        raise ValueError('a restart or a power off is going on - wait for it to end')
    known = host_nodes(store)
    alive = host_alive(store)
    nodes = [n for n in known if n in (nodes or known)]
    if not nodes:
        raise ValueError('which node?')
    gone = [n for n in nodes if not alive.get(n)]
    if gone:
        raise ValueError('%s is not heard from: bring it back first' % ', '.join(gone))
    if reboot not in ('ask', 'auto'):
        reboot = 'ask'
    # The others first, this one last - the page the person looks at stays
    # up the longest, as in an upgrade of otp.
    me = node_name()
    order = sorted(n for n in nodes if n != me) + ([me] if me in nodes else [])
    plan = {'id': secrets.token_hex(6), 'order': order, 'reboot': reboot, 'by': by,
            'at': time.time(), 'state': 'running', 'from': me}
    store.set_meta('host:osup:plan', json.dumps(plan))
    store.add_event('settings', '%s started the update of the system: %s, one at a time%s'
                    % (by, ', '.join(order), ', each restarted when it needs it'
                       if reboot == 'auto' else ''), 'warn', who=by)
    return plan


def osup_cancel(store, by):
    plan = osup_plan(store)
    if plan.get('state') != 'running':
        raise ValueError('no update is going on')
    plan.update(state='cancelled', ended=time.time(), cancelled_by=by)
    store.set_meta('host:osup:plan', json.dumps(plan))
    store.add_event('settings', '%s stopped the update of the system - a node being updated '
                    'finishes' % by, 'warn', who=by)


def _osup_job(kind):
    """The helper asked to start the work; its id."""
    got = root_ask('osup.ask', 'osup.ans', {'do': 'run', 'kind': kind}, 60)
    return got


def _osup_read():
    try:
        return json.loads((WEB_DIR / 'osup.json').read_text())
    except (OSError, ValueError):
        return {}


def osup_tick(daemon):
    """Every few seconds: a look for updates asked of this node; its turn in an
    update; what the helper says while it works."""
    store = daemon.store
    me = node_name()
    if HOST_WORK['osup'] or HA_REBUILDING.is_set():
        return
    # Back up after a restart the update asked for: done, and back in service.
    row = osup_row(store, me)
    if row.get('reboot') and not row.get('rebooted') and \
            boot_time() > float(row.get('done_at') or row.get('at') or 0) + 1:
        row['rebooted'] = True
        store.set_meta(node_key('host:osup:checkwant', me),
                       json.dumps({'id': secrets.token_hex(6), 'by': 'otp (system update)',
                                   'at': time.time()}))
        if row.get('state') == 'rebooting':
            row['state'] = 'done'
            row['said'] = 'up again after the restart'
            plan = osup_plan(store)
            if plan.get('state') == 'running' and (plan.get('order') or [None])[-1] == me and \
                    row.get('plan') == plan.get('id'):
                plan.update(state='done', ended=time.time())
                store.set_meta('host:osup:plan', json.dumps(plan))
            if row.get('maint'):
                try:
                    maintenance_set(store, False, '', 'otp (system update)')
                except Exception:                       # noqa: BLE001
                    pass
                row['maint'] = False
        osup_put(store, row)
    # A look for updates, asked.
    chk = _meta_json(store, 'host:osup:check:' + me) or {}
    # It said a restart was waiting and the node has restarted since: looked
    # at again, not left saying so (1.0.159).
    if chk.get('reboot_now') and chk.get('state') == 'done' and not chk.get('relook') and \
            boot_time() > float(chk.get('checked') or 0) + 1:
        chk['relook'] = True
        store.set_meta('host:osup:check:' + me, json.dumps(chk))
        store.set_meta(node_key('host:osup:checkwant', me),
                       json.dumps({'id': secrets.token_hex(6), 'by': 'otp (system update)',
                                   'at': time.time()}))
    for r in node_key_rows(store, 'host:osup:checkwant', me):
        try:
            a = json.loads(r['v'] or '{}')
        except ValueError:
            continue
        if a.get('id') and a['id'] not in (chk.get('asked') or []) and \
                time.time() - float(a.get('at') or 0) < 900:
            _osup_go(daemon, 'check', a)
            return
    if chk.get('state') == 'running':
        _osup_follow_check(store, chk)
        return
    plan = osup_plan(store)
    if plan.get('state') != 'running' or me not in (plan.get('order') or []):
        return
    row = osup_row(store, me)
    if row.get('plan') != plan.get('id'):
        row = {'plan': plan.get('id'), 'state': 'waiting'}
    st = row.get('state') or 'waiting'
    if st == 'waiting':
        # My turn once every node before me is done.
        before = plan['order'][:plan['order'].index(me)]
        rows = {n: osup_row(store, n) for n in before}
        bad = [n for n in before if rows[n].get('plan') == plan['id'] and
               rows[n].get('state') == 'failed']
        if bad:
            return
        if all(rows[n].get('plan') == plan['id'] and rows[n].get('state') in ('done', 'skipped')
               for n in before):
            _osup_go(daemon, 'upgrade', {'plan': plan, 'row': row})
        return
    if st == 'draining':
        if time.time() - float(row.get('drain_at') or 0) >= 15:
            _osup_go(daemon, 'upgrade-now', {'plan': plan, 'row': row})
        return
    if st == 'updating':
        _osup_follow(daemon, plan, row)


def _osup_go(daemon, what, ctx):
    HOST_WORK['osup'] = True

    def go():
        store = daemon.store
        me = node_name()
        by = 'otp (system update)'
        try:
            if what == 'check':
                chk = _meta_json(store, 'host:osup:check:' + me) or {}
                asked = (list(chk.get('asked') or []) + [ctx['id']])[-20:]
                try:
                    _osup_job('check')
                    store.set_meta('host:osup:check:' + me, json.dumps(
                        dict(chk, state='running', asked=asked, began=time.time(), at=time.time(),
                             error='', lines=[])))
                except ValueError as e:
                    store.set_meta('host:osup:check:' + me, json.dumps(
                        dict(chk, state='failed', asked=asked, at=time.time(), error=str(e)[:300])))
                return
            plan, row = ctx['plan'], ctx['row']
            if what == 'upgrade':
                # Out of service first where another node answers meanwhile:
                # the web address moves to it, RADIUS is answered there.
                many = any(n.get('alive') and not n.get('me') for n in ha_nodes(store))
                if many:
                    maintenance_set(store, True, 'the system is being updated', by)
                    osup_put(store, row, state='draining', drain_at=time.time(), maint=True,
                             said='out of service - the other node answers', pct=0, lines=[])
                    return
                row['maint'] = False
            try:
                _osup_job('upgrade')
                osup_put(store, row, state='updating', began=time.time(), pct=1, lines=[],
                         said='the packages are being updated')
            except ValueError as e:
                _osup_end(store, plan, row, False, str(e))
        except Exception as e:                          # noqa: BLE001
            log('the update of the system: %s' % e, 'warn')
        finally:
            HOST_WORK['osup'] = False
    threading.Thread(target=go, name='otp-osup', daemon=True).start()


def _osup_follow_check(store, chk):
    me = node_name()
    got = _osup_read()
    if not got or got.get('kind') != 'check' or float(got.get('began') or 0) < \
            float(chk.get('began') or 0) - 5:
        if time.time() - float(chk.get('began') or 0) > 1800:
            store.set_meta('host:osup:check:' + me, json.dumps(
                dict(chk, state='failed', error='the helper did not say anything', at=time.time())))
        return
    if got.get('state') == 'running':
        if time.time() - float(chk.get('at') or 0) > 3:
            store.set_meta('host:osup:check:' + me, json.dumps(
                dict(chk, at=time.time(), lines=(got.get('lines') or [])[-40:])))
        return
    store.set_meta('host:osup:check:' + me, json.dumps(dict(
        chk, state=got.get('state'), at=time.time(), checked=time.time(), relook=False,
        packages=(got.get('packages') or [])[:1000], count=int(got.get('count') or 0),
        security=got.get('security'), pm=got.get('pm'), error=got.get('said') or '',
        reboot_after=bool(got.get('reboot_after')), reboot_why=(got.get('reboot_why') or [])[:20],
        reboot_now=bool(got.get('reboot_now')),
        lines=(got.get('lines') or [])[-40:])))


def _osup_follow(daemon, plan, row):
    store = daemon.store
    got = _osup_read()
    if not got or got.get('kind') != 'upgrade' or \
            float(got.get('began') or 0) < float(row.get('began') or 0) - 5:
        if time.time() - float(row.get('began') or 0) > 600:
            _osup_end(store, plan, row, False, 'the helper did not start the update')
        return
    if got.get('state') == 'running':
        if time.time() - HOST_WORK['osup_read'] > 2:
            HOST_WORK['osup_read'] = time.time()
            osup_put(store, row, pct=int(got.get('pct') or 0), phase=got.get('phase') or '',
                     lines=(got.get('lines') or [])[-300:])
        return
    row['lines'] = (got.get('lines') or [])[-300:]
    row['pct'] = 100
    _osup_end(store, plan, row, got.get('state') == 'done', got.get('said') or '',
              reboot=bool(got.get('reboot')))


def _osup_end(store, plan, row, ok, said='', reboot=False):
    me = node_name()
    by = 'otp (system update)'
    row.update(done_at=time.time(), reboot=reboot, rebooted=False)
    if not ok:
        osup_put(store, row, state='failed', said=said or 'it failed')
        if row.get('maint'):
            maintenance_set(store, False, '', by)
            row['maint'] = False
            osup_put(store, row)
        plan.update(state='failed', ended=time.time(), failed_on=me)
        store.set_meta('host:osup:plan', json.dumps(plan))
        store.add_event('settings', 'the update of the system failed on %s: %s' % (me, said),
                        'bad', who=by)
        return
    if reboot and plan.get('reboot') == 'auto':
        osup_put(store, row, state='rebooting', said='updated - restarting, as it needs')
        try:
            power_ask(store, 'reboot', [me], 'one', by)
        except ValueError as e:
            osup_put(store, row, state='done', said='updated; the restart was not started: %s' % e)
        return
    osup_put(store, row, state='done', said='updated' + (' - it needs a restart' if reboot else ''))
    # What is waiting looked at again, not left at what was there before.
    store.set_meta(node_key('host:osup:checkwant', me),
                   json.dumps({'id': secrets.token_hex(6), 'by': by, 'at': time.time()}))
    if row.get('maint'):
        maintenance_set(store, False, '', by)
        row['maint'] = False
        osup_put(store, row)
    store.add_event('settings', 'the system of %s is updated%s' % (
        me, ' - it needs a restart' if reboot else ''), 'warn' if reboot else 'info', who=by)
    order = plan.get('order') or []
    if order and order[-1] == me:
        plan.update(state='done', ended=time.time())
        store.set_meta('host:osup:plan', json.dumps(plan))
