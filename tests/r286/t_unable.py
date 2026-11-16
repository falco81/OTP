# t_unable.py VERSION - 1.0.286: a browser that cannot be checked (the kit's 3rd edition, found on a real iPad:
# Safari signs nothing for a page in the background). On the installed server, through nginx and PHP with
# client certificates (tests/cert/ui_cert_setup.py):
#  - allow (the default): the first check without the card, never found before - 4 px, not watched: the
#    event says why (no certificate came), whoami no card, nothing held, card-gone changes nothing more;
#    the same by card-gone {nopicture} and {nocookie} - each reason in the events;
#  - found once (a check with the card): a later one without it is a card taken out (grace: 2 px, 423);
#  - signout: never found, no card - as before (signout mode: 403, signed out);
#  - no cookie: 3 px; another card: 403 even before it was found; the facts say the setting; the range.
import http.cookiejar, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'r285'))
HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util
R = []


def ok(w, c, more=''):
    R.append(bool(c))
    print(('ok   ' if c else 'FAIL ') + w + ('' if c or not more else ' (%s)' % str(more)[:400]), flush=True)


# the browser of t_card.py
src = open(os.path.join(HERE, '..', 'r285', 't_card.py')).read()
g = {'__name__': 't_card_lib', '__file__': os.path.join(HERE, '..', 'r285', 't_card.py'), 'sys': sys}
exec(compile(src[:src.index("print(setup('up').strip())")], 't_card', 'exec'), g)
Browser, setup, helper, CONF = g['Browser'], g['setup'], g['helper'], g['CONF']
PW = g['PW']


def events(text):
    st, got = admin.j('events')
    return text in json.dumps(got, ensure_ascii=False)


print(setup('up').strip())
admin = Browser()
st, got = admin.j('login', {'name': 'admin', 'password': PW})
ok('the local administrator signs in', st == 200, got)


def settings(**kv):
    st, got = admin.j('settings', {'settings': kv})
    if st != 200:
        print('   settings', kv, st, str(got)[:200])
    time.sleep(1.2)
    return st


settings(admin_cert_card='grace', admin_cert_card_s=5, admin_cert_card_grace_s=30)
helper(lambda: 'alive' in open(CONF).read())
time.sleep(4)
st, v = admin.j('certlogin')
ok('the default: allow (the card\'s facts)', v.get('watch_unable') == 'allow', v.get('watch_unable'))

# allow: never found, no certificate - cannot be checked
falco = Browser('falco')
me = falco.cert_login()
ok('falco signs in with the certificate - watched (whoami card)', bool(((me or {}).get('who') or {}).get('card')), me)
st, w, hd = Browser(jar=falco.jar).alive()
ok('allow: the first check without the card, never found - 4 px (cannot be checked)', (st, w) == (200, 4), (st, w))
ok('...said in the events, with why: no certificate came', events("the card of falco's sign-in cannot be checked in this browser - no certificate came with the check"))
st, me = falco.j('whoami')
ok('...not watched from now on: whoami no card, the role kept', not (me.get('who') or {}).get('card') and (me.get('who') or {}).get('role') == 'readonly', me.get('who'))
st, got = falco.j('status')
ok('...nothing held (200)', st == 200, st)
st, w, hd = Browser(jar=falco.jar).alive()
ok('...a later check without the card: nothing (1 px, still signed in)', (st, w) == (200, 1) and falco.j('status')[0] == 200, (st, w))
st, got = falco.j('card-gone', {'why': 'nopicture'})
ok('...card-gone: not watched, nothing', got.get('watched') is False and falco.j('status')[0] == 200, got)

# allow: card-gone first (an iPad: the picture never arrives)
falco = Browser('falco')
falco.cert_login()
st, got = falco.j('card-gone', {'why': 'nopicture'})
ok('allow: card-gone {nopicture} first - unable, nothing held', got.get('unable') is True and falco.j('status')[0] == 200, got)
ok('...said: the check got no answer at all (as an iPad gives)', events('the check got no answer at all (the browser did not sign the connection)'))
falco = Browser('falco')
falco.cert_login()
st, got = falco.j('card-gone', {'why': 'nocookie'})
ok('allow: card-gone {nocookie} - unable, said: no cookie', got.get('unable') is True and events('the browser sent no cookie with the check'), got)
st, w, hd = Browser(jar=http.cookiejar.CookieJar()).alive()
ok('no cookie with the check at all: 3 px', (st, w) == (200, 3), (st, w))

# found once: a later check without the card is a card taken out
falco = Browser('falco')
falco.cert_login()
st, w, hd = falco.alive()
ok('found once (a check with the card): 1 px', (st, w) == (200, 1), (st, w))
st, w, hd = Browser(jar=falco.jar).alive()
ok('...then without it: a card taken out (grace - 2 px)', (st, w) == (200, 2), (st, w))
st, got = falco.j('status')
ok('...held (423)', st == 423, st)
st, got = falco.j('card-gone', {'why': 'nopicture'})
ok('...card-gone now: out, not unable', got.get('watched') is True and not got.get('unable'), got)
falco.alive()

# another card: at once, found or not
falco = Browser('falco')
falco.cert_login()
st, w, hd = Browser('falco-sid2', jar=falco.jar).alive()
ok('another card, before any check found the card: 403, signed out', st == 403 and not falco.j('whoami')[1].get('who'), st)

# signout: never found, no card - as before
settings(admin_cert_card_unable='signout')
st, v = admin.j('certlogin')
ok('A browser that cannot be checked = signout (the facts)', v.get('watch_unable') == 'signout', v.get('watch_unable'))
falco = Browser('falco')
falco.cert_login()
st, w, hd = Browser(jar=falco.jar).alive()
ok('signout: never found, no card - as a card out (grace: 2 px, held)', (st, w) == (200, 2) and falco.j('status')[0] == 423, (st, w))
settings(admin_cert_card='signout')
falco = Browser('falco')
falco.cert_login()
st, got = falco.j('card-gone', {'why': 'nopicture'})
ok('...watching signout: card-gone - signed out', got.get('gone') is True and not falco.j('whoami')[1].get('who'), got)
ok('the value must be allow or signout', settings(admin_cert_card_unable='maybe') == 400)

settings(admin_cert_card='off', admin_cert_card_s=15, admin_cert_card_grace_s=30, admin_cert_card_unable='allow')
helper(lambda: 'alive' not in open(CONF).read())
time.sleep(4)
print(setup('down').strip())
print('ALL %d / %d' % (sum(R), len(R)))
