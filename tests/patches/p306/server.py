# 1.0.306: mail, alerts and SNMP (hunt round 5) - an alert or report that reached some of its recipients
# is sent, not mailed again every 15-30 min; "Who was refused" counts refusals, not challenges; SNMP's
# clock values and the time of the last backup kept in an Integer32.   python3 server.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('88z_alerts.py', [
("""    except Exception as e:                              # noqa: BLE001 - not a MailError alone (1.0.287)
        # Waiting for another try in the outgoing mail is sent as far as the
        # alerts go: it is not made again every minute.
        entry.update(ok=False, said=str(e)[:200], queued=getattr(e, 'queued', '') or '')""",
 """    except Exception as e:                              # noqa: BLE001 - not a MailError alone (1.0.287)
        # Waiting for another try in the outgoing mail is sent as far as the
        # alerts go: it is not made again every minute.
        left = getattr(e, 'left', None)
        if isinstance(left, list) and to and len(left) < len(to):
            # Some took it, the rest refused for good (1.0.306): sent - the same alert went to
            # every recipient again every 15 min, the report every 30, for as long as one
            # address was gone.
            entry.update(said='not delivered to %s: %s' % (', '.join(left)[:200], str(e)[:200]),
                         partial=True)
        else:
            entry.update(ok=False, said=str(e)[:200], queued=getattr(e, 'queued', '') or '')"""),
("""        "AND ts < ? AND packet = 'Access-Request' AND result <> 'accept' AND result <> 'acct' "
        "GROUP BY username ORDER BY n DESC LIMIT 15", (since, until))""",
 """        "AND ts < ? AND packet = 'Access-Request' AND result IN ('reject', 'drop') "
        "GROUP BY username ORDER BY n DESC LIMIT 15", (since, until))"""),
("""        r = db.rows("SELECT reason FROM radius_log WHERE username = ? AND ts >= ? AND ts < ? AND "
                    "result <> 'accept' ORDER BY ts DESC LIMIT 1", (u['who'], since, until))""",
 """        # A refusal, not the challenge of a sign-in in two windows (1.0.306): every user of a
        # challenge realm was listed, as many times as they signed in.
        r = db.rows("SELECT reason FROM radius_log WHERE username = ? AND ts >= ? AND ts < ? AND "
                    "result IN ('reject', 'drop') ORDER BY ts DESC LIMIT 1", (u['who'], since, until))"""),
])

edit('90s_snmp.py', [
("""            (B + (2, 0), 'int', int(last)), (B + (3, 0), 'gauge', _sn_g(now - last) if last else SNMP_MIB_GAUGE_MAX),""",
 """            (B + (2, 0), 'int', _sn_i32(last)), (B + (3, 0), 'gauge', _sn_g(now - last) if last else SNMP_MIB_GAUGE_MAX),"""),
("""            (B + (3, 0), 'int', int(round(float(ref) * 1000)) if isinstance(ref, (int, float)) else 0),
            (B + (4, 0), 'int', int(round(float(skew) * 1000)) if isinstance(skew, (int, float)) else 0),
            (B + (5, 0), 'int', int(round(float(c.get('correction') or 0) * 1000)))]""",
 """            (B + (3, 0), 'int', _sn_i32(float(ref) * 1000) if isinstance(ref, (int, float)) else 0),
            (B + (4, 0), 'int', _sn_i32(float(skew) * 1000) if isinstance(skew, (int, float)) else 0),
            (B + (5, 0), 'int', _sn_i32(float(c.get('correction') or 0) * 1000))]


def _sn_i32(v):
    \"\"\"An Integer32 (1.0.306): a clock months off (ms) or a time after 2038 was 5-6 bytes, and a
    strict manager refused the whole answer - when it mattered most.\"\"\"
    try:
        return max(-2 ** 31, min(2 ** 31 - 1, int(round(float(v)))))
    except (TypeError, ValueError, OverflowError):
        return 0"""),
])
edit('70_radius_server.py', [
("""                    def remember(b, key=key):
                        # The answer kept for a repeat the moment it is sent
                        # (1.0.101), not after it is written down: a repeat
                        # coming meanwhile got nothing.
                        with self.seen_lock:
                            if key in seen:
                                seen[key] = (arrived, b)""",
 """                    def remember(b, until=0, key=key):
                        # The answer kept for a repeat the moment it is sent
                        # (1.0.101), not after it is written down: a repeat
                        # coming meanwhile got nothing.
                        with self.seen_lock:
                            if key in seen:
                                seen[key] = (arrived, b, until)"""),
("""            reply.late = True
            reply.late_until = time.time() + min(delay, 10000) / 1000.0
            self.later(min(delay, 10000) / 1000.0, sock, bytes(reply), peer)""",
 """            reply.late = True
            reply.late_until = time.time() + min(delay, 10000) / 1000.0
            # Kept for a repeat now, with when it may go (1.0.306): kept only after it was written
            # down, a repeat coming once the late refusal went - the database slower than the
            # delay - found nothing and was swallowed as "repeated": the NAS got no answer.
            if remember is not None:
                remember(bytes(reply), reply.late_until)
            self.later(min(delay, 10000) / 1000.0, sock, bytes(reply), peer)"""),
])
print('ok')
