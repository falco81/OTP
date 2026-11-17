# 1.0.296: bug fixes - the RADIUS counters (counted once the answer is decided, under a lock),
# the periodic report given back when its mail did not go.   python3 server.py PARTS
import re
import sys
P = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(P + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(P + f, 'w').write(s)


edit('70_radius_server.py', [
("""        if d.result == 'accept':
            self.counts['accept'] += 1
            code = ACCESS_ACCEPT""", """        if d.result == 'accept':
            code = ACCESS_ACCEPT"""),
("""            # the code, and the words it shows. Nothing that lets in.
            self.counts['challenge'] += 1
            code = ACCESS_CHALLENGE""", """            # the code, and the words it shows. Nothing that lets in.
            code = ACCESS_CHALLENGE"""),
("""        else:
            self.counts['reject'] += 1
            code = ACCESS_REJECT
            # The reason is cut by bytes""", """        else:
            code = ACCESS_REJECT
            # The reason is cut by bytes"""),
("""            if code == ACCESS_ACCEPT:
                self.counts['accept'] -= 1
                self.counts['reject'] += 1
                d.refuse(""", """            if code == ACCESS_ACCEPT:
                d.refuse("""),
("""        took = int((time.time() - arrived) * 1000)
""", """        # Counted once, as it goes out (1.0.296): an Accept too long to send was counted and
        # taken back, and a counter of /metrics went down - a reset to Prometheus.
        self.count({ACCESS_ACCEPT: 'accept', ACCESS_CHALLENGE: 'challenge'}.get(code, 'reject'))
        took = int((time.time() - arrived) * 1000)
"""),
("""        self.counts = collections.Counter()
        self.bound = []""", """        self.counts = collections.Counter()
        # Every worker counts (1.0.296): `+= 1` from several threads lost some, and /metrics read
        # the Counter while a new key went in.
        self.counts_lock = threading.Lock()
        self.bound = []"""),
("""    def state(self):
        return {'listening': self.bound, 'trouble': self.trouble, 'counts': dict(self.counts),""",
 """    def count(self, k, n=1):
        with self.counts_lock:
            self.counts[k] += n

    def state(self):
        with self.counts_lock:
            counts = dict(self.counts)
        return {'listening': self.bound, 'trouble': self.trouble, 'counts': counts,"""),
])
s = open(P + '70_radius_server.py').read()
s, n = re.subn(r"self\.counts\['([a-z_]+)'\] \+= 1", r"self.count('\1')", s)
assert n >= 15, n
assert s.count('self.counts[') == 1, s.count('self.counts[')
open(P + '70_radius_server.py', 'w').write(s)

edit('88z_alerts.py', [
("""            if CONFIG.get('report') and report_due():
                since, until, pid = report_period()
                was_sent = store.get_meta('report:sent')
                if was_sent != pid and claim_once(store, 'report:sent', pid):
                    try:
                        report_send(store, since, until, reader=daemon.reader())
                    except Exception as e:      # noqa: BLE001""",
 """            if CONFIG.get('report') and report_due() and \\
                    time.monotonic() - float(ALERT_WORK.get('report_fail') or -1e9) > 1800:
                since, until, pid = report_period()
                was_sent = store.get_meta('report:sent')
                if was_sent != pid and claim_once(store, 'report:sent', pid):
                    try:
                        entry = report_send(store, since, until, reader=daemon.reader())
                        # Its mail did not go and is not waiting for another try (1.0.296): mail
                        # off, or refused for good - the period given back and tried again in
                        # 30 min; it was kept as sent and that report never went.
                        if not entry.get('ok') and entry.get('queued') != 'waiting':
                            ALERT_WORK['report_fail'] = time.monotonic()
                            if store.get_meta('report:sent') == pid:
                                store.set_meta('report:sent', was_sent or '')
                            log_sparing('report-fail', 'the report did not go: %s'
                                        % entry.get('said'), 'warn', every=3600)
                    except Exception as e:      # noqa: BLE001"""),
])
print('ok')
