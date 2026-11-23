"""1.0.326 (parts): a host name of more than 64 characters refused on the page."""
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


edit('87n_net.py', [
("""        raise ValueError('the host name is the whole name: otp1.example.cz')
    old_ip = net_current_ip(now).split('/')[0]
""",
 """        raise ValueError('the host name is the whole name: otp1.example.cz')
    if len(host) > 64 and not same:
        raise ValueError('the host name is the whole name, 64 characters at most')   # (1.0.326)
    old_ip = net_current_ip(now).split('/')[0]
"""),
])
