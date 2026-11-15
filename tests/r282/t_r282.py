# t_r282.py VERSION - 1.0.282:
# - the SID as the URL of a certificate's SAN (tag:microsoft.com,2022-09-14:sid:...) read as its SID;
# - the values of a certificate request for an account of the directory (the installed server's API, the
#   mock directory of the package on 3899): subject, UPN, the SID's URL, certreq's .inf, openssl's config,
#   what would stand in the way; a full administrator only; nothing kept;
# - the keytab guide's values from AD: the NetBIOS name of the domain's crossRef (CORPNET_NT - not the
#   first part of corpnet.loc), its DNS name, the account holding each SPN.
import json, os, re, ssl, subprocess, sys, tempfile, urllib.request, http.cookiejar
V = sys.argv[1] if len(sys.argv) > 1 else '1.0.282'
OTP_PY = '/home/claude/build/out/otp-%s/otp.py' % V
src = open(OTP_PY).read()
g = {'__name__': 'otp_t', '__file__': OTP_PY}
exec(compile(src, 'otp.py', 'exec'), g)
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:300]))


# a certificate whose SID is only the URL of its SAN
d = tempfile.mkdtemp(prefix='t-r282-')
SID = 'S-1-5-21-1111-2222-3333-1105'
open(d + '/c.cnf', 'w').write('[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=ext\n[dn]\nCN=Falco Tester\n'
                              '[ext]\nsubjectAltName=@alt\nextendedKeyUsage=clientAuth\n[alt]\n'
                              'otherName.1=1.3.6.1.4.1.311.20.2.3;UTF8:falco@corpnet.cz\n'
                              'URI.1=tag:microsoft.com,2022-09-14:sid:%s\n' % SID)
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', d + '/c.key', '-out', d + '/c.pem',
                '-days', '2', '-config', d + '/c.cnf'], check=True, capture_output=True)
f = g['cert_facts'](open(d + '/c.pem').read())
ok('the SID in the SAN\'s URL read as the certificate\'s SID', f['sid'] == SID, f['sid'])
ok('...the UPN beside it', f['upn'] == ['falco@corpnet.cz'], f['upn'])
open(d + '/c2.cnf', 'w').write(open(d + '/c.cnf').read().replace('tag:microsoft.com,2022-09-14:sid:', 'https://example/sid:'))
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', d + '/c2.key', '-out', d + '/c2.pem',
                '-days', '2', '-config', d + '/c2.cnf'], check=True, capture_output=True)
ok('...an URL of another kind is no SID', g['cert_facts'](open(d + '/c2.pem').read())['sid'] == '')

# the installed server's API
for k in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy'):
    os.environ.pop(k, None)
HERE = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, HERE + '/../cert/ui_cert_setup.py', 'up'], check=True, capture_output=True)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE


def browser():
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                       urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), urllib.request.ProxyHandler({}))


def api(op, what, body=None):
    rq = urllib.request.Request('https://127.0.0.1/admin/?api=' + what, data=json.dumps(body).encode() if body is not None else None,
                                headers={'Content-Type': 'application/json', 'Accept': 'application/json', 'Sec-Fetch-Site': 'same-origin'})
    try:
        r = op.open(rq, timeout=60)
        return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}


A = browser()
st, _ = api(A, 'login', {'name': 'admin', 'password': open('/home/claude/run/adminpw').read().strip()})
ok('signed in as the full administrator', st == 200, st)
st, x = api(A, 'certlogin', {'action': 'request', 'name': 'falco'})
ok('falco looked up (%s)' % st, st == 200 and x.get('upn') == 'falco@corpnet.cz', x)
ok('...the subject: CN=Falco Tester', x.get('subject') == 'CN=Falco Tester' and x.get('cn') == 'Falco Tester', x.get('subject'))
ok('...the SID, and its URL for the SAN', x.get('sid') == SID and x.get('url') == 'tag:microsoft.com,2022-09-14:sid:' + SID, x.get('url'))
ok('...certreq\'s .inf: the subject, the UPN and the URL in the SAN', 'Subject = "CN=Falco Tester"' in x.get('certreq', '') and
   '_continue_ = "upn=falco@corpnet.cz&"' in x['certreq'] and '_continue_ = "url=tag:microsoft.com,2022-09-14:sid:%s&"' % SID in x['certreq'], x.get('certreq', '')[-300:])
ok('...openssl\'s config the same', 'otherName:1.3.6.1.4.1.311.20.2.3;UTF8:falco@corpnet.cz' in x.get('openssl', '') and
   'URI:tag:microsoft.com,2022-09-14:sid:' + SID in x['openssl'])
ok('...its role here (read only: VPN_2FACT_USERS)', x.get('role') == 'readonly', x.get('role'))
st, x = api(A, 'certlogin', {'action': 'request', 'name': 'CORP\\falco'})
ok('DOMAIN\\name: the same account', st == 200 and x.get('upn') == 'falco@corpnet.cz', (st, x.get('upn')))
st, x = api(A, 'certlogin', {'action': 'request', 'name': 'falco@corpnet.cz'})
ok('the UPN: the same account', st == 200 and x.get('name') == 'falco', (st, x.get('name')))
st, x = api(A, 'certlogin', {'action': 'request', 'name': 'jnovak'})
ok('jnovak (no SID in the directory): said, the URL left out', st == 200 and not x.get('url') and
   any('SID' in n[1] for n in x.get('notes') or []) and 'url=' not in x.get('certreq', ''), x.get('notes'))
st, x = api(A, 'certlogin', {'action': 'request', 'name': 'nogroups'})
ok('nogroups (no UPN, no role): both said', st == 200 and any('userPrincipalName' in n[1] for n in x.get('notes') or [])
   and any('none of the groups' in n[1] for n in x.get('notes') or []), x.get('notes'))
st, x = api(A, 'certlogin', {'action': 'request', 'name': 'nobody-here'})
ok('nobody of that name: 404', st == 404, (st, x))
st, x = api(A, 'certlogin', {'action': 'request', 'name': 'a*b'})
ok('a name with a filter\'s letters: no wildcard - nobody found (escaped) or refused', st in (400, 404) and not x.get('upn'), (st, x))
B = browser()
st, _ = api(B, 'certlogin', {'action': 'request', 'name': 'falco'})
ok('not without signing in', st in (401, 403), st)

# the keytab guide's values from AD
st, x = api(A, 'kerberos', {'action': 'ad'})
ok('AD asked for the domain\'s names (%s)' % st, st == 200 and x.get('ok'), x)
ok('...its NetBIOS name: CORPNET_NT - not the first part of corpnet.loc', x.get('netbios') == 'CORPNET_NT', x.get('netbios'))
ok('...its DNS name and realm', x.get('dns') == 'corpnet.loc' and x.get('realm') == 'CORPNET.LOC', (x.get('dns'), x.get('realm')))
spn = x.get('spn') or {}
ok('...the account holding HTTP/otp.corpnet.loc: svc-otp-web', spn.get('HTTP/otp.corpnet.loc') == ['svc-otp-web'], spn)
subprocess.run([sys.executable, HERE + '/../cert/ui_cert_setup.py', 'down'], capture_output=True)
print('ALL %d / %d' % (sum(R), len(R)))
