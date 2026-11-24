"""1.0.335 (parts): a network change of a node in a cluster whose VIP is IPv6 no longer refused."""
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
("""        if vnet and vnet.ip not in a4.network and not want.get('vip_elsewhere'):
""",
 """        # An IPv4 VIP against the IPv4 network (1.0.335): an IPv6 one is in no IPv4 network, and
        # every change of the network of every node was refused.
        if vnet and vnet.version == 4 and vnet.ip not in a4.network and not want.get('vip_elsewhere'):
"""),
])
