# t_card4.py VERSION - 1.0.288: the card watched, the kit's 4th edition. On the installed server, through nginx
# and PHP with client certificates (tests/cert/ui_cert_setup.py):
#  - a check waiting on a window of the card's (card-gone {waiting}): out - for a browser already proven; for
#    one never found, nothing (not held, not "cannot be checked");
#  - whoami's card.out_for: how long the card has been out by the server's clock (F5 goes on counting);
#  - the mode changed: the count starts afresh (not ended at once for time counted under grace);
#  - ended by the server: 5 px (the card out), 6 px (another card) - not a bare 403; no session: still 403/3 px;
#  - the page's policy: a name the policy cannot carry - pictures over https.
import json, os, sys, time, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]), flush=True)


src = open(os.path.join(HERE, '..', 'r285', 't_card.py')).read()
g = {'__name__': 't_card_lib', '__file__': os.path.join(HERE, '..', 'r285', 't_card.py'), 'sys': sys}
exec(compile(src[:src.index("print(setup('up').strip())")], 't_card', 'exec'), g)
Browser, setup, helper, CONF, PW = g['Browser'], g['setup'], g['helper'], g['CONF'], g['PW']


def events(text):
    st, got = admin.j('events')
    return text in json.dumps(got, ensure_ascii=False)


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


def card(b):
    return ((b.j('whoami')[1].get('who') or {}).get('card')) or {}


print(setup('up').strip())
admin = Browser()
st, got = admin.j('login', {'name': 'admin', 'password': PW})
ok('the local administrator signs in', st == 200, got)
settings(admin_cert_card='grace', admin_cert_card_s=5, admin_cert_card_grace_s=60)
helper(lambda: 'alive' in open(CONF).read())
time.sleep(4)

# waiting, never found: nothing
falco = Browser('falco')
falco.cert_login()
st, got = falco.j('card-gone', {'why': 'waiting'})
ok('waiting, the card never found in this browser: nothing (not watched, not unable)',
   st == 200 and got.get('watched') is False and not got.get('unable') and not got.get('gone'), got)
ok('...nothing held, still watched', falco.j('status')[0] == 200 and bool(card(falco)), card(falco))

# waiting, proven: out
st, w, hd = Browser('falco', jar=falco.jar).alive()
ok('a check with the card: 1 px (proven)', (st, w) == (200, 1), (st, w))
st, got = falco.j('card-gone', {'why': 'waiting'})
ok('waiting, proven: the card out (grace)', st == 200 and got.get('watched') is True and got.get('gone') is False, got)
ok('...held (423)', falco.j('status')[0] == 423)
c = card(falco)
ok('...whoami: out, out_for counted', c.get('out') is True and isinstance(c.get('out_for'), int), c)
time.sleep(3)
c2 = card(falco)
ok('...out_for goes on (a page loaded again counts from the server\'s time)', c2.get('out_for', 0) >= 3, (c, c2))
ok('...said in the events', events('falco: the card they signed in with is out'))
st, w, hd = Browser('falco', jar=falco.jar).alive()
ok('the card back: 1 px, answered again', (st, w) == (200, 1) and falco.j('status')[0] == 200, (st, w))
ok('...out_for 0', card(falco).get('out_for') == 0 and card(falco).get('out') is False, card(falco))

# the mode changed: counted afresh
st, got = falco.j('card-gone', {'why': 'waiting'})
ok('out again (grace)', got.get('watched') is True and falco.j('status')[0] == 423, got)
settings(admin_cert_card='signout')
time.sleep(1)
st, me = falco.j('whoami')
ok('the mode changed to signout: not ended at once for the time out under grace', bool(me.get('who')), me)
ok('...counted afresh: not out', (me.get('who') or {}).get('card', {}).get('out') is False, me.get('who'))
ok('...answered', falco.j('status')[0] == 200)

# ended by the server: 5 px (signout, no card)
st, w, hd = Browser(jar=falco.jar).alive()
ok('signout: no card - 5 px (ended for its card), not a bare 403', (st, w) == (200, 5), (st, w))
ok('...signed out', not falco.j('whoami')[1].get('who'))
# another card: 6 px
falco = Browser('falco')
falco.cert_login()
st, w, hd = Browser('falco-sid2', jar=falco.jar).alive()
ok('another card: 6 px (ended for another card)', (st, w) == (200, 6), (st, w))
ok('...signed out, said why', not falco.j('whoami')[1].get('who') and
   events('another certificate than the one signed in with was offered'))
# no session at all: as before
st, w, hd = Browser('falco').alive()
ok('no session: 3 px (no cookie), as before', (st, w) == (200, 3), (st, w))
gone = Browser('falco')
gone.cert_login()
import http.cookiejar
kept = http.cookiejar.CookieJar()       # the cookie as a page still holding it would send it
for c in gone.jar:
    kept.set_cookie(c)
gone.j('logout', {})
st, w, hd = Browser('falco', jar=kept).alive()
ok('a session over: 403, as before', st == 403, (st, w))

# the page's policy
settings(admin_cert_card='grace')
falco = Browser('falco')
falco.cert_login()
st, hd, raw = falco.raw('https://127.0.0.1/admin/')
csp = hd.get('Content-Security-Policy') or ''
ok('the page by its address: img-src names the port', 'https://127.0.0.1:8443' in csp, csp)
import urllib.request
req = urllib.request.Request('https://127.0.0.1/admin/', headers={'Host': 'otp_one.lan', 'Accept': 'text/html'})
try:
    with falco.op.open(req, timeout=30) as r:
        st2, csp2 = r.status, r.headers.get('Content-Security-Policy') or ''
except urllib.error.HTTPError as e:
    st2, csp2 = e.code, e.headers.get('Content-Security-Policy') or ''
if st2 == 200:
    ok('a name with an underscore: pictures over https (img-src ... https:)', "img-src 'self' data: https:;" in csp2, csp2)
else:
    print('   (nginx refuses that Host here: %s - the policy not tried)' % st2)

# off: as before
settings(admin_cert_card='off')
ok('off: whoami no card', not card(falco))
print(setup('down').strip())
print('ALL %d / %d' % (sum(R), len(R)))
