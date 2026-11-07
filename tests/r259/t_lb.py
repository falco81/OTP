"""t_lb.py - 1.0.259, the load balancer: the layer switch (L7, L4 with the PROXY protocol, L4 without a
client address) on every kind that can do it, the enrolment pages alone through the balancer (an exact
list of paths), the client's address put in and never added to, no secret in any text; the nodes' own
port for the balancer (web_proxy_port): its server written by otp_web.py from a sample otp.conf
(the PROXY protocol, X-Forwarded-For, the allow list and the sign-in by the balancer carried over,
nothing but the enrolment pages, nginx -t on a scratch copy with unix sockets - no port bound), the
realip lines of 443 left out with the PROXY protocol, the firewall opening it from the balancers only,
the settings (default, range, name, help, group, depends, the checks), lb_facts, the SSO card's guides,
docs, install.sh, the Czech. Pure Python + node: no daemon, no ports, no database.

    cd /tmp && python3 t_lb.py 1.0.259
"""
import ast, ipaddress, json, os, re, shutil, subprocess, sys, tempfile, importlib.util
from pathlib import Path

VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.259'
BUILD = '/home/claude/build'
PARTS = BUILD + '/parts'
OUT = '%s/out/otp-%s' % (BUILD, VER)
R = []


def ok(n, c, m=''):
    R.append(bool(c))
    print(('ok  ' if c else 'FAIL') + ' ' + n + ('' if c else ' ' + str(m)[:500]))


def src_of(fname):
    return open(os.path.join(PARTS, fname), encoding='utf-8').read()


def defs(fname, names):
    text = src_of(fname)
    tree = ast.parse(text)
    lines = text.splitlines(True)
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            out.append(''.join(lines[node.lineno - 1:node.end_lineno]))
    missing = set(names) - set(re.findall(r'^(?:def|class) (\w+)', ''.join(out), re.M))
    assert not missing, missing
    return '\n\n'.join(out)


TMP = Path(tempfile.mkdtemp(prefix='t_lb_', dir='/tmp/claude-0' if os.path.isdir('/tmp/claude-0') else None))
JS = open(OUT + '/web/assets/admin.js', encoding='utf-8').read()

# ---- the generated texts, per kind and layer (node runs admin.js's own code) -------------------
a = JS.index('function lbServers(v, fmt)')
b = JS.index('function drawHaLb(d)')
lbcode = JS[a:b]
SECRET = 'S3cr3t-must-never-appear'
runner = TMP / 'gen.js'
runner.write_text(lbcode + r'''
var LB_UI = {secret: "%s"};
function sub(t, v) { return t.replace(/\{([a-z0-9_]+)\}/g, function (m, k) { return v[k] !== undefined ? String(v[k]) : m; }); }
var nodes = [{name: 'otp1', address: '192.0.2.11'}, {name: 'otp2', address: '192.0.2.12'}];
var out = {};
['l7', 'l4', 'snat'].forEach(function (layer) {
  var v = {lb: '192.0.2.5', src: '192.0.2.6', name: 'otp.example.cz', hc: '/healthz', layer: layer, pp: 8443,
           secret: LB_SECRET, auth: 1812, acct: 1813, nodes: nodes, xffh: 'X-Forwarded-For',
           wp: {on: false, from: [], header: 'X-Forwarded-For', recursive: true, port: 0}};
  v.np = layer === 'snat' ? 443 : 8443;
  nodes.forEach(function (n, i) { v['n' + i] = n.name; v['a' + i] = n.address; });
  LB_GUIDES.forEach(function (g) {
    var k = g[0] + ':' + layer;
    if (g[3] && g[3].indexOf(layer) < 0) { out[k] = null; return; }
    out[k] = g[4](v).map(function (p) { return [sub(p[0], v), sub(p[1], v)]; });
  });
  out['set:' + layer] = lbSetLine(v);
});
out.re = LB_PORTAL_RE;
out.kinds = LB_GUIDES.map(function (g) { return [g[0], g[3]]; });
var wpOk = {on: true, from: ['192.0.2.6/32'], header: 'proxy_protocol', recursive: false, port: 8443};
out.setok = lbSetLine({src: '192.0.2.6', layer: 'l4', xffh: 'X-Forwarded-For', pp: 8443, wp: wpOk}).ok;
out.ipin = [lbIpIn('10.1.2.3', '10.0.0.0/8'), lbIpIn('192.0.2.6', '192.0.2.0/24'), lbIpIn('192.0.3.6', '192.0.2.0/24'),
            lbIpIn('2001:db8::1', '2001:db8::1/128')];
console.log(JSON.stringify(out));
''' % SECRET)
got = subprocess.run(['node', str(runner)], capture_output=True, text=True)
ok('the guides run in node', got.returncode == 0, got.stderr[-400:])
G = json.loads(got.stdout or '{}')


def text_of(k):
    return '\n'.join(p[0] + '\n' + p[1] for p in (G.get(k) or []))


everything = json.dumps(G)
ok('no secret in any generated text, the placeholder in its place', SECRET not in everything and '<the shared secret>' in text_of('asa:l7') and '<the shared secret>' in text_of('forti:l7'))
ok('the RADIUS secret field is gone from the page (no maskBox, LB_SECRET constant)',
   "key === 'secret' ? maskBox" not in JS and "var LB_SECRET = '<the shared secret>';" in JS and "field('RADIUS shared secret'" not in JS)
RX = re.compile(G['re'])
good = ['/', '/index.php', '/favicon.ico', '/assets/core.js', '/assets/portal.js', '/assets/i18n.js', '/assets/otp.css',
        '/assets/favicon.svg', '/assets/apple-touch-icon.png', '/apple-touch-icon.png', '/apple-touch-icon-precomposed.png',
        '/apple-touch-icon-180x180.png']
bad = ['/admin/', '/admin', '//admin/', '/assets/../admin/', '/assets/%2e%2e/admin/', '/metrics', '/healthz', '/api/health',
       '/assets/admin.js', '/otp-api.php', '/lang/cs.json', '/.well-known/acme-challenge/x', '/index.php/../admin/', '/x']
ok('the portal regex: every path the enrolment pages need', all(RX.match(p) for p in good), [p for p in good if not RX.match(p)])
ok('the portal regex: nothing else (the administration, //admin, dot segments, /metrics, /healthz)', not any(RX.match(p) for p in bad), [p for p in bad if RX.match(p)])
kinds = dict((k, l) for k, l in G['kinds'])
for k in ('haproxy', 'nginx', 'f5', 'netscaler'):
    ok('%s: L7, L4 PROXY and L4 without an address offered' % k, kinds.get(k) == ['l7', 'l4', 'snat'], kinds.get(k))
ok('apache: L7 only, L4 says why', kinds.get('apache') == ['l7'] and G.get('apache:l4') is None and 'balances HTTP only' in JS)
ok('lvs, asa, forti: RADIUS, no layer', all(kinds.get(k) is None for k in ('lvs', 'asa', 'forti')))
for k in ('haproxy', 'nginx', 'apache', 'f5', 'netscaler'):
    t = text_of(k + ':l7')
    ok('%s L7: the exact allow list of the portal\'s paths' % k, G['re'] in t, t[:200])
    ok('%s L7: 404/denied for everything else, nothing about /admin as a prefix' % k,
       ('404' in t or 'Require all denied' in t) and 'starts_with "/admin"' not in t and 'STARTSWITH' not in t)
    ok('%s L7: the client\'s X-Otp-Sso-Key and X-Otp-Restore taken away' % k, 'X-Otp-Sso-Key' in t and 'X-Otp-Restore' in t)
    ok('%s L7: TLS 1.2 and 1.3 only' % k, re.search(r'ssl-min-ver TLSv1\.2|ssl_protocols TLSv1\.2 TLSv1\.3|SSLProtocol -all \+TLSv1\.2 \+TLSv1\.3|no-tlsv1\.1|-tls11 DISABLED', t), t[:300])
    ok('%s L7: HSTS' % k, 'Strict-Transport-Security' in t or '-HSTS ENABLED' in t)
    ok('%s L7: to the nodes\' own port 8443' % k, ':8443' in t or ' 8443' in t)
h = text_of('haproxy:l7')
ok('haproxy L7: X-Forwarded-For set (put in), not option forwardfor', 'http-request set-header X-Forwarded-For %[src]' in h and 'option forwardfor' not in h)
ok('haproxy: timeout connect and the portal\'s 130 s', 'timeout connect 5s' in h and 'timeout client 130s' in h and '900' not in h)
ok('haproxy L7: the health check asks 443', 'check port 443 ssl' in h)
n7 = text_of('nginx:l7')
ok('nginx L7: proxy_set_header X-Forwarded-For $remote_addr, never $proxy_add_x_forwarded_for',
   'proxy_set_header X-Forwarded-For $remote_addr;' in n7 and 'proxy_add_x_forwarded_for' not in n7)
ok('nginx L7: 8m, 130 s (the portal\'s), not 4g / 900 s', 'client_max_body_size 8m' in n7 and 'proxy_read_timeout 130s' in n7 and '4g' not in n7 and '900' not in n7)
ok('nginx: RADIUS by hash, the nodes see this machine', 'hash $remote_addr consistent' in n7 and 'this machine as the RADIUS client' in n7)
ap = text_of('apache:l7')
ok('apache: the client\'s X-Forwarded-For unset early, 8 MB, ProxyTimeout 130', 'RequestHeader unset X-Forwarded-For early' in ap and 'LimitRequestBody 8388608' in ap and 'ProxyTimeout 130' in ap and 'LimitRequestBody 0' not in ap)
f7 = text_of('f5:l7')
ok('f5: the monitors ask 443 (destination *:443), recv "ok " not "^ok "', f7.count('destination *:443') == 2 and 'recv "ok "' in f7 and '^ok' not in f7)
ok('f5 L7: XFF removed then inserted, no insert-xforwarded-for', 'HTTP::header remove "X-Forwarded-For"' in f7 and 'HTTP::header insert "X-Forwarded-For" [IP::client_addr]' in f7 and 'insert-xforwarded-for' not in f7)
ns = text_of('netscaler:l7')
ok('netscaler L7: -cip DISABLED, XFF deleted then inserted, the TLS limits', '-cip DISABLED' in ns and 'delete_http_header X-Forwarded-For' in ns and 'insert_http_header X-Forwarded-For CLIENT.IP.SRC' in ns and '-tls1 DISABLED' in ns and '-cip ENABLED' not in ns)
ok('netscaler: the monitor sends Host', '-customHeaders "Host: otp.example.cz' in ns)
for k, word in (('haproxy', 'send-proxy-v2'), ('nginx', 'proxy_protocol on;'), ('f5', 'TCP::respond "PROXY TCP'), ('netscaler', '-proxyProtocol ENABLED -proxyProtocolVersion V2')):
    t4, ts = text_of(k + ':l4'), text_of(k + ':snat')
    ok('%s L4: the PROXY protocol to 8443' % k, word in t4 and '8443' in t4, t4[:300])
    ok('%s L4 without an address: no PROXY protocol, to 443' % k, word not in ts and '8443' not in ts.replace('{pp}', ''), ts[:300])
ok('haproxy L4: the check asks 443 without PROXY, port 80 the ACME question only', 'check port 443 check-ssl verify none send-proxy-v2' in text_of('haproxy:l4') and 'check-send-proxy' not in text_of('haproxy:l4') and 'acme-challenge' in text_of('haproxy:l4'))
ok('asa: reactivation-mode depletion deadtime 1 (no "dead-time")', 'reactivation-mode depletion deadtime 1' in text_of('asa:l7') and 'dead-time' not in text_of('asa:l7'))
s7, s4, ss = G['set:l7'], G['set:l4'], G['set:snat']
ok('the settings line L7: the source /32, X-Forwarded-For, recursive, the port, on', s7['line'] == "otp --set web_proxy_from='192.0.2.6/32' --set web_proxy_header=X-Forwarded-For --set web_proxy_recursive=1 --set web_proxy_port={pp} --set web_proxy=1", s7)
ok('the settings line L4: proxy_protocol, not recursive', "--set web_proxy_header=proxy_protocol --set web_proxy_recursive=0 --set web_proxy_port={pp}" in s4['line'], s4)
ok('the settings line without an address: web_proxy=0', ss['line'] == 'otp --set web_proxy=0', ss)
ok('the settings line says "done" when the nodes have it', G['setok'] is True)
ok('lbIpIn: IPv4 networks, IPv6 the same address', G['ipin'] == [True, True, False, True], G['ipin'])
# the page itself
dh = JS[JS.index('function drawHaLb(d)'):JS.index('/* ---- signed in by a load balancer or WAF (1.0.239)')]
ok('drawHaLb: the Layer switch, the source field, the port field', "segOf('Layer', 'layer', LB_LAYERS)" in dh and "field('The address it comes to the nodes from', 'src'" in dh and "field('The nodes\\' port for the balancer', 'pp'" in dh)
ok('drawHaLb: trust notes per layer, the admin list, /healthz, the firewall, a way to the setting',
   all(w in dh for w in ("v.layer === 'l7'", "v.layer === 'l4'", 'acc.admin', 'acc.health', 'lb.fw_managed', "showPane('fw')")))
ok('Check it: the 404 checks (/admin/, //admin/, /metrics, /healthz)', all(w in dh for w in ('/admin/        # 404', '//admin/       # 404', '/metrics       # 404', '/healthz       # 404')))
sso = JS[JS.index('var SSO_GUIDES = ['):JS.index('function drawSso()')]
ok('the SSO guides: the exact allow list, no /admin prefix blocks', sso.count('LB_PORTAL_RE') == 3 and 'STARTSWITH' not in sso and 'starts_with "/admin"' not in sso and 'location /admin { return 403; }' not in sso)
ok('the SSO card no longer says "never passes /admin on"', 'never passes /admin on' not in JS and 'passes on the enrolment pages alone - an exact list of paths' in JS)

# ---- otp_web.py: the balancer's own port ----------------------------------------------------------
spec = importlib.util.spec_from_file_location('otp_web_t', OUT + '/deploy/otp_web.py')
ow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ow)
SAMPLE = open(OUT + '/deploy/nginx-otp.conf').read()
ok('otp_web: NGINX_LB is conf.d/otp_lbport.conf, read after otp.conf', ow.NGINX_LB.endswith('/otp_lbport.conf') and 'otp_lbport.conf' > 'otp.conf')
ok('lbport_checked: None leaves nginx alone, port 0 takes it away', ow.lbport_checked(None) is None and ow.lbport_checked({'port': 0}) == {'port': 0})
for bad_lp, why in (({'port': 80, 'from': ['192.0.2.6']}, 'below 1024'), ({'port': 8443, 'from': []}, 'no balancer'),
                    ({'port': 8443, 'from': ['x']}, 'not an address'), ({'port': 8443, 'from': ['192.0.2.6'], 'header': 'Host'}, 'Host'),
                    ({'port': 8443, 'from': ['192.0.2.6'], 'header': 'X-A;\n'}, 'a ; in a header'), ('x', 'not an object')):
    try:
        ow.lbport_checked(bad_lp)
        ok('lbport_checked refuses: ' + why, False)
    except ow.Refused:
        ok('lbport_checked refuses: ' + why, True)
try:
    ow.realip_checked({'from': ['192.0.2.6'], 'header': 'proxy_protocol'})
    ok('realip (443) refuses proxy_protocol as a header', False)
except ow.Refused:
    ok('realip (443) refuses proxy_protocol as a header', True)
lpp = ow.lbport_checked({'port': 8443, 'from': ['192.0.2.6/32', '2001:db8::6'], 'header': 'proxy_protocol', 'recursive': True})
ok('lbport_checked: the PROXY protocol never recursive', lpp['header'] == 'proxy_protocol' and lpp['recursive'] is False and lpp['from'] == ['192.0.2.6/32', '2001:db8::6/128'], lpp)
pp = ow.lbport_server(SAMPLE, lpp)
ok('the server: listen 8443 ssl http2 proxy_protocol on IPv4 and IPv6', 'listen 8443 ssl http2 proxy_protocol;' in pp and 'listen [::]:8443 ssl http2 proxy_protocol;' in pp)
ok('the server: the balancers alone believed, in the PROXY protocol', 'set_real_ip_from 192.0.2.6/32;' in pp and 'set_real_ip_from 2001:db8::6/128;' in pp and 'real_ip_header proxy_protocol;' in pp and 'real_ip_recursive off;' in pp)
ok('the server: the certificate and TLS lines of 443', 'ssl_certificate           /etc/nginx/certs/otp.pem;' in pp and 'ssl_protocols             TLSv1.2 TLSv1.3;' in pp and 'Strict-Transport-Security' in pp)
ok('the server: the enrolment page as on 443 (its allow list, limits, index.php)', '# PORTAL-ALLOW-BEGIN' in pp and 'allow 10.0.0.0/8;' in pp and 'limit_req zone=otp_login' in pp and '$document_root/index.php' in pp)
ok('the server: nothing else - no admin, metrics, healthz, acme', not re.search(r'admin/index\.php|metrics\.php|healthz\.php|acme\.php|client_max_body_size 4g|fastcgi_read_timeout 900', pp))
ok('the server: everything else 404, 8 MB, GET/HEAD/POST, no multipart', 'location / { return 404; }' in pp and 'client_max_body_size 8m;' in pp and '^(GET|HEAD|POST)$' in pp and 'multipart' in pp)
ok('the server: the portal\'s own assets only', ow.LB_ASSETS in pp and 'location /assets/' not in pp)
lx = ow.lbport_checked({'port': 9443, 'from': ['192.0.2.6'], 'header': 'X-Real-IP', 'recursive': False})
xs = ow.lbport_server(SAMPLE, lx)
ok('X-Real-IP: no proxy_protocol, the header, recursive off', 'proxy_protocol' not in xs and 'real_ip_header X-Real-IP;' in xs and 'listen 9443 ssl http2;' in xs and 'real_ip_recursive off;' in xs)
# what the other writers did to otp.conf is carried over
acc = ow.access_checked({'portal': {'any': False, 'from': ['198.51.100.0/24']}, 'admin': {'any': False, 'from': ['10.9.0.0/16']},
                         'health': {'any': False, 'from': ['192.0.2.6']}})
main2 = ow.sso_peer_into(ow.access_into(SAMPLE, acc), True)
pp2 = ow.lbport_server(main2, lpp)
ok('the allow list of the enrolment pages, as set, carried over', 'allow 198.51.100.0/24;' in pp2 and '10.9.0.0/16' not in pp2)
ok('the sign-in by the balancer: OTP_PEER carried over', 'fastcgi_param  OTP_PEER $realip_remote_addr;' in pp2)
main3 = ow.realip_into(main2, {'from': ['192.0.2.6/32'], 'header': 'X-Forwarded-For', 'recursive': True})
ok('443\'s own realip lines are not copied into the balancer\'s port', ow.lbport_server(main3, lpp).count('real_ip_header') == 1)
ok('realip with no balancer (the PROXY protocol on its own port) takes 443\'s lines out',
   'OTP-REALIP-BEGIN' not in ow.realip_into(main3, {'from': [], 'header': '', 'recursive': False}))
try:
    ow.lbport_server(SAMPLE.replace('location = / {', 'location = /x {'), lpp)
    ok('a file without location = / is refused, not half written', False)
except ow.Refused:
    ok('a file without location = / is refused, not half written', True)
src = open(OUT + '/deploy/otp_web.py').read()
ok('nginx_part: the file in the snapshot (put back when nginx refuses), written and taken away',
   'paths = [NGINX_MAIN, NGINX_VIP, NGINX_LB]' in src and 'write_root(NGINX_LB, text, 0o644)' in src and 'os.unlink(NGINX_LB)' in src)
ok('nginx_part: built after the TLS of 443 is in (main as written)', src.index('lbport_server(main[:where[0]] + block + main[where[1]:], lp)') > src.index("new, words, dh['node'] = tls_into(block"))
ok('the request: lbport checked', "out['lbport'] = lbport_checked(r.get('lbport'))" in src)
# nginx -t on a scratch copy: unix sockets in place of every port - nothing bound
if shutil.which('nginx'):
    d = str(TMP) + '/ng/'
    os.makedirs(d)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', d + 'k.key', '-out', d + 'c.pem',
                    '-days', '2', '-subj', '/CN=t'], capture_output=True)
    shutil.copy('/etc/nginx/fastcgi_params', d + 'fastcgi_params')
    n = [0]

    def unix(m):
        n[0] += 1
        return 'listen unix:%ss%d.sock' % (d, n[0])

    def fix(t):
        t = t.replace('/etc/nginx/certs/otp.pem', d + 'c.pem').replace('/etc/nginx/certs/otp.key', d + 'k.key').replace('/var/log/nginx/', d)
        return re.sub(r'listen\s+(\[::\]:)?\d+', unix, t)

    for lp, what in ((lpp, 'the PROXY protocol'), (lx, 'X-Real-IP')):
        n[0] = 0
        open(d + 'otp.conf', 'w').write(fix(main3))
        open(d + 'lb.conf', 'w').write(fix(ow.LB_HEAD + ow.lbport_server(main3, lp)))
        open(d + 'nginx.conf', 'w').write('pid %snginx.pid;\nerror_log %serror.log;\nevents {}\nhttp {\n  access_log %saccess.log;\n'
                                          '  client_body_temp_path %scb; proxy_temp_path %spt; fastcgi_temp_path %sft; uwsgi_temp_path %sut; scgi_temp_path %sst;\n'
                                          '  include %sotp.conf;\n  include %slb.conf;\n}\n' % ((d,) * 10))
        t = subprocess.run(['nginx', '-t', '-c', d + 'nginx.conf', '-p', d], capture_output=True, text=True)
        ok('nginx -t takes otp.conf and the balancer\'s port (%s)' % what, t.returncode == 0, t.stderr[-300:])
else:
    print('(nginx not installed: nginx -t not tried)')

# ---- the daemon: the settings ---------------------------------------------------------------------
g = {'__name__': 't_lb_head'}
exec(compile(src_of('00_head.py'), '00_head.py', 'exec'), g)
cs, Bad = g['check_setting'], g['BadSetting']
ok('web_proxy_port: default 0, range 0-65535', g['DEFAULTS'].get('web_proxy_port') == 0 and g['TUNABLE'].get('web_proxy_port') == (0, 65535))
ok('web_proxy_port: its name, its help, in the fw pane, only with web_proxy on', 'web_proxy_port' in g['NAMES'] and 'web_proxy_port' in g['SAYS']
   and 'web_proxy_port' in g['PANES']['fw'] and g['ONLY_WHEN'].get('web_proxy_port') == ['web_proxy', '1'])
for v, want in ((0, 0), (8443, 8443), ('4443', 4443)):
    ok('web_proxy_port %r taken' % (v,), cs('web_proxy_port', v) == want)
# 9861 (the API) and 18129 (the SSH gate) are refused by the save of the whole batch since 1.0.262
# (web_proxy_port_problem), so a save that moves both in one go works
ok('web_proxy_port: the API and the SSH gate refused at the save', g['web_proxy_port_problem']({'web_proxy_port': 9861, 'web_proxy': 1}, {'api_port': 9861, 'ssh_gate_port': 18129}) != '' and
   g['web_proxy_port_problem']({'web_proxy_port': 18129, 'web_proxy': 1}, {'api_port': 9861, 'ssh_gate_port': 18129}) != '')
for v in (80, 443, 1023, 70000, -1):
    try:
        cs('web_proxy_port', v)
        ok('web_proxy_port %r refused' % v, False)
    except Bad:
        ok('web_proxy_port %r refused' % v, True)
ok('web_proxy_header: proxy_protocol taken, X-Forwarded-For still', cs('web_proxy_header', 'proxy_protocol') == 'proxy_protocol' and cs('web_proxy_header', 'X-Forwarded-For') == 'X-Forwarded-For')
for v in ('proxy-protocol;', 'Host', 'a b', 'proxy_protocol2'):
    try:
        cs('web_proxy_header', v)
        ok('web_proxy_header %r refused' % v, False)
    except Bad:
        ok('web_proxy_header %r refused' % v, True)
dm = src_of('80_daemon.py')
ok('the save: proxy_protocol only with the balancer\'s own port', "'proxy_protocol' and not int(after.get('web_proxy_port') or 0)" in dm)
ok('web_proxy_port kept as a row at 0 (so the port is taken away again)', 'web_proxy_port' in g['KEPT_OFF_KEYS'])
ok('the database guard knows web_proxy_port', "'web_proxy_port'" in src_of('50g_guard.py'))

# 88w_web.py: what root is asked
CONF = {}
w = {'re': re, 'ipaddress': ipaddress, 'CONFIG': CONF, 'saved_keys': lambda st: set(CONF.get('_saved', ()))}
exec(defs('88w_web.py', ['realip_desired', 'web_proxy_nets', 'lbport_desired']), w)
CONF.update(web_proxy=1, web_proxy_from='192.0.2.6 10.0.0.0/8 bad', web_proxy_header='proxy_protocol', web_proxy_recursive=1, web_proxy_port=8443)
ok('with the PROXY protocol: 443 believes nobody\'s header', w['realip_desired'](None) == {'from': [], 'header': '', 'recursive': False})
ok('...and the balancer\'s port gets it, never recursive', w['lbport_desired'](None) == {'port': 8443, 'from': ['192.0.2.6/32', '10.0.0.0/8'], 'header': 'proxy_protocol', 'recursive': False}, w['lbport_desired'](None))
CONF.update(web_proxy_header='X-Forwarded-For')
ok('with X-Forwarded-For: 443 as before, and the port too', w['realip_desired'](None)['header'] == 'X-Forwarded-For' and w['lbport_desired'](None)['header'] == 'X-Forwarded-For')
CONF.update(web_proxy_port=0)
ok('port 0, never set: nothing asked (nginx as it is)', w['lbport_desired'](None) is None)
CONF['_saved'] = ['web_proxy_port']
ok('port 0 after it was set: taken away', w['lbport_desired'](None) == {'port': 0})
CONF.update(web_proxy=0, web_proxy_port=8443)
ok('web_proxy off: taken away too', w['lbport_desired'](None) == {'port': 0})
wsrc = src_of('88w_web.py')
ok('the request carries lbport; a request with lbport alone is asked', "out['lbport'] = lp" in wsrc and "'lbport' not in desired" in wsrc)
ok('the firewall: the port from the balancers only', "'port': str(lp['port'])" in wsrc and "'source': n, 'note': 'the balancer\\'s own port'" in wsrc)
# lb_facts
api = src_of('90_api.py')
lf = {'re': re, 'Path': Path, 'CONFIG': {'web_proxy': 1, 'web_proxy_from': '192.0.2.6', 'web_proxy_header': 'proxy_protocol', 'web_proxy_port': 8443, 'portal_sso': 1},
      'NGINX_CONF_PATHS': [str(TMP / 'none.conf')], 'vip_conf': lambda st: {}, 'web_proxy_nets': lambda: ['192.0.2.6/32'],
      'access_desired': lambda st: {'admin': {'any': False, 'from': ['10.0.0.0/8']}},
      'fw_conf': lambda st: {'set': True, 'on': True}}


class St:
    def clients(self):
        return [{'name': 'asa', 'address': '10.1.1.1', 'enabled': 1, 'secret': SECRET}]


exec(defs('90_api.py', ['lb_facts', '_lb_fw_on']), lf)
facts = lf['lb_facts'](St())
ok('lb_facts: web_proxy, the three lists, portal_sso, the firewall', facts['web_proxy'] == {'on': True, 'from': ['192.0.2.6/32'], 'header': 'proxy_protocol', 'recursive': True, 'port': 8443}
   and facts['access']['admin'] == {'any': False, 'from': ['10.0.0.0/8'], 'set': True} and facts['access']['portal']['any'] is True
   and facts['portal_sso'] is True and facts['fw_managed'] is True, facts)
ok('lb_facts: no secret', SECRET not in json.dumps(facts))

# ---- the rest of the package ---------------------------------------------------------------------
doc = open(OUT + '/docs/load-balancers.md', encoding='utf-8').read()
ok('docs: the layers, the balancer\'s own port, the exact list', all(w in doc for w in ('## The layer: L7 or L4', "## The nodes' own port for the balancer (1.0.259)", G['re'], 'web_proxy_header=proxy_protocol')))
ok('docs: nothing of the old advice (option forwardfor, $proxy_add_x_forwarded_for, recv "^ok ", dead-time, 4g)',
   not re.search(r'option forwardfor|proxy_add_x_forwarded_for|recv "\^ok |dead-time 1|client_max_body_size 4g|LimitRequestBody 0', doc))
ins = open(OUT + '/install.sh').read()
ok('install.sh --uninstall takes otp_lbport.conf away too', 'rm -f /etc/nginx/conf.d/otp_lbport.conf' in ins)
# the Czech
sys.path.insert(0, '/home/claude/i18n')
from cs_267 import S267, P267
pack = json.load(open(OUT + '/web/lang/cs.json'))
had = {v['source'] for v in pack['strings'].values() if v.get('text')}
hadp = [v['source'] for v in pack['patterns'].values() if v.get('text')]


def covered(t):
    if t in S267 or t in had:
        return True
    for k in list(P267) + hadp:
        if re.match('^' + re.sub(r'\\\{\d\\\}', '(.+?)', re.escape(k)) + '$', t):
            return True
    return False


words = ['L7 - TLS ended on the balancer', 'L4 - TLS passed through, PROXY protocol', 'L4 - no client address (not advised)',
         'Layer', 'The address it comes to the nodes from', "The nodes' port for the balancer", 'Settings → Firewall and access',
         "The nodes take the client's own address from X-Forwarded-For sent by 192.0.2.6, on their port 8443 that serves the enrolment pages only.",
         'Who may ask /healthz does not take 192.0.2.6: the balancer would take both nodes out.',
         'apache balances HTTP only: pick L7 above, or HAProxy, nginx, the F5 or the NetScaler for L4.'.replace('apache', 'Apache httpd'),
         "The balancer's own port on the nodes", g['SAYS']['web_proxy_port'],
         "nginx: the balancer's own port 8443 - the enrolment pages only, for 192.0.2.6/32 (the PROXY protocol)"]
for k in G:
    if ':' in k and G[k] and not k.startswith('set:'):
        words += [p[0] for p in G[k] if not p[0].startswith(('/etc', 'tmsh', 'NetScaler', 'From any'))]
words += [p[0] for k in G if ':' in k and G[k] and not k.startswith('set:') for p in G[k] if p[1]]
missing = sorted({x.replace('otp.example.cz', '{n}') for x in words if not covered(x)})
ok('Czech: every new word of the load balancer (cs_267 or cs.json)', not missing, missing[:5])
ok('Czech: formal (vy), not ty', not re.search(r'\b(stiskni|udělej|podívej|vlož|zadej|otevři|ty)\b', json.dumps([S267, P267], ensure_ascii=False)))
ok('Czech: the established "stránky registrace" for the enrolment pages', 'zápis tokenů' not in json.dumps([S267, P267], ensure_ascii=False))

shutil.rmtree(TMP, ignore_errors=True)
print('ALL %d / %d' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
