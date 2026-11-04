
# ---- the local users of the machines (1.0.243) -----------------------------------------
# Settings -> Local users: the users of each node (root and those of the normal range), made and
# looked after on every node of a cluster at once or on one - by each node's root helper
# (otp_web.py, users.ask), asked through the database as root's SSH keys are: what is asked of a
# node is in a row of the asking node's own ('host:users:want:NODE@@ASKER', signed when the guard
# of root's actions is on), and the node answers in a row of its own ('host:users:now:NODE').
# root is shown, never changed. A password is typed on one node and never leaves it as itself:
# its hash (SHA-512 crypt, made by openssl from standard input) is what is asked, sealed with
# the cluster's key, taken out of the asking row once the node said it is done.
OSU_WORK = {'busy': False, 'since': 0.0, 'seen': 0.0}
OSU_KEEP = ('root', 'otp', 'otp-web', 'postgres', 'nginx', 'apache', 'nobody', 'keepalived',
            'chrony', 'sshd', 'polkitd', 'dbus', 'systemd-network', 'tss')
OSU_DOS = ('list', 'add', 'password', 'lock', 'unlock', 'sudo', 'set', 'drop')
OSU_PW_MIN = 8


def osu_now(store, n):
    return _meta_json(store, 'host:users:now:' + n) or {}


def osu_asks(store, n):
    out = []
    for r in node_key_rows(store, 'host:users:want', n):
        try:
            asks = json.loads(r['v'] or '[]')
        except ValueError:
            continue
        for a in asks if isinstance(asks, list) else [asks]:
            if isinstance(a, dict) and a.get('id'):
                out.append(a)
    return out


def osu_view(store):
    alive = host_alive(store)
    nodes = []
    for n in host_nodes(store):
        now = osu_now(store, n)
        done = set(now.get('done') or [])
        pending = late = 0
        for a in osu_asks(store, n):
            if a['id'] in done or a.get('do') == 'list':
                continue
            age = time.time() - float(a.get('at') or 0)
            if age < 300:
                pending += 1
            elif age < 3600:
                late += 1
        nodes.append({'name': n, 'me': n == node_name(), 'alive': alive.get(n, False),
                      'users': now.get('users') or [], 'at': now.get('at'),
                      'admin_group': now.get('admin_group') or '', 'shells': now.get('shells') or [],
                      'uid_min': now.get('uid_min'), 'uid_max': now.get('uid_max'),
                      'today': now.get('today'), 'said': now.get('said') or [],
                      'error': now.get('error') or ('%d change(s) asked of it more than five minutes '
                                                    'ago are not done - is otp-web.path running '
                                                    'there?' % late if late else ''),
                      'pending': pending})
    return {'nodes': nodes, 'cluster': len(nodes) > 1, 'pw_min': OSU_PW_MIN,
            'openssl': bool(shutil.which('openssl'))}


def osu_hash(password):
    """The SHA-512 crypt hash of a password, by openssl from its standard input."""
    pw = str(password or '')
    if len(pw) < OSU_PW_MIN:
        raise ValueError('the password is %d characters at least' % OSU_PW_MIN)
    if len(pw) > 256 or re.search(r'[\x00-\x1f\x7f]', pw):
        raise ValueError('the password is 256 characters at most, with no line breaks')
    exe = shutil.which('openssl')
    if not exe:
        raise ValueError('openssl is not on this node - it makes the password\'s hash')
    got = subprocess.run([exe, 'passwd', '-6', '-stdin'], input=pw + '\n', capture_output=True,
                         text=True, timeout=30)
    h = (got.stdout or '').strip()
    if got.returncode != 0 or not h.startswith('$6$'):
        raise ValueError('openssl did not make the password\'s hash: %s'
                         % ((got.stderr or '').strip()[:200] or 'no answer'))
    return h


def osu_free_uid(store, nodes, name):
    """One UID for the new user on every node: the one it has where it is there already, or the
    lowest of the normal range none of the nodes uses."""
    lo, hi, used = 1000, 60000, set()
    for n in nodes:
        now = osu_now(store, n)
        if not now.get('at'):
            raise ValueError('%s has not said who its users are yet - wait a few seconds' % n)
        lo = max(lo, int(now.get('uid_min') or 1000))
        hi = min(hi, int(now.get('uid_max') or 60000))
        used.update(int(u) for u in now.get('used') or [] if str(u).isdigit())
        for u in now.get('users') or []:
            if u.get('name') == name:
                return int(u['uid'])
    for uid in range(lo, hi + 1):
        if uid not in used:
            return uid
    raise ValueError('no UID of the normal range is free on %s' % ', '.join(nodes))


def osu_ask(store, nodes, do, by, **f):
    """One change asked of the nodes named - checked here, done by each node's root helper."""
    known = host_nodes(store)
    nodes = [n for n in known if n in (nodes or [])]
    if not nodes:
        raise ValueError('which node?')
    if do not in OSU_DOS:
        raise ValueError('no such thing to do with a user')
    name = str(f.get('name') or '')
    ask = {'do': do, 'by': by, 'at': time.time()}
    if do != 'list':
        if name == 'root':
            raise ValueError('root is shown here, never changed - on the machine itself only')
        if not SSH_USER_RE.match(name) or name in OSU_KEEP or name.lower() != name:
            raise ValueError('a user\'s name is small letters, digits, _ . and -, 32 at most, '
                             'starting with a letter - and not one of the system\'s')
        ask['name'] = name
        if do != 'add':
            # Only a user of the normal range the node said it has.
            for n in nodes:
                now = osu_now(store, n)
                if now.get('at') and not any(u.get('name') == name and not u.get('root')
                                             for u in now.get('users') or []):
                    if do != 'drop':
                        raise ValueError('%s has no user %s' % (n, name))
    if do in ('add', 'set'):
        if 'gecos' in f:
            g = str(f.get('gecos') or '').strip()
            if len(g) > 120 or re.search(r'[:\x00-\x1f\x7f]', g):
                raise ValueError('the full name is 120 characters at most, without a colon')
            ask['gecos'] = g
        if 'shell' in f:
            s = str(f.get('shell') or '')
            if not re.match(r'^/[A-Za-z0-9_./-]{1,80}\Z', s):
                raise ValueError('that is not a shell')
            ask['shell'] = s
    if do == 'add':
        ask['uid'] = osu_free_uid(store, nodes, name)
        ask['sudo'] = bool(f.get('sudo'))
        ask['must_change'] = bool(f.get('must_change'))
        if f.get('password'):
            ask['hash'] = seal_secret(osu_hash(f['password']), 'osuser:' + name)
    elif do == 'password':
        ask['hash'] = seal_secret(osu_hash(f.get('password')), 'osuser:' + name)
        ask['must_change'] = bool(f.get('must_change'))
    elif do == 'sudo':
        ask['on'] = bool(f.get('on'))
    elif do == 'drop':
        ask['home'] = bool(f.get('home'))
    for n in nodes:
        k = node_key('host:users:want', n)
        try:
            had = json.loads(store.get_meta(k) or '[]')
        except ValueError:
            had = []
        had = [x for x in (had if isinstance(had, list) else [had])
               if isinstance(x, dict) and time.time() - float(x.get('at') or 0) < 3600]
        had.append(dict(ask, id=secrets.token_hex(6)))
        store.set_meta(k, json.dumps(had[-20:]))
    if do != 'list':
        words = {'add': 'made the local user %s' % name,
                 'password': 'set a new password for the local user %s' % name,
                 'lock': 'locked the local user %s' % name,
                 'unlock': 'unlocked the local user %s' % name,
                 'sudo': '%s the local user %s sudo' % ('gave' if ask.get('on') else 'took from', name),
                 'set': 'changed the local user %s' % name,
                 'drop': 'took away the local user %s%s' % (name, ' and the home folder'
                                                             if ask.get('home') else '')}[do]
        if do == 'add':
            words += ' (UID %d%s%s)' % (ask['uid'], ', sudo' if ask['sudo'] else '',
                                        ', a password set' if ask.get('hash') else ', no password')
        store.add_event('settings', '%s %s on %s' % (by, words, ', '.join(nodes)), 'warn', who=by)
    return nodes


def osu_forget_hashes(store):
    """The hashes this node asked of the others, taken out of its own rows once done."""
    me = node_name()
    for n in host_nodes(store):
        k = node_key('host:users:want', n)
        try:
            had = json.loads(store.get_meta(k) or '[]')
        except ValueError:
            continue
        if not isinstance(had, list) or not any(isinstance(a, dict) and a.get('hash') for a in had):
            continue
        done = set(osu_now(store, n).get('done') or [])
        changed = False
        for a in had:
            if isinstance(a, dict) and a.get('hash') and (
                    a.get('id') in done or time.time() - float(a.get('at') or 0) > 900):
                a.pop('hash', None)
                a['hash_gone'] = True
                changed = True
        if changed:
            store.set_meta(k, json.dumps(had))


def osu_keep(row, got):
    row.update({k: got.get(k) for k in ('users', 'uid_min', 'uid_max', 'used', 'admin_group',
                                        'shells', 'today')})
    row['at'] = time.time()


def osu_one(a):
    """One change done by the root helper: its answer, or what went wrong (words)."""
    q = {k: v for k, v in a.items() if k in ('do', 'name', 'uid', 'gecos', 'shell', 'sudo',
                                              'must_change', 'on', 'home')}
    if a.get('hash'):
        h = unseal_secret(a['hash'], 'osuser:' + str(a.get('name') or ''))
        if not str(a['hash']).startswith(SEALED2) or not h:
            return ('the password for %s could not be opened here - is the key that opens the '
                    'tokens the same on this node?' % a.get('name'))
        q['hash'] = h
    elif a.get('hash_gone'):
        return 'it came too late: the password for %s is no longer kept' % a.get('name')
    try:
        return root_ask('users.ask', 'users.json', q, 120)
    except Exception as e:                              # noqa: BLE001
        err = str(e)[:300] or e.__class__.__name__
        log('the local user %s: %s' % (a.get('name') or '?', err), 'warn')
        return err


def osu_tick(daemon):
    store = daemon.store
    me = node_name()
    try:
        osu_forget_hashes(store)
    except Exception as e:                              # noqa: BLE001
        log_sparing('osu-forget', 'the local users: %s' % e, 'warn', every=600)
    if OSU_WORK['busy'] and time.time() - OSU_WORK['since'] < 900:
        return
    now = osu_now(store, me)
    done = list(now.get('done') or [])
    todo = [a for a in osu_asks(store, me) if a['id'] not in done and
            time.time() - float(a.get('at') or 0) < 3600]
    todo.sort(key=lambda a: float(a.get('at') or 0))
    stale = time.time() - OSU_WORK['seen'] > 300 or not now
    if not todo and not stale:
        return
    changes = [a for a in todo if a.get('do') != 'list']
    lists = [a for a in todo if a.get('do') == 'list']
    OSU_WORK.update(busy=True, since=time.time())

    def go():
        row = dict(now)
        said = list(row.get('said') or [])[-10:]
        try:
            for a in changes:
                err, got = osu_one(a), None
                if isinstance(err, dict):
                    got, err = err, ''
                done.append(a['id'])
                said.append({'at': time.time(), 'id': a['id'], 'do': a.get('do'),
                             'name': a.get('name') or '', 'by': a.get('by') or '',
                             'ok': not err, 'said': err or (got or {}).get('said') or ''})
                if got:
                    osu_keep(row, got)
                row.update(done=done[-300:], said=said[-10:])
                store.set_meta('host:users:now:' + me, json.dumps(row))
            if changes:
                # SSH keys' "Whose keys" read again here too (1.0.244): a user just made was not
                # there until the page was loaded anew and the keys asked again.
                try:
                    sshkeys_ask(store, [me], 'list', 'local users')
                except Exception:                       # noqa: BLE001
                    pass
            try:
                osu_keep(row, root_ask('users.ask', 'users.json', {'do': 'list'}, 60))
                row['error'] = ''
            except Exception as e:                      # noqa: BLE001
                row['error'] = 'its users could not be read: %s' % (str(e)[:300] or
                                                                   e.__class__.__name__)
            done.extend(x['id'] for x in lists)
            row.update(done=done[-300:], said=said[-10:])
            store.set_meta('host:users:now:' + me, json.dumps(row))
            OSU_WORK['seen'] = time.time()
        except Exception as e:                          # noqa: BLE001
            log_sparing('osu', 'the local users: %s' % e)
        finally:
            OSU_WORK['busy'] = False
    threading.Thread(target=go, name='otp-osusers', daemon=True).start()


@route('GET', '/api/osusers')
def _osusers(h):
    h.me('fulladmin')
    return osu_view(h.store)


@route('POST', '/api/osusers')
def _osusers_do(h):
    s = h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    nodes = b.get('nodes') or host_nodes(h.store)
    if not isinstance(nodes, list):
        raise ApiError(400, 'nodes is a list')
    if act == 'refresh':
        act = 'list'
    if act not in OSU_DOS:
        raise ApiError(400, 'no such thing to do with a user')
    f = {k: b[k] for k in ('name', 'gecos', 'shell', 'sudo', 'must_change', 'password', 'on', 'home')
         if k in b}
    try:
        done = osu_ask(h.store, nodes, act, s['name'], **f)
    except ValueError as e:
        raise ApiError(400, str(e))
    if act == 'list':
        return {'message': 'asked again', 'nodes': done}
    return {'message': 'done on %s within a few seconds' % ', '.join(done), 'nodes': done}
