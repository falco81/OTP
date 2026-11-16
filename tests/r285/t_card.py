# t_card.py VERSION - 1.0.285: the card of a sign-in with a certificate watched (admin_cert_card), on
# the installed server (tests/cert/ui_cert_setup.py: the mock directory, the test PKI, nginx on 8443):
#  - off (the default): whoami says nothing to look for, ?api=cert-alive says '' - nothing changes;
#  - nginx on the certificate's port: no TLS session taken up again (openssl -reconnect: all New), no
#    connection kept (Connection: close); ?api=cert-alive answered there, to the pages' own origin only;
#  - lock: the same certificate - in; another (falco-sid2), none, or the page's "card-gone" - the pages
#    locked: every question 423 (code card), whoami no role; the same card again - unlocked; events;
#  - signout: another certificate - the sign-in ended, whoami nobody, the event;
#  - a sign-in not seen for long (its row aged by hand): taken as without its card;
#  - a password's sign-in untouched in every mode; the interval said; off again.
import http.cookiejar, json, os, re, ssl, subprocess, sys, time, urllib.parse, urllib.request
VER = sys.argv[1] if len(sys.argv) > 1 else '1.0.285'
HERE = os.path.dirname(os.path.abspath(__file__))
PKI = os.environ.get('PKI_DIR', '/tmp/claude-0/pki2')
PW = open('/home/claude/run/adminpw').read().strip()
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]), flush=True)


# 1.0.288: the server's end said by the picture - 5 px (the card out), 6 px (another card); a bare 403 before
def ended(st, w, why):
    return st == 403 if VER < '1.0.288' else (st, w) == (200, why)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Browser(object):
    def __init__(self, cert=None, jar=None):
        self.jar = jar if jar is not None else http.cookiejar.CookieJar()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if cert:
            ctx.load_cert_chain(PKI + '/%s.pem' % cert, PKI + '/%s.key' % cert)
        self.op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                              urllib.request.HTTPCookieProcessor(self.jar), NoRedirect)

    def raw(self, url, body=None, origin=None):
        h = {'Accept': 'application/json', 'Sec-Fetch-Site': 'same-origin'}
        if origin:
            h['Origin'] = origin
        data = None
        if body is not None:
            h['Content-Type'] = 'application/json'
            data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=h)
        try:
            with self.op.open(req, timeout=60) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def j(self, what, body=None):
        st, hd, raw = self.raw('https://127.0.0.1/admin/?api=' + what, body)
        try:
            return st, json.loads(raw or b'{}')
        except ValueError:
            return st, {'raw': raw[:200]}

    def alive(self):
        """One check as the page's picture makes it: (HTTP status, the picture's width or None)."""
        # The check's key as the page has it (1.0.287): from whoami; without it the check changes nothing.
        k = ''
        try:
            k = ((self.j('whoami')[1].get('who') or {}).get('card') or {}).get('key') or ''
        except Exception:                               # noqa: BLE001
            k = ''
        st, hd, raw = self.raw('https://127.0.0.1:8443/admin/?api=cert-alive&k=%s&r=1' % k)
        wide = raw[6] if st == 200 and 'image/gif' in (hd.get('Content-Type') or '') and len(raw) > 7 else None
        return st, wide, hd

    def cert_login(self):
        st, got = self.j('cert-nonce', {})
        if st != 200:
            return None
        self.raw(got['url'])
        st, me = self.j('whoami')
        return me if st == 200 else None


def setup(a):
    return subprocess.run([sys.executable, HERE + '/../cert/ui_cert_setup.py', a], capture_output=True, text=True).stdout


def events(text):
    st, got = admin.j('events')
    return text in json.dumps(got, ensure_ascii=False)


CONF = '/etc/nginx/conf.d/otp_certlogin.conf'


def helper(until, wait=120):
    """root's helper run as otp-web.path would (no systemd here), until the condition holds."""
    end = time.time() + wait
    while time.time() < end:
        subprocess.run([sys.executable, '-I', '/usr/local/lib/otp/otp_web.py'], capture_output=True, timeout=120)
        if until():
            return True
        time.sleep(1.5)
    return False


def page_csp(b):
    st, hd, raw = b.raw('https://127.0.0.1/admin/')
    return hd.get('Content-Security-Policy') or ''


def age(field, ago):
    """A field of falco's watched sign-ins put `ago` seconds back (the database of a standalone server)."""
    import sqlite3
    db = sqlite3.connect('/var/lib/otp/otp.db', timeout=20)
    n = 0
    for sid, data in db.execute("SELECT id, data FROM sessions WHERE kind = 'admin' AND name = 'falco'").fetchall():
        dd = json.loads(data or '{}')
        if dd.get('card'):
            dd[field] = time.time() - ago
            db.execute('UPDATE sessions SET data = ? WHERE id = ?', (json.dumps(dd), sid))
            n += 1
    db.commit()
    db.close()
    return n


print(setup('up').strip())
admin = Browser()
st, got = admin.j('login', {'name': 'admin', 'password': PW})
ok('the local administrator signs in (a password)', st == 200, got)


def settings(**kv):
    st, got = admin.j('settings', {'settings': kv})
    for _ in range(10):                 # nginx's rate (429): asked again a moment later
        if st != 429:
            break
        time.sleep(3)
        st, got = admin.j('settings', {'settings': kv})
    if st != 200:
        print('   settings', kv, st, str(got)[:200])
    time.sleep(1.2)
    return st


# ---- off: as before ----
settings(admin_cert_card='off', admin_cert_card_s=15, admin_cert_card_grace_s=30)
helper(lambda: 'alive' not in open(CONF).read())
time.sleep(4)                      # nginx -s reload settled (its old workers gone)
before = open(CONF).read()
ok('off (the default): nginx on the port as before - nothing of the card', 'alive' not in before and
   'ssl_session_cache off' not in before and 'keepalive_timeout 0' not in before, before[:200])
falco = Browser('falco')
me = falco.cert_login()
ok('off: falco signs in with the certificate', me and (me.get('who') or {}).get('name') == 'falco', me)
ok('...whoami: nothing to watch', me and not (me.get('who') or {}).get('card'), me)
ok('...the page\'s policy as before (no other address for pictures)', "img-src 'self' data:;" in page_csp(falco), page_csp(falco))
st, w, hd = falco.alive()
ok('...?api=cert-alive not answered on the port (404, as before)', st == 404, st)
st, v = falco.j('certlogin')
ok('...the card\'s facts: off', v.get('watch') == 'off', v.get('watch'))

# ---- signout: nginx made for it ----
settings(admin_cert_card='signout', admin_cert_card_s=5)
ok('signout: root\'s helper writes nginx again', helper(lambda: 'alive' in open(CONF).read()))
conf = open(CONF).read()
ok('nginx: no TLS session, no connection kept, cert-alive let through', 'ssl_session_cache off;' in conf and
   'ssl_session_tickets off;' in conf and 'keepalive_timeout 0;' in conf and 'cert-(login|check|alive)' in conf
   and 'shared:' not in conf, conf[:300])
# nginx -s reload is asynchronous: the old workers (with the default 'none' - an OpenSSL cache of one
# session) take connections for a moment after it. Measured once nginx has settled, three times.
time.sleep(4)
reused = []
for _ in range(3):
    o = subprocess.run(['openssl', 's_client', '-connect', '127.0.0.1:8443', '-reconnect', '-cert', PKI + '/falco.pem',
                        '-key', PKI + '/falco.key', '-tls1_2'], input='', capture_output=True, text=True, timeout=60).stdout
    reused.append((o.count('Reused,'), o.count('New,')))
    time.sleep(2)
ok('...openssl -reconnect: every handshake new, none taken up again (TLS 1.2, three times)', all(r == 0 and n >= 6 for r, n in reused), reused)
subprocess.run(['openssl', 's_client', '-connect', '127.0.0.1:8443', '-sess_out', '/tmp/claude-0/t_card.sess', '-tls1_3',
                '-cert', PKI + '/falco.pem', '-key', PKI + '/falco.key'], input='GET / HTTP/1.0\r\n\r\n', capture_output=True, text=True, timeout=60)
o2 = subprocess.run(['openssl', 's_client', '-connect', '127.0.0.1:8443', '-sess_in', '/tmp/claude-0/t_card.sess', '-tls1_3'],
                    input='', capture_output=True, text=True, timeout=60).stdout
ok('...TLS 1.3: no ticket to take it up again', 'Reused,' not in o2, re.findall(r'(New|Reused),[^\n]*', o2))
st, me = falco.j('whoami')
card_said = dict((me.get('who') or {}).get('card') or {})
card_key = card_said.pop('key', None)
card_said.pop('out_for', None)          # 1.0.288
ok('...whoami: the page told how (signout, 5 s, grace 30, port 8443)', card_said ==
   {'mode': 'signout', 'every': 5, 'grace': 30, 'port': 8443, 'out': False, 'stale': False}, card_said)
csp = page_csp(falco)
ok('...the page\'s policy lets in pictures of the port, that one address only', "img-src 'self' data: https://127.0.0.1:8443;" in csp
   and "connect-src 'self';" in csp, csp)
ok('...a password\'s page: as before', "img-src 'self' data:;" in page_csp(admin))
st, w, hd = falco.alive()
ok('...the card there: a picture 1 px wide', (st, w) == (200, 1), (st, w))
ok('...nothing kept (no-store), the connection closed', 'no-store' in (hd.get('Cache-Control') or '') and
   (hd.get('Connection') or '').lower() == 'close', hd)
st, got = falco.j('status')
ok('...the pages answer', st == 200, st)
st, w, hd = Browser(jar=http.cookiejar.CookieJar()).alive()
# 1.0.286: no cookie at all - a picture 3 px wide (the page then says so on 443); 403 before it
ok('no session at all: nothing asked (3 px from 1.0.286, 403 before)', (st, w) == (200, 3) or st == 403, (st, w))
if VER >= '1.0.287':
    # A page of another host of the same site (1.0.287): the session's cookie goes with a picture, not its key.
    st, hd, raw = Browser(jar=falco.jar).raw('https://127.0.0.1:8443/admin/?api=cert-alive&k=0123abcd&r=1')
    ok('a check without the page\'s key (another site\'s page): nothing changed, 1 px', st == 200 and raw[6] == 1 and
       falco.j('status')[0] == 200, st)
    ok('...the key is the session\'s (32 hex)', bool(card_key) and len(card_key) == 32, card_key)
st, w, hd = Browser(jar=falco.jar).alive()
ok('signout: the card out (no certificate) - 403 (5 px from 1.0.288)', ended(st, w, 5), (st, w))
st, me = falco.j('whoami')
ok('...signed out', st == 200 and not me.get('who'), me)
ok('...said in the events', events('falco was signed out: the card they signed in with was taken out'))
falco.cert_login()
st, w, hd = Browser('falco-sid2', jar=falco.jar).alive()
ok('another card than the one signed in with - 403 (6 px from 1.0.288)', ended(st, w, 6), (st, w))
st, me = falco.j('whoami')
ok('...signed out', not me.get('who'), me)
ok('...said: the card was changed', events('another certificate than the one signed in with was offered (the card was changed)'))
falco.cert_login()
falco.alive()           # a check found the card in this browser (1.0.286: before it, card-gone means "cannot be checked")
st, got = falco.j('card-gone', {})
ok('the page\'s picture got nothing at all (card-gone): signed out', got.get('gone') is True, (st, got))
falco.cert_login()
st, me = admin.j('whoami')
ok('a password\'s sign-in: nothing watched', not (me.get('who') or {}).get('card'), me.get('who'))
st, got = admin.j('card-gone', {})
st2, got2 = admin.j('status')
ok('...card-gone from it: nothing (still answered)', got.get('watched') is False and st2 == 200, (got, st2))

# ---- grace ----
settings(admin_cert_card='grace', admin_cert_card_grace_s=30)
st, w, hd = falco.alive()
ok('grace: the card there - 1 px', (st, w) == (200, 1), (st, w))
st, w, hd = Browser(jar=falco.jar).alive()
ok('...the card out - 2 px, still signed in', (st, w) == (200, 2), (st, w))
st, me = falco.j('whoami')
ok('...whoami: out, no role (the PHP pages\' gates refuse it)', (me.get('who') or {}).get('card', {}).get('out') is True
   and (me.get('who') or {}).get('role') == '', me.get('who'))
st, got = falco.j('status')
ok('...nothing answered meanwhile: 423, code card', st == 423 and got.get('code') == 'card', (st, got))
st, w, hd = falco.alive()
ok('...back in time - 1 px', (st, w) == (200, 1), (st, w))
st, got = falco.j('status')
ok('...the pages answer again', st == 200, st)
ok('...said in the events: out, back', events('falco: the card they signed in with is out - the session waits 30 s for it')
   and events('falco: the card they signed in with is back'))
Browser(jar=falco.jar).alive()
age('card_out', 40)
st, w, hd = Browser(jar=falco.jar).alive()
ok('...out longer than the grace: 403 (5 px from 1.0.288), signed out', ended(st, w, 5) and not falco.j('whoami')[1].get('who'), st)
ok('...said: not put back in time', events('falco was signed out: the card they signed in with was not put back in time'))
falco.cert_login()
falco.alive()
st, w, hd = Browser('falco-sid2', jar=falco.jar).alive()
ok('grace: another card - 403 (6 px from 1.0.288) at once', ended(st, w, 6) and not falco.j('whoami')[1].get('who'), st)
falco.cert_login()
falco.alive()
st, got = falco.j('card-gone', {})
ok('grace: card-gone - held, the time counted', got.get('gone') is False and 0 < got.get('grace_left', 0) <= 30, got)
falco.alive()
# the server's half: a page that stopped checking (asleep - a tablet locked): held, not ended
falco.j('status')
n = age('card_seen', 1000)
st, got = falco.j('status')
ok('the server\'s half: no check for long - held: nothing answered (423), not signed out', n and st == 423 and got.get('code') == 'card', (n, st, got))
st, me = falco.j('whoami')
ok('...whoami: still falco, no role, the page told to check at once (stale)', (me.get('who') or {}).get('name') == 'falco' and
   (me.get('who') or {}).get('role') == '' and ((me.get('who') or {}).get('card') or {}).get('stale') is True, me.get('who'))
st, w, hd = falco.alive()
ok('...the page wakes, its check finds the card: 1 px', (st, w) == (200, 1), (st, w))
st, got = falco.j('status')
ok('...answered again', st == 200, st)
age('card_seen', 1000)
st, w, hd = Browser(jar=falco.jar).alive()
ok('...held, and the check finds no card: out (grace - 2 px)', (st, w) == (200, 2), (st, w))
falco.alive()

# ---- the ranges ----
for k, v in (('admin_cert_card_s', 4), ('admin_cert_card_s', 301), ('admin_cert_card_grace_s', 4),
             ('admin_cert_card_grace_s', 601), ('admin_cert_card', 'lock')):
    ok('%s=%s refused' % (k, v), settings(**{k: v}) == 400)

# ---- off again ----
settings(admin_cert_card='off', admin_cert_card_s=15, admin_cert_card_grace_s=30)
ok('off again: nginx as it was before', helper(lambda: open(CONF).read() == before), open(CONF).read()[:200])
falco.cert_login()
st, me = falco.j('whoami')
ok('...nothing watched, the policy as before', not (me.get('who') or {}).get('card') and "img-src 'self' data:;" in page_csp(falco))
print(setup('down').strip())
print('ALL %d / %d' % (sum(R), len(R)))
