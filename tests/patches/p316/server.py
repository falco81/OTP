"""1.0.316 (parts): no address of the Teltonika gateway set is said as the administrator's to fix (400), not
as the gateway failing (502)."""
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


edit('90_api.py', [
("""        h.me('fulladmin')
        try:
            pem = tel_peer_chain()
        except SmsError as e:
            raise ApiError(502, str(e))
""",
 """        h.me('fulladmin')
        if not str(CONFIG.get('sms_tel_host') or '').strip().rstrip('/'):
            # Nothing to ask (1.0.316): the administrator's to put in, not the gateway failing.
            raise ApiError(400, 'no address of the Teltonika gateway is set')
        try:
            pem = tel_peer_chain()
        except SmsError as e:
            raise ApiError(502, str(e))
"""),
])
