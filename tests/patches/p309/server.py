# 1.0.309: time and the VIP address (hunt round 8) - the clock guard times its own work by a clock that is
# not stepped; whether the other node beats, read in its database, is judged by that machine's own clock;
# keepalived's check takes no word dated ahead; the sign-in pages' tidying never ends a RADIUS guard's
# block early.   python3 server.py PARTS OUTDIR
import sys
P = sys.argv[1].rstrip('/') + '/'
O = sys.argv[2].rstrip('/') + '/'


def edit(f, pairs, base=P):
    s = open(base + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(base + f, 'w').write(s)


edit('87z_clock.py', [
("""def clock_step(store, now=None, ref=None, skew=None, dir_ok=None, peer=None):
    \"\"\"One look. `ref`, `skew`, `dir_ok`, `peer` given only by the tests.\"\"\"""",
 """def clock_step(store, now=None, ref=None, skew=None, dir_ok=None, peer=None):
    \"\"\"One look. `ref`, `skew`, `dir_ok`, `peer` given only by the tests.\"\"\"
    # Its own work timed by a clock that is not stepped (1.0.309): the wall clock is what it watches -
    # stepped back 5 min, nothing was written nor the directory asked for 5 min, and the last row
    # ("aside", dated ahead) was read as fresh by the other node all that while.
    mark = time.monotonic() if now is None else now"""),
("""    elif CONFIG.get('health_dir') and now - CLOCK['dir_at'] > CLOCK_DIR_EVERY_S:
        ok, dirs = clock_dir_check(store)
        CLOCK.update(dir_ok=ok, dirs=dirs, dir_at=now)""",
 """    elif CONFIG.get('health_dir') and (mark - CLOCK.get('dir_mark', -1e12) > CLOCK_DIR_EVERY_S or
                                       mark < CLOCK.get('dir_mark', -1e12)):
        ok, dirs = clock_dir_check(store)
        CLOCK.update(dir_ok=ok, dirs=dirs, dir_at=now, dir_mark=mark)"""),
("""    if now - CLOCK['written'] > 10:
        CLOCK['written'] = now""",
 """    if mark - CLOCK.get('written_mark', -1e12) > 10 or mark < CLOCK.get('written_mark', -1e12):
        CLOCK['written'] = now
        CLOCK['written_mark'] = mark"""),
])

edit('88_upgrade.py', [
("""            beat = json_obj(far.value('SELECT v FROM meta WHERE k = ?', ('node:' + name,)))
            at = (beat or {}).get('at')
            # No heartbeat there, or none that reads, is not alive (1.0.271): it was taken as
            # beating just now, and while node1 was rebuilt nobody led (no alerts, no claims).
            alive = isinstance(at, (int, float)) and not isinstance(at, bool) and \\
                now_minus(at) < 120""",
 """            beat = json_obj(far.value('SELECT v FROM meta WHERE k = ?', ('node:' + name,)))
            at = (beat or {}).get('at')
            # No heartbeat there, or none that reads, is not alive (1.0.271): it was taken as
            # beating just now, and while node1 was rebuilt nobody led (no alerts, no claims).
            # Judged by that machine's own clock (1.0.309): the heartbeat is written there, and the
            # database answering is there too - this node's clock 2 min ahead took it for gone.
            there = peer_db_now(far)
            alive = isinstance(at, (int, float)) and not isinstance(at, bool) and \\
                ((there - float(at)) if there else now_minus(at)) < 120"""),
("""def _peer_still_at_it(turn):""",
 """def peer_db_now(far):
    \"\"\"The time by the clock of the machine the other node's database is on (1.0.309), or None.\"\"\"
    try:
        if getattr(far, 'engine', '') == 'postgres':
            v = far.value('SELECT EXTRACT(EPOCH FROM now())')
            return float(v) if v is not None else None
    except Exception:                                   # noqa: BLE001
        return None
    return None


def _peer_still_at_it(turn):"""),
])

edit('90_api.py', [
("""                keep_s = max(span, 6 * 3600)
                for k in [k for k, v in fl.items() if not v or t - v[-1] > keep_s]:
                    fl.pop(k, None)
                    self.d.login_info.pop(k, None)""",
 """                keep_s = max(span, 6 * 3600)
                info = self.d.login_info
                # Never a place still blocked (1.0.309): RADIUS's guard keeps its blocks in the same
                # maps, for up to a week - tidied after 6 h of quiet, a block ended early.
                held = lambda k: fnum((info.get(k) or {}).get('blocked_until')) > t
                for k in [k for k, v in fl.items() if (not v or t - v[-1] > keep_s) and not held(k)]:
                    fl.pop(k, None)
                    info.pop(k, None)"""),
("""                    for k in order[:len(fl) // 2]:
                        if k not in keys:
                            fl.pop(k, None)
                            self.d.login_info.pop(k, None)""",
 """                    for k in order[:len(fl) // 2]:
                        if k not in keys and not held(k):
                            fl.pop(k, None)
                            self.d.login_info.pop(k, None)"""),
])

edit('deploy/otp-vip-check', [
("""    [ $((now - at)) -le 10 ] || exit 1""",
 """    [ $((now - at)) -le 10 ] || exit 1
    # Not dated ahead (1.0.309): after the clock was stepped back, a daemon hung but alive kept the
    # address for as long as the step.
    [ $((now - at)) -ge -2 ] || exit 1"""),
], base=O)
print('ok')
