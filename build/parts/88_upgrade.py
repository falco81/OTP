

# ---------------------------------------------------------------------------
# Maintenance, and a new version put in from the pages (1.0.37)
# ---------------------------------------------------------------------------
# Maintenance is per node: the node stops answering RADIUS (the VPN goes to
# the other one, as it would to a node that is down) and /healthz says 503
# (the load balancer takes it out). The pages go on working, so the node can
# be looked at and brought back.
#
# An upgrade: the package goes into the database, in pieces (so the other
# node of a cluster has it too), and a plan says which nodes, in which
# order. Each node does its own turn when it comes - maintenance on, a
# moment for the balancer to notice, the package handed to root
# (otp_upgrade.py, by otp-upgrade.path), and after its restart its own
# check before it leaves maintenance. Then the next one.
#
# Every row has ONE node that writes it (the plan: the one that started it;
# `upgrade:node:X` and `maint:X`: node X - or, for maintenance, the pages,
# which only ever UPDATE it). Replicated, a newer version may add a column,
# and the older node then takes nothing more from it until it is upgraded
# too; so a node's own rows are also written straight into the other's
# database - an UPDATE of a row both have, never an INSERT, which the
# replication arriving later would then collide with.
UPGRADE_DIR = STATE_DIR / 'upgrade'
UPGRADE_HELPER = Path(os.environ.get('OTP_UPGRADE_HELPER',
                                     str(Path(__file__).resolve().parent / 'otp_upgrade.py')))
UPGRADE_MOST = 64 * 1024 * 1024
UPGRADE_PIECE = 40000                       # base64 characters in one meta row
UPGRADE_DRAIN_S = int(os.environ.get('OTP_UPGRADE_DRAIN_S', '20'))
UPGRADE_TIMEOUT_S = 30 * 60
MAINT_CACHE = {'at': 0.0, 'row': None}


def _meta_json(store, k):
    try:
        got = store.get_meta(k)
        return json.loads(got) if got else None
    except (ValueError, TypeError):
        return None


def _peer_update(k, v):
    """The same row changed in the other node's database too - UPDATE only."""
    if CONFIG.get('ha_mode') != 'replicated' or not CONFIG.get('ha_peer'):
        return False
    try:
        far = ha_peer_db()
    except Exception:                                   # noqa: BLE001
        return False
    try:
        return bool(far.run('UPDATE meta SET v = ? WHERE k = ?', (v, k)))
    except Exception:                                   # noqa: BLE001
        return False
    finally:
        try:
            far.close()
        except Exception:                               # noqa: BLE001
            pass


def _row_write(store, k, data, mine=True, mirror=True):
    """A row of this node's own (made here if need be), or someone else's
    (only ever UPDATEd)."""
    v = json.dumps(data, default=str)
    if store.db.value('SELECT k FROM meta WHERE k = ?', (k,)) is None:
        if not mine:
            raise ValueError('that node has not been heard of here yet')
        store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, v))
    else:
        store.db.run('UPDATE meta SET v = ? WHERE k = ?', (v, k))
    if mirror:
        _peer_update(k, v)


# ---- maintenance ---------------------------------------------------------------------
def maintenance_row(store, name=None):
    return _meta_json(store, 'maint:' + (name or node_name())) or {'on': False}


def maintenance_now(store):
    """This node's maintenance, read at most every two seconds - asked for
    every RADIUS packet."""
    if HA_REBUILDING.is_set():
        return {'on': True, 'why': 'rebuilt from the other node'}
    now = time.time()
    if now - MAINT_CACHE['at'] > 2:
        MAINT_CACHE['at'] = now
        try:
            MAINT_CACHE['row'] = maintenance_row(store)
        except Exception:                               # noqa: BLE001
            pass                                        # the last one known stands
    return MAINT_CACHE['row'] or {'on': False}


def maintenance_ensure(store):
    """The row of this node, made by this node: the pages only change it."""
    if HA_REBUILDING.is_set():
        return
    try:
        if store.get_meta('maint:' + node_name()) is None:
            store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)',
                         ('maint:' + node_name(), json.dumps({'on': False})))
    except Exception:                                   # noqa: BLE001
        pass


def maintenance_set(store, on, why='', by='', name=None):
    name = name or node_name()
    row = {'on': bool(on), 'why': str(why or '')[:200], 'by': str(by or '')[:100],
           'at': time.time()}
    _row_write(store, 'maint:' + name, row, mine=(name == node_name()))
    MAINT_CACHE['at'] = 0
    store.add_event('starting and stopping', '%s: %s%s' % (
        name, 'in maintenance' if on else 'back in service',
        (' - ' + why) if why and on else ''), 'warn' if on else 'info', who=by or None)
    return row


# ---- the package --------------------------------------------------------------------
def upgrade_inspect(path):
    """What the package is, asked of otp_upgrade.py - the same check root
    makes again before putting it in."""
    if not UPGRADE_HELPER.exists():
        raise ValueError('otp_upgrade.py is not installed beside otp.py; upgrade once on the '
                         'command line (install.sh --upgrade)')
    try:
        r = subprocess.run([sys.executable, '-I', str(UPGRADE_HELPER), '--inspect', str(path)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        got = json.loads(r.stdout.decode('utf-8', 'replace') or '{}')
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        raise ValueError('the package could not be checked: %s' % e)
    if not got.get('ok'):
        raise ValueError(got.get('said') or 'the package was refused')
    return got


def upgrade_store_package(store, path, info, by):
    """The package into the database in pieces, the one before taken out."""
    raw = Path(path).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    text = base64.b64encode(raw).decode('ascii')
    pieces = [text[i:i + UPGRADE_PIECE] for i in range(0, len(text), UPGRADE_PIECE)]
    old = _meta_json(store, 'upgrade:pkg') or {}
    # Every other package's pieces out, not only the last one's (1.0.44).
    store.db.run("DELETE FROM meta WHERE k LIKE 'upgrade:piece:%' AND k NOT LIKE ?",
                 ('upgrade:piece:%s:%%' % sha[:16],))
    for i, one in enumerate(pieces):
        k = 'upgrade:piece:%s:%04d' % (sha[:16], i)
        if store.get_meta(k) is None:
            store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)', (k, one))
    meta = {'sha': sha, 'version': info['version'], 'bytes': len(raw), 'pieces': len(pieces),
            'signed_by': info.get('signed_by'), 'changelog': info.get('changelog', ''),
            'by': by, 'at': time.time()}
    store.set_meta('upgrade:pkg', json.dumps(meta))
    return meta


def upgrade_package_file(store, meta):
    """The package back out of the database, to the folder root takes it
    from - from the other node's database when this one has not all of it
    yet."""
    UPGRADE_DIR.mkdir(mode=0o750, exist_ok=True)
    out = UPGRADE_DIR / ('otp-%s.tar.gz' % meta['version'])

    def pieces_of(db):
        rows = db.rows("SELECT k, v FROM meta WHERE k LIKE ? ESCAPE '!' ORDER BY k",
                       ('upgrade:piece:%s:%%' % meta['sha'][:16],))
        return [r['v'] for r in rows]
    got = pieces_of(store.db)
    if len(got) != int(meta['pieces']) and CONFIG.get('ha_mode') == 'replicated':
        far = ha_peer_db()
        try:
            got = pieces_of(far)
        finally:
            far.close()
    if len(got) != int(meta['pieces']):
        raise ValueError('the package has not all arrived in this node\'s database')
    raw = base64.b64decode(''.join(got))
    if hashlib.sha256(raw).hexdigest() != meta['sha']:
        raise ValueError('the package in the database is damaged')
    tmp = out.with_suffix('.part')
    try:
        tmp.unlink()
    except OSError:
        pass
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw)
    os.replace(str(tmp), str(out))
    return out


# ---- the plan ------------------------------------------------------------------------
def upgrade_nodes_now(store):
    """The nodes an upgrade goes over: every one heard from lately, or this
    one alone."""
    nodes = [n for n in ha_nodes(store) if n.get('alive')]
    if not nodes:
        nodes = [{'name': node_name(), 'version': __version__, 'me': True, 'alive': True}]
    return nodes


def upgrade_plan(store):
    plan = _meta_json(store, 'upgrade:plan')
    if not plan:
        return None
    plan['steps'] = []
    plan['drain_s'] = UPGRADE_DRAIN_S
    for name in plan.get('order') or []:
        row = _meta_json(store, 'upgrade:node:' + name) or {}
        if row.get('id') != plan.get('id'):
            row = {'state': 'waiting'}
        row['name'] = name
        plan['steps'].append(row)
    states = [s.get('state') for s in plan['steps']]
    if any(s == 'failed' for s in states):
        plan['state'] = 'failed'
    elif states and all(s == 'done' for s in states):
        plan['state'] = 'done'
    elif plan.get('cancelled'):
        plan['state'] = 'cancelled'
    else:
        plan['state'] = 'running'
    return plan


def upgrade_checks(store, meta, pages=False):
    """What must be so before an upgrade starts - (ok, [why not]). A package
    to go back to (1.0.143) is looked at again as it was when it was taken."""
    why = []
    if not meta:
        return False, ['no package has been sent yet']
    down = bool(meta.get('downgrade'))
    if down:
        why += downgrade_why_not(store, meta['version'])
        if pages and not CONFIG.get('upgrade_downgrade'):
            # Switched off since it was fetched (1.0.146): not started from the pages.
            why.append('going back to an older version is switched off (Settings → Upgrades)')
    nodes = upgrade_nodes_now(store)
    for n in ha_nodes(store):
        if not n.get('alive'):
            why.append('%s has not been heard from for %d s - bring it back, or forget it '
                       '(Settings - High availability)' % (n['name'], int(n.get('age') or 0)))
    for n in nodes:
        have = str(n.get('version') or '')
        try:
            if have and not down and tuple(int(x) for x in have.split('.')) > \
                    tuple(int(x) for x in meta['version'].split('.')):
                why.append('%s runs %s, newer than %s' % (n['name'], have, meta['version']))
        except ValueError:
            pass
    if CONFIG.get('ha_mode') == 'replicated':
        rep = ha_repl_state(store)
        if not rep.get('healthy'):
            why.append('the replication is not running both ways - see Settings - High '
                       'availability')
    plan = upgrade_plan(store)
    if plan and plan['state'] == 'running':
        why.append('an upgrade is going on already')
    return not why, why


def upgrade_start(store, by, pages=False):
    meta = _meta_json(store, 'upgrade:pkg')
    ok, why = upgrade_checks(store, meta, pages)
    if not ok:
        raise ValueError('; '.join(why))
    names = [n['name'] for n in upgrade_nodes_now(store)]
    me = node_name()
    # The others first and this node last: the pages it shows stay up the
    # longest, and the first node is the one somebody can look at while it
    # is done.
    order = sorted(n for n in names if n != me) + ([me] if me in names else [])
    ident = '%d-%s' % (int(time.time()), secrets.token_hex(4))
    for name in order:
        k = 'upgrade:node:' + name
        if store.get_meta(k) is None:
            # Made here, for every node, before anything else: from then on
            # each node only UPDATEs its own.
            store.db.run('INSERT INTO meta (k, v) VALUES (?, ?)',
                         (k, json.dumps({'state': 'none'})))
    plan = {'id': ident, 'version': meta['version'], 'sha': meta['sha'], 'order': order,
            'by': by, 'at': time.time(), 'from': me, 'downgrade': bool(meta.get('downgrade'))}
    store.set_meta('upgrade:plan', json.dumps(plan))
    store.add_event('starting and stopping', '%s started %s %s: %s, one at a time' % (
        by, 'going back to' if plan['downgrade'] else 'the upgrade to', meta['version'],
        ', '.join(order)), 'warn', who=by)
    return upgrade_plan(store)


def upgrade_cancel(store, by):
    plan = _meta_json(store, 'upgrade:plan')
    if not plan:
        raise ValueError('no upgrade is going on')
    plan['cancelled'] = {'by': by, 'at': time.time()}
    store.set_meta('upgrade:plan', json.dumps(plan))
    _peer_update('upgrade:plan', json.dumps(plan))
    store.add_event('starting and stopping', '%s stopped the upgrade to %s: the nodes not '
                    'begun stay as they are' % (by, plan.get('version')), 'warn', who=by)


def _my_step(store, plan, **fields):
    k = 'upgrade:node:' + node_name()
    row = _meta_json(store, k) or {}
    if row.get('id') != plan['id']:
        row = {'id': plan['id']}
    row.update(fields)
    row['at'] = time.time()
    _row_write(store, k, row, mine=False)
    return row


def _helper_status():
    try:
        fd = os.open(str(UPGRADE_DIR / 'status.json'), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as f:
            return json.loads(f.read(1 << 20).decode('utf-8'))
    except (OSError, ValueError):
        return {}


def upgrade_log_tail(lines=200):
    try:
        fd = os.open(str(UPGRADE_DIR / 'last.log'), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as f:
            text = f.read(4 << 20).decode('utf-8', 'replace')
        return text.splitlines()[-lines:]
    except OSError:
        return []


def upgrade_tick(daemon):
    """This node's part of the plan, every few seconds."""
    store = daemon.store
    if HA_REBUILDING.is_set():
        return
    plan = upgrade_plan(store)
    # A cancelled plan is still finished where a node has begun (1.0.44):
    # one that drains goes back into service, one that installs is checked
    # and comes back - it never stays in maintenance for good.
    if plan and plan['state'] == 'failed':
        _back_after_marked(store, plan)
    if not plan or plan['state'] not in ('running', 'cancelled'):
        return
    me = node_name()
    if store.get_meta('upgrade:node:' + me) is None:
        return                          # its row has not come over from the other node yet
    steps = plan['steps']
    turn = next((s for s in steps if s.get('state') != 'done'), None)
    if turn and turn['name'] != me and turn.get('state') in ('draining', 'installing',
                                                             'checking'):
        # The node whose turn it is gone for longer than an upgrade takes
        # (1.0.59): marked failed from here, or the plan ran for ever and
        # stopped every new upload and start until somebody cancelled it.
        alive = any(n.get('name') == turn['name'] and n.get('alive')
                    for n in ha_nodes(store))
        if not alive and now_minus(turn.get('at')) > UPGRADE_TIMEOUT_S + 300 and \
                not _peer_still_at_it(turn):
            row = dict(turn)
            row.pop('name', None)
            row.update({'state': 'failed', 'at': time.time(), 'marked_by': me,
                        'said': 'not heard from for %d min while %s - marked failed by %s'
                                % (UPGRADE_TIMEOUT_S // 60 + 5, turn.get('state'), me)})
            try:
                _row_write(store, 'upgrade:node:' + turn['name'], row, mine=False)
                store.add_event('starting and stopping', 'the upgrade of %s to %s failed: '
                                'the node has not been heard from' % (turn['name'],
                                                                      plan['version']), 'bad')
            except Exception as e:                      # noqa: BLE001
                log('the upgrade of %s could not be marked failed: %s' % (turn['name'], e),
                    'warn')
        return
    if not turn or turn['name'] != me:
        return
    state = turn.get('state')
    now = time.time()
    if plan.get('cancelled') and state in ('waiting', 'none', None, 'cancelled'):
        return
    if plan.get('cancelled') and state == 'draining':
        if not turn.get('was_maint'):
            maintenance_set(store, False, by=plan.get('by') or '')
        _my_step(store, plan, state='cancelled', said='cancelled before it was installed; '
                 'back in service')
        return
    if state in ('waiting', 'none', None) and len(steps) > 1:
        # Never both out at once (1.0.44): the others have to be alive and
        # in service before this one leaves.
        for n in ha_nodes(store):
            if n['name'] == me or n['name'] not in [x['name'] for x in steps]:
                continue
            if not n.get('alive') or maintenance_row(store, n['name']).get('on'):
                if turn.get('said') != 'waiting for %s to be in service' % n['name']:
                    _my_step(store, plan, state='waiting',
                             said='waiting for %s to be in service' % n['name'])
                return
    if state in ('waiting', 'none', None):
        was = maintenance_row(store)
        alone = len(steps) == 1
        maintenance_set(store, True, 'upgrade to %s' % plan['version'], plan.get('by') or '')
        _my_step(store, plan, state='draining', was_maint=bool(was.get('on')),
                 began=now, said='in maintenance; the balancer and the VPN go to the other '
                 'node' if not alone else 'in maintenance')
        if not alone:
            return
        state = 'draining'
        turn = _meta_json(store, 'upgrade:node:' + me)
    if state == 'draining':
        if len(steps) > 1 and now - float(turn.get('at') or 0) < UPGRADE_DRAIN_S:
            return
        meta = _meta_json(store, 'upgrade:pkg') or {}
        try:
            if meta.get('sha') != plan['sha']:
                raise ValueError('the package in the database is not the one this upgrade '
                                 'was started with')
            path = upgrade_package_file(store, meta)
            req = {'id': plan['id'], 'file': path.name, 'sha': plan['sha'],
                   'version': plan['version'], 'by': plan.get('by'), 'at': now,
                   'downgrade': bool(plan.get('downgrade'))}
            tmp = UPGRADE_DIR / 'request.part'
            try:
                tmp.unlink()
            except OSError:
                pass
            fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
            with os.fdopen(fd, 'w') as f:
                json.dump(req, f)
            os.replace(str(tmp), str(UPGRADE_DIR / 'request.json'))
        except Exception as e:                          # noqa: BLE001
            _upgrade_failed(store, plan, turn, 'the package could not be handed over: %s' % e)
            return
        _my_step(store, plan, state='installing', asked=now,
                 said='handed to root (otp-upgrade.service)')
        log('the upgrade to %s is handed to otp-upgrade.service' % plan['version'])
        return
    if state == 'installing':
        if __version__ == plan['version'] and float(daemon.started or 0) > \
                float(turn.get('asked') or 0):
            _my_step(store, plan, state='checking', said='restarted as %s' % __version__)
            state = 'checking'
            turn = _meta_json(store, 'upgrade:node:' + me)
        else:
            got = _helper_status()
            if got.get('id') == plan['id'] and got.get('state') == 'failed':
                _upgrade_failed(store, plan, turn, got.get('said') or
                                'install.sh ended with %s' % got.get('rc'),
                                tail=got.get('tail'))
                return
            if not (UPGRADE_DIR / 'request.json').exists() and \
                    not (UPGRADE_DIR / 'request.taken').exists() and \
                    got.get('id') != plan['id'] and now - float(turn.get('asked') or now) > 120:
                _upgrade_failed(store, plan, turn, 'otp-upgrade.service never took the request '
                                '- is otp-upgrade.path installed and running? (install.sh '
                                '--upgrade once on the command line puts it in)')
                return
            if now - float(turn.get('asked') or now) > UPGRADE_TIMEOUT_S:
                _upgrade_failed(store, plan, turn, 'it has not come back as %s in %d min'
                                % (plan['version'], UPGRADE_TIMEOUT_S // 60))
                return
            # How far install.sh is (1.0.67): its sections, "==> ...", for the
            # bar on the pages - written when one more has begun.
            if got.get('id') == plan['id'] and got.get('state') == 'running':
                parts = [x[4:].strip() for x in upgrade_log_tail(400) if x.startswith('==> ')]
                if parts and len(parts) != int(turn.get('part') or 0):
                    _my_step(store, plan, part=len(parts), part_words=parts[-1][:120],
                             asked=turn.get('asked'))
            return
    if state == 'checking':
        trouble = []
        try:
            store.db.value('SELECT 1')
        except Exception as e:                          # noqa: BLE001
            trouble.append('the database: %s' % e)
        if not getattr(getattr(daemon, 'radius', None), 'bound', None):
            trouble.append('RADIUS is not listening')
        got = _helper_status()
        if got.get('id') == plan['id'] and got.get('state') == 'running':
            if now - float(turn.get('at') or now) < 600:
                return                  # install.sh is still finishing (the firewall, its checks)
            # Not done just because it took long (1.0.44).
            trouble.append('install.sh has not said it finished in 10 min (see '
                           'journalctl -u otp-upgrade)')
        if got.get('id') == plan['id'] and got.get('state') == 'failed':
            trouble.append(got.get('said') or 'install.sh ended with %s' % got.get('rc'))
        if CONFIG.get('ha_mode') == 'replicated':
            ha_refresh_tables(store)
        if trouble:
            _upgrade_failed(store, plan, turn, '; '.join(trouble), tail=got.get('tail'))
            return
        if not turn.get('was_maint'):
            maintenance_set(store, False, by=plan.get('by') or '')
        _my_step(store, plan, state='done', said='%s, checked, back in service' % __version__,
                 tail=(got.get('tail') or [])[-12:])
        store.add_event('starting and stopping', '%s is upgraded to %s' % (me, __version__))
        log('upgraded to %s and back in service' % __version__)
        if all((s.get('state') == 'done') or s['name'] == me for s in steps):
            store.add_event('starting and stopping', 'the upgrade to %s is done on every node'
                            % plan['version'])


def _peer_still_at_it(turn):
    """Its own row read in its own database (1.0.61): while it runs the new
    version, what it writes does not come over to this one - its heartbeat
    looks stale, and a node that was fine was marked failed."""
    try:
        far = ha_peer_db()
    except Exception:                                   # noqa: BLE001
        return False                    # not reachable either: gone indeed
    try:
        row = json.loads(far.value('SELECT v FROM meta WHERE k = ?',
                                   ('upgrade:node:' + turn['name'],)) or '{}')
        beat = json.loads(far.value('SELECT v FROM meta WHERE k = ?',
                                    ('node:' + turn['name'],)) or '{}')
        return row.get('state') == 'done' or now_minus(row.get('at')) < 600 or \
            now_minus(beat.get('at')) < 120
    except Exception:                                   # noqa: BLE001
        return False
    finally:
        try:
            far.close()
        except Exception:                               # noqa: BLE001
            pass


def _back_after_marked(store, plan):
    """A node the other one marked failed while it drained, come back on
    its old version (1.0.61): taken out of the maintenance the upgrade put
    it in, once - nothing else would."""
    me = node_name()
    row = _meta_json(store, 'upgrade:node:' + me) or {}
    if row.get('id') != plan.get('id') or row.get('state') != 'failed' or \
            not row.get('marked_by') or row.get('back') or __version__ == plan.get('version'):
        return
    if not row.get('was_maint'):
        try:
            maintenance_set(store, False, by=plan.get('by') or '')
        except Exception:                               # noqa: BLE001
            return
    row['back'] = True
    try:
        _row_write(store, 'upgrade:node:' + me, row, mine=False)
    except Exception:                                   # noqa: BLE001
        pass
    log('back in service: the upgrade had been marked failed by %s while this node waited'
        % row.get('marked_by'), 'warn')


def now_minus(at):
    try:
        return time.time() - float(at or time.time())
    except (TypeError, ValueError):
        return 0.0


def _upgrade_failed(store, plan, turn, said, tail=None):
    # Already running the new version and its checks failed (1.0.59): kept
    # in maintenance - it is the broken version that would be put in service.
    # Only once it has started again as that version (1.0.61): the same
    # version put in again, failing before anything was installed, left a
    # working node out.
    broken_new = __version__ == plan.get('version') and turn.get('state') == 'checking'
    if broken_new:
        said = '%s - left in maintenance: it runs %s, which did not pass its checks' % (
            said, __version__)
    _my_step(store, plan, state='failed', said=str(said)[:500], tail=(tail or [])[-40:])
    # Back in service where it still runs as it did: a failed upgrade must
    # not leave a working node out.
    if not turn.get('was_maint') and not broken_new:
        try:
            maintenance_set(store, False, by=plan.get('by') or '')
        except Exception:                               # noqa: BLE001
            pass
    store.add_event('starting and stopping', 'the upgrade of %s to %s failed: %s'
                    % (node_name(), plan['version'], said), 'bad')
    log('the upgrade to %s failed: %s' % (plan['version'], said), 'error')


def ha_refresh_tables(store):
    """The list of tables taken from the other node read again, here and
    there: a version that adds a table needs it, and it costs nothing when
    none was added. Where the other node does not have the table yet (it
    is still the older version) its half fails, and it is done again when
    that node comes back upgraded."""
    try:
        ha_control(store, 'refresh', by='the upgrade')
    except Exception as e:                              # noqa: BLE001
        log('reading the tables of the other node again: %s' % e, 'warn')
    slot = int(CONFIG.get('ha_slot') or 1)
    try:
        far = ha_peer_db()
        try:
            far.run('ALTER SUBSCRIPTION %s REFRESH PUBLICATION WITH (copy_data = false)'
                    % ha_sub_here(far, slot))
        finally:
            far.close()
    except Exception as e:                              # noqa: BLE001
        log('the other node could not read this one\'s tables again yet: %s'
            % str(e).split('\n')[0][:200], 'info')
