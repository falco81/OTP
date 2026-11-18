"""1.0.311 (web, OUTDIR): the HA pane's balancer helper knows the certificate sign-in's own port."""
import sys, pathlib
OUT = pathlib.Path(sys.argv[1])
PARTS = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None


def edit(path, pairs):
    p = pathlib.Path(path)
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (str(p), n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


if PARTS:
    edit(PARTS / '90_api.py', [
("""                          'port': int(CONFIG.get('web_proxy_port') or 0)},
            'access': access,""",
 """                          'port': int(CONFIG.get('web_proxy_port') or 0)},
            # The certificate sign-in's own port, when it is on (1.0.311): the guides offered 8443 for
            # the balancer - the same port, refused by the nodes, and a balancer configured by them
            # would have published the sign-in with a card.
            'cert_port': int(CONFIG.get('admin_cert_port') or 8443) if CONFIG.get('admin_cert') else 0,
            'access': access,"""),
])

edit(OUT / 'web/assets/admin.js', [
("""    pp: LB_UI.pp || String(wp.port || 8443), hc: LB_UI.hc || '/healthz'};""",
 """    pp: LB_UI.pp || String(wp.port || lbPortSay(lb)), hc: LB_UI.hc || '/healthz'};"""),
("""    var pp = parseInt(LB_UI.pp || v0.pp, 10) || 8443;""",
 """    var pp = parseInt(LB_UI.pp || v0.pp, 10) || lbPortSay(lb);"""),
("""    if (!set.ok) trust.appendChild(lbBlock(set.line, v, ''));""",
 """    /* The certificate sign-in's own port (1.0.311): not the balancer's - the nodes refuse it, and a
       balancer sent there would publish the sign-in with a card. */
    if (lb.cert_port && v.pp === lb.cert_port && v.layer !== 'snat') {
      note('bad', 'Port ' + v.pp + ' is the certificate sign-in\\'s own port (admin_cert_port): the nodes refuse it for the balancer, and a balancer sent there would publish the sign-in with a card to everybody - give the balancer another port (' + (v.pp === 9443 ? 8443 : 9443) + ', say).');
    }
    if (!set.ok) trust.appendChild(lbBlock(set.line, v, ''));"""),
("""function drawHaLb(d) {""",
 """/* The balancer's port offered (1.0.311): 8443, or 9443 when the certificate sign-in has 8443. */
function lbPortSay(lb) { return lb && lb.cert_port === 8443 ? 9443 : 8443; }
function drawHaLb(d) {"""),
])

edit(OUT / 'docs/load-balancers.md', [
("""8443; another port needs `semanage port -a -t http_port_t -p tcp PORT`.""",
 """8443; another port needs `semanage port -a -t http_port_t -p tcp PORT`.
With the sign-in by a certificate or a smart card on (`admin_cert`), its own port
(`admin_cert_port`, 8443 by default) is not the balancer's: the nodes refuse the same
port for both, and a balancer sent to it would publish that sign-in - give the
balancer another one (9443, say, with the `semanage` line above); the guides in
Settings → High availability offer it by themselves."""),
])
print('ok')
