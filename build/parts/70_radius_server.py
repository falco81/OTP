

# ---------------------------------------------------------------------------
# Deciding: one Access-Request, step by step
# ---------------------------------------------------------------------------
# The order (1.0.33): the realm and whether this client may use it, the
# directory - is the account there, in use, in a group that lets in - and
# its password, and the code last. Somebody who does not know the password
# can then neither guess codes nor lock a token out by guessing them, and a
# code is only used up by a request that would otherwise be let in. (Until
# 1.0.32 the code came first, as the old token server had it.)
#
# Every step is written down - what was asked, what came back, how long it
# took - and kept with the request, so that "why was I refused" is answered
# by opening one row rather than by reading a debug log.

class Decision(object):
    def __init__(self):
        self.steps = []
        self.began = time.time()
        self.result = 'reject'
        self.reason = ''
        self.otp = ''
        self.reply = []                 # [(Name, value)]
        self.realm = ''
        self.user = ''
        self.token_name = ''
        self.display = ''
        self.state = None               # an Access-Challenge's State (1.0.76)
        self.message = ''               # and the words of its second window

    def step(self, what, ok, said='', since=None):
        one = {'what': what, 'ok': ok, 'said': str(said or '')[:600]}
        if since is not None:
            one['ms'] = int((time.time() - since) * 1000)
        self.steps.append(one)
        if debugging('radius'):
            log('radius %s: %s%s' % (self.user or '?', what,
                                     (' - ' + str(said)) if said else ''), 'debug')
        return one

    def refuse(self, reason):
        self.result = 'reject'
        self.reason = reason
        return self


def client_realm_list(client):
    """The realms a client may use, by name, lower case; [] for any."""
    raw = (client or {}).get('realms') or ''
    if isinstance(raw, (list, tuple)):
        got = raw
    else:
        got = re.split(r'[,;\n]+', str(raw))
    return [str(x).strip().lower() for x in got if str(x).strip()]


def ipv6_usable():
    """Can a socket listen on :: here (the kernel's IPv6 on)?"""
    try:
        t = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    except OSError:
        return False
    try:
        t.bind(('::', 0))
        return True
    except OSError:
        return False
    finally:
        t.close()


def realm_main_name(user, realm):
    """novak@dpmo.local as novak@dpmo.cz, where dpmo.local is another suffix
    of the realm whose own is dpmo.cz (1.0.117). Anything else as it is."""
    who, at, where = str(user or '').rpartition('@')
    if at and realm and where.lower() in (realm.get('aliases') or []) and \
            realm.get('suffix') not in (None, '', '*'):
        return '%s@%s' % (who, realm['suffix'])
    return str(user or '')


def realm_names(user, realm):
    """The name as written, then under each suffix of its realm (1.0.117)."""
    out = [str(user or '')]
    who, at, _where = out[0].rpartition('@')
    if at and realm and realm.get('suffix') not in (None, '', '*'):
        for suf in [realm['suffix']] + list(realm.get('aliases') or []):
            n = '%s@%s' % (who, suf)
            if n.lower() not in [x.lower() for x in out]:
                out.append(n)
    return out


class Authenticator(object):
    """What the RADIUS server asks: may this person in, and with what."""

    def __init__(self, store, tokens, dirs):
        self.store = store
        self.tokens = tokens
        self.dirs = dirs                 # name -> Directory

    def directory(self, name):
        return self.dirs.get(str(name or '').lower())

    @staticmethod
    def full_name(user, client_realm):
        """The name as it will be looked up: DOMAIN\\name as name, and the
        client's own realm added to a name that has none - what FreeRADIUS's
        hints file did, NAS by NAS. A dot at the end of the realm is dropped
        (corp.cz. is corp.cz) and a name with nothing before its @ is no
        name at all (1.0.33)."""
        said = str(user or '').strip()
        if said.count('@') > 1:
            # novak@foo@x.cz (1.0.101): the realm by the last @, the account
            # by the first - and a token under the rest, a second one for the
            # same person. Not a name.
            return ''
        if '\\' in said and '@' in said:
            # DOMAIN\\name@realm (1.0.101): the directory finds name, the
            # token is looked for under the whole of it - a second token for
            # the same person, made by whoever has the password before its
            # owner enrols. Not a name.
            return ''
        if '\\' in said:
            said = said.split('\\', 1)[1]
        if '@' in said:
            who, _, where = said.rpartition('@')
            where = where.strip().rstrip('.')
            who = who.strip()
            if not who or not where:
                return ''
            return '%s@%s' % (who, where)
        if not said:
            return ''
        if client_realm:
            said = '%s@%s' % (said, str(client_realm).lstrip('@'))
        return said

    @staticmethod
    def token_name(user, realm):
        if realm and realm.get('token_name') == 'bare':
            # Before the last @, as the realm is found by it (1.0.101).
            return norm_name(user.rpartition('@')[0] or user)
        # Under the realm's own suffix (1.0.117): novak@dpmo.local is
        # novak@dpmo.cz where dpmo.local is another suffix of the realm.
        return norm_name(realm_main_name(user, realm))

    @classmethod
    def token_for(cls, store, user, realm):
        """(the token's name, how it was found). Its own name first; then
        the name as written, for a token made before the suffix became
        another of the realm's (1.0.117); then the same account's token in
        another realm reading the same directory by the account name - the
        one the enrolment pages found and kept (portal_same_person)."""
        mine = cls.token_name(user, realm)
        if store.token(mine) or not realm:
            return mine, ''
        typed = norm_name(user)
        if typed != mine and store.token(typed):
            return typed, 'made before @%s was another suffix of the realm %s' % (
                typed.rpartition('@')[2], realm['name'])
        if realm.get('lookup') == 'sam' and realm.get('directory') and '@' in str(user):
            who = str(user).rpartition('@')[0]
            here = str(realm.get('directory') or '').lower()
            for r in store.realms():
                if not r.get('enabled') or r['id'] == realm['id'] or \
                        str(r.get('directory') or '').lower() != here or \
                        r.get('lookup') != 'sam' or r.get('suffix') in (None, '', '*'):
                    continue
                cand = cls.token_name('%s@%s' % (who, r['suffix']), r)
                if store.token(cand):
                    return cand, 'the same account (%s) in the realm %s, on the same directory' % (
                        who, r['name'])
        return mine, ''

    @staticmethod
    def find_person(ad, user, lookup, realm):
        """The directory entry; by userPrincipalName also under the realm's
        other suffixes (1.0.117): novak@dpmo.local whose UPN is
        novak@dpmo.cz."""
        entry = ad.find_user(user, lookup)
        if entry or lookup != 'upn':
            return entry
        for alt in realm_names(user, realm)[1:]:
            entry = ad.find_user(alt, 'upn')
            if entry:
                return entry
        return None

    def decide(self, user, password, client_realm='', src='', rid='', chap=False,
               how='radius', client=None):
        d = Decision()
        d.user = self.full_name(user, client_realm or CONFIG.get('default_realm') or '')
        if not d.user:
            d.step('a name', False, 'the request carries no User-Name, or only a realm')
            return d.refuse('the request carries no User-Name')
        if d.user != str(user):
            d.step('the name is read as %s' % d.user, True,
                   'the client adds @%s to a name without a realm' % client_realm
                   if client_realm and '@' not in str(user) else '')
        realm = self.store.realm_for(d.user)
        if not realm:
            d.step('a realm for %s' % d.user, False, 'no realm takes this name')
            return d.refuse('no realm takes the name %s' % d.user)
        d.realm = realm['name']
        d.step('the realm is %s' % realm['name'], True, {
            'otp': 'the password is the code from the phone',
            'password_otp': 'the password is the directory password followed by the code',
            'password': 'the password is the directory password alone',
            'challenge': 'the directory password, then the code in a second window'}[
                realm['auth_mode']])
        # Whether this client may use that realm at all (1.0.33): without it
        # the name typed chose the realm, and with it how strictly the
        # person is checked - user@wifi through the VPN, password alone.
        allowed = client_realm_list(client)
        if allowed and realm['name'].lower() not in allowed:
            d.step('the client may use the realm %s' % realm['name'], False,
                   'the client %s may use only: %s' % ((client or {}).get('name') or '?',
                                                       ', '.join(allowed)))
            return d.refuse('the client %s may not use the realm %s'
                            % ((client or {}).get('name') or '?', realm['name']))
        if chap or password is None:
            d.step('a password', False, 'CHAP or no User-Password: a one-time code can only '
                   'travel as PAP')
            return d.refuse('the request carries no User-Password (PAP)')
        if password and any(ord(c) < 32 or c == '\ufffd' for c in password):
            d.step('the password reads as text', False, 'what came is not text - is the shared '
                   'secret the same on both sides?')
            return d.refuse('the password does not decode: the shared secret is probably '
                            'not the same as on the client')
        if not password:
            d.step('a password', False, 'it is empty')
            return d.refuse('the password is empty')
        d.token_name, found_how = self.token_for(self.store, d.user, realm)
        if d.token_name != norm_name(d.user):
            d.step('the token is %s' % d.token_name, True, found_how or (
                'the realm keeps its tokens under @%s' % realm.get('suffix')
                if realm.get('token_name') != 'bare' else 'the realm keeps its tokens under '
                'the name alone'))
        mode = realm['auth_mode']
        # ---- a code in a second window (1.0.76) ---------------------------
        # A token that gets its codes by mail or SMS always signs in so - the
        # password is the directory's and the code is asked for after it,
        # whatever the realm says of a code from the phone; a realm in the
        # "challenge" mode asks so of the app's tokens too. Everybody else
        # signs in exactly as before.
        challenge = None
        tok = self.store.token(d.token_name) if mode != 'password' else None
        kind = token_kind(tok) if tok else None
        if mode == 'challenge':
            if not tok:
                d.step('a token for %s' % d.token_name, False, SAY_NONE)
                d.otp = SAY_NONE
                return d.refuse('Denied by the token server: ' + SAY_NONE)
            challenge = kind
        elif tok and kind in ('mail', 'sms'):
            challenge = kind
        if challenge:
            if tok.get('state') == 'pending':
                d.step('the token of %s' % d.token_name, False, SAY_PENDING)
                d.otp = SAY_PENDING
                return d.refuse('Denied by the token server: ' + SAY_PENDING)
            if challenge in ('mail', 'sms') and challenge not in code_channels():
                why = ('sending mail is not set up' if challenge == 'mail'
                       else 'sending SMS is not set up')
                d.step('a code by %s' % ('mail' if challenge == 'mail' else 'SMS'), False, why)
                return d.refuse('Denied by the token server: the code cannot be sent - ' + why)
            d.step('the code comes in a second window', True,
                   'the token gets %s; the password is the directory password'
                   % CODE_KIND_WORDS[challenge])
        # ---- where the password ends and the code begins -------------------
        code, ad_password = None, None
        guessed = False
        if challenge:
            ad_password = password
        elif mode == 'otp':
            code = password
        elif mode == 'password_otp':
            tok = self.store.token(d.token_name)
            digits = int((tok or {}).get('digits') or CONFIG.get('totp_digits') or 6)
            splits = []
            if len(password) > digits:
                splits.append((password[-digits:], password[:-digits]))
            sd = int(CONFIG.get('scratch_digits') or 8)
            if len(password) > sd and sd != digits:
                splits.append((password[-sd:], password[:-sd]))
            if not splits:
                d.step('the code', False, 'nothing after the password looks like a code')
                d.otp = SAY_BAD
                return d.refuse('Denied by the token server: ' + SAY_BAD)
            code, ad_password = splits[0]
            if len(splits) > 1:
                guessed = splits[1][1]
                # Which one: the code that is right now, found with a dry
                # check that counts nothing and writes nothing - so one
                # password costs the directory one try, not two.
                for c, rest in splits:
                    ok, _said, _f = self.tokens.check(d.token_name, c, how=how, src=src,
                                                      rid=rid, dry=True, quiet=True)
                    if ok:
                        code, ad_password = c, rest
                        guessed = False
                        break
        # ---- the directory -----------------------------------------------
        entry = None
        lookup = realm.get('lookup') or ''
        if lookup not in ('upn', 'sam'):
            # No way chosen: by the form of the name. A realm with a directory
            # always asks it - its groups and a switched-off account are never
            # skipped because nobody picked how to look a name up.
            lookup = 'upn' if '@' in d.user else 'sam'
        if (realm.get('groups') or []) and not realm.get('directory'):
            d.step('the groups of %s' % d.user, False, 'the realm names groups and no directory '
                   'to ask them of')
            return d.refuse('account does not pass LDAP group filter(s): the realm %s has no '
                            'directory' % realm['name'])
        if realm.get('directory'):
            ad = self.directory(realm['directory'])
            if not ad:
                d.step('the directory %s' % realm['directory'], False, 'it is not set up')
                return d.refuse('the directory %s is not set up' % realm['directory'])
            t = time.time()
            try:
                entry = self.find_person(ad, d.user, lookup, realm)
            except LdapError as e:
                d.step('look %s up in %s' % (d.user, ad.name), False, str(e), t)
                return d.refuse('LDAP server(s) have gone away' if isinstance(
                    e, LdapUnreachable) else 'the directory could not be asked: %s' % e)
            if not entry:
                d.step('look %s up in %s' % (d.user, ad.name), False,
                       'by %s: there is no such account' % {'upn': 'userPrincipalName',
                                                           'sam': 'sAMAccountName'}.get(lookup,
                                                                                         lookup),
                       t)
                return d.refuse('account does not pass LDAP user filter: %s is not in %s'
                                % (d.user, ad.name))
            d.display = entry.get('display') or ''
            if entry.get('many'):
                # Two accounts answer to the name (1.0.57): which one would
                # be checked is chance, so neither is.
                d.step('look %s up in %s' % (d.user, ad.name), False,
                       'more than one account answers to the name', t)
                return d.refuse('more than one account in %s answers to %s'
                                % (ad.name, d.user))
            d.step('found %s' % entry['dn'], True, entry.get('display') or '', t)
            if realm.get('check_disabled', 1):
                why = entry_unusable(entry)
                if why:
                    d.step('the account is in use', False, why)
                    if entry.get('disabled'):
                        return d.refuse('the account is disabled in the directory')
                    if entry.get('expires') and entry['expires'] < time.time():
                        return d.refuse('the account has expired in the directory')
                    return d.refuse('the account may not sign in: %s' % why)
            if mode in ('password', 'password_otp') or challenge:
                pw = password if mode == 'password' else ad_password
                if code is not None or challenge:
                    # A token locked out or paused is refused before its
                    # password is tried in the directory (1.0.57).
                    stop = self.tokens.blocked(d.token_name)
                    if stop:
                        d.step('the code for the token %s' % d.token_name, False, stop)
                        return d.refuse('Denied by the token server: ' + stop)
                t = time.time()
                try:
                    ad.password_ok(entry, pw)
                    d.step('the directory password', True, '', t)
                except LdapError as e:
                    d.step('the directory password', False, str(e), t)
                    if guessed and not isinstance(e, LdapUnreachable) and \
                            int((tok or {}).get('scratch_left') or 0) > 0:
                        # No split gave a right code, and the password before
                        # a code from the phone was refused (1.0.101). If the
                        # password was right, what followed it was a wrong
                        # recovery code - nothing counted that before, past
                        # the pause and the lockout. The directory is not asked
                        # twice to find out (a typo would count twice there);
                        # each such request is counted towards the token's
                        # recovery codes instead: past a day's few, they are
                        # not taken for a while. Codes from the app go on.
                        scratch_guard_note(self.store, d.token_name,
                                           getattr(REQUEST_PLACE, 'v', ''))
                    return d.refuse('the directory refused the password: %s' % e
                                    if not isinstance(e, LdapUnreachable)
                                    else 'LDAP server(s) have gone away')
            wanted = realm.get('groups') or []
            if wanted:
                t = time.time()
                try:
                    have = ad.groups_of(entry, bool(realm.get('nested', 1)))
                except LdapError as e:
                    d.step('the groups of %s' % d.user, False, str(e), t)
                    return d.refuse('LDAP server(s) have gone away')
                hit = group_matches(wanted, have, ad)
                if not hit:
                    names = ', '.join(cn_of(w.get('group') or '') or w.get('group') or ''
                                      for w in wanted[:6]) + (' …' if len(wanted) > 6 else '')
                    d.step('a member of one of %d group(s)' % len(wanted), False,
                           'a member of %d group(s)%s, none of them one of: %s'
                           % (len(have), ' (nested counted)' if realm.get('nested', 1) else '',
                              names), t)
                    return d.refuse('account does not pass LDAP group filter(s): %s is in '
                                    'none of %s' % (d.user, names))
                d.step('a member of %s' % hit['group'], True, '', t)
                try:
                    d.reply.extend(reply_lines(hit.get('reply') or ''))
                except RadiusError as e:
                    # Never an Accept without what limits it (1.0.57).
                    d.step('the answer of the group %s' % hit['group'], False, str(e))
                    return d.refuse('the answer for the group cannot be built: %s' % e)
        elif mode in ('password', 'password_otp') or challenge:
            d.step('the directory password', False, 'the realm has no directory to ask')
            return d.refuse('the realm %s has no directory' % realm['name'])
        if challenge:
            try:
                reply = reply_lines(realm.get('reply') or '') + d.reply
            except RadiusError as e:
                d.step('the answer', False, str(e))
                return d.refuse('the answer of the realm cannot be built: %s' % e)
            return self.challenge_start(d, realm, tok, challenge, reply, client, src, rid)
        # ---- the code, last ----------------------------------------------
        if code is not None:
            t = time.time()
            ok, said, facts = self.tokens.check(d.token_name, code, how=how, src=src, rid=rid)
            d.otp = said
            d.step('the code for the token %s' % d.token_name, ok, said, t)
            if not ok:
                return d.refuse('Denied by the token server: ' + said)
        try:
            d.reply = reply_lines(realm.get('reply') or '') + d.reply
        except RadiusError as e:
            d.step('the answer', False, str(e))
            return d.refuse('the answer of the realm cannot be built: %s' % e)
        d.result = 'accept'
        d.step('let in', True, ', '.join('%s = %s' % p for p in d.reply))
        return d


    # ---- the second window (1.0.76) ----------------------------------------------
    def challenge_start(self, d, realm, tok, kind, reply, client, src, rid):
        """The password was right: a code sent (mail, SMS) or asked for (the
        app), and an Access-Challenge to say so."""
        name = d.token_name
        data = {'name': name, 'user': d.user, 'realm': realm['name'],
                'client': (client or {}).get('id'), 'kind': kind,
                'reply': [list(p) for p in reply], 'src': src,
                # What the first request proved (1.0.118), for the second
                # one's decision to show: the account, its password, its group.
                'checked': [str(one.get('what') or '')[:200] for one in d.steps
                            if one.get('ok') and not str(one.get('what') or '').startswith(
                                ('the realm is', 'the name is read', 'the code comes'))][:8],
                'rid': str(rid or '')[:120]}
        if kind in ('mail', 'sms'):
            dest = str(tok.get('dest') or '')
            if not dest:
                d.step('where the code goes', False, 'the token has no address or number')
                return d.refuse('Denied by the token server: the token has nowhere to send '
                                'a code')
            if not code_send_allowed(self.store, name):
                said = ('%d codes were sent in %d min already'
                        % (int(CONFIG.get('code_send_max') or 5),
                           int(CONFIG.get('code_send_window_min') or 15)))
                d.step('a code sent', False, said)
                d.otp = 'Too many codes sent'
                return d.refuse('Denied by the token server: too many codes sent - ' + said)
            code = code_new()
            data['code'] = code_hash(name, code)
            data['dest'] = dest          # the answer checks the token still sends there (1.0.94)
            d.state = chal_new(self.store, data)
            code_send_later(self.store, kind, dest, code, name, rid)
            d.message = code_words('ask_' + kind, lang=token_lang(tok), dest=dest_masked(kind, dest))
            d.step('a code sent by %s to %s' % ('mail' if kind == 'mail' else 'SMS',
                                                 dest_masked(kind, dest)), True,
                   'good for %d s' % int(CONFIG.get('code_ttl_s') or 300))
            d.otp = 'Code sent by %s' % ('mail' if kind == 'mail' else 'SMS')
        else:
            d.state = chal_new(self.store, data)
            d.message = code_words('ask_totp', lang=token_lang(tok))
            d.step('the code from the app asked for', True, '')
            d.otp = 'Code asked for'
        d.result = 'challenge'
        d.reason = 'the code is asked for in a second window'
        return d

    def answer(self, user, password, state, client_realm='', src='', rid='', chap=False,
               how='radius', client=None):
        """The second Access-Request: the code typed into the second window,
        with the State of the challenge."""
        d = Decision()
        d.user = self.full_name(user, client_realm or CONFIG.get('default_realm') or '')
        chal, raw = chal_get(self.store, state)
        if not chal:
            d.step('the question this answers', False, 'there is none - it was answered, or '
                   'ran out, or was asked by another server')
            return d.refuse('the code was asked for too long ago: sign in again')
        d.realm = chal.get('realm') or ''
        d.token_name = name = chal.get('name') or ''
        kind = chal.get('kind') or 'totp'
        if float(chal.get('exp') or 0) < time.time():
            chal_take(self.store, state, raw)
            d.step('the question this answers', False, 'it ran out %s' % stamp(chal.get('exp')))
            d.otp = 'The code ran out'
            return d.refuse('Denied by the token server: the code ran out - sign in again')
        if norm_name(chal.get('user') or '') != norm_name(d.user) or \
                chal.get('client') != (client or {}).get('id'):
            d.step('the question this answers', False, 'it was asked of another name or through '
                   'another client')
            return d.refuse('the answer does not belong to the question it names')
        d.step('the answer to the code asked for: %s' % CODE_KIND_WORDS.get(kind, kind), True,
               'asked %s' % stamp(chal.get('made')))
        if chal.get('checked'):
            # Checked once, with the first request (1.0.118): the second
            # carries the code alone, and is let in on what the first proved.
            d.step('checked with the first request%s' % (
                ' (%s)' % chal['rid'] if chal.get('rid') else ''), True,
                '; '.join(chal['checked']))
        if chap or not password:
            d.step('the code', False, 'nothing came, or not as PAP')
            return d.refuse('the request carries no code (PAP)')
        code = str(password).strip()
        t = time.time()
        # A try is taken before the code is looked at (1.0.101): written to
        # the question with a conditional update, so of answers that came
        # at the same moment only as many as there are tries are compared -
        # not all of them, each having read "0 tries so far".
        limit = int(CONFIG.get('code_tries') or 3)
        for _round in range(64):
            if int(chal.get('tries') or 0) >= limit:
                chal_take(self.store, state, raw)
                d.step('the code for the token %s' % name, False, 'no tries left', t)
                d.otp = SAY_RATE
                return d.refuse('Denied by the token server: no tries left - sign in again')
            nxt = dict(chal)
            nxt['tries'] = int(chal.get('tries') or 0) + 1
            if chal_put(self.store, state, raw, nxt):
                chal, raw = nxt, json.dumps(nxt)
                break
            chal, raw = chal_get(self.store, state)
            if not chal:
                d.step('the question this answers', False, 'answered meanwhile')
                return d.refuse('the code was asked for too long ago: sign in again')
        else:
            return d.refuse('Denied by the token server: too many answers at once')
        if kind in ('mail', 'sms'):
            stop = self.tokens.blocked(name)
            # The token as it is now (1.0.94): taken away, made anew for the
            # app, or sending elsewhere since - the code sent is nothing then.
            now_tok = self.store.token(name)
            if not stop and (not now_tok or token_kind(now_tok) != kind or (
                    chal.get('dest') and str(now_tok.get('dest') or '') != chal.get('dest'))):
                stop = 'the token changed since the code was sent - sign in again'
            if stop:
                chal_take(self.store, state, raw)
                d.step('the code for the token %s' % name, False, stop, t)
                d.otp = stop
                return d.refuse('Denied by the token server: ' + stop)
            if re.fullmatch(r'[0-9]{4,10}', code, re.ASCII) and \
                    hmac.compare_digest(code_hash(name, code), str(chal.get('code') or '')):
                ok, said = True, 'Code sent by %s accepted' % ('mail' if kind == 'mail' else 'SMS')
                if once_take(self.store, 'chal', name, hashlib.sha256(bytes(state)).hexdigest()):
                    chal_drop(self.store, state)
                    self.tokens.used_sent(name, kind)
                    self.tokens._said(name, True, said, how, src, rid)
                else:
                    ok, said = False, SAY_REUSED
            else:
                # A recovery code - or a wrong code, counted as one from the
                # phone is, towards the lockout.
                ok, said, _f = self.tokens.check(name, code, how=how, src=src, rid=rid)
                if ok:
                    chal_drop(self.store, state)
        else:
            # The code is taken once by the token itself (its step, once_take):
            # the question is done with, even if a second answer to it counted
            # a try meanwhile - that refused the right code and used it up.
            ok, said, _f = self.tokens.check(name, code, how=how, src=src, rid=rid)
            if ok:
                chal_drop(self.store, state)
        d.otp = said
        d.step('the code for the token %s' % name, ok, said, t)
        if ok:
            d.reply = [tuple(p) for p in chal.get('reply') or []]
            d.result = 'accept'
            d.step('let in', True, ', '.join('%s = %s' % p for p in d.reply))
            return d
        if said == SAY_REUSED or chal['tries'] >= limit or self.tokens.blocked(name):
            chal_take(self.store, state, raw)
            return d.refuse('Denied by the token server: ' + said)
        d.state = state
        d.message = code_words('again', lang=token_lang(self.store.token(name)))
        d.result = 'challenge'
        d.reason = 'the code was not right: asked again (%d of %d)' % (
            chal['tries'], limit)
        return d


# ---------------------------------------------------------------------------
# The RADIUS server
# ---------------------------------------------------------------------------
class SentReply(bytes):
    """An answer, and whether it has gone out already."""
    sent = False
    late = False


class RadiusServer(object):
    """Two UDP sockets - authentication and accounting - read by a thread
    each and answered by a pool of workers."""

    def __init__(self, daemon):
        self.d = daemon
        self.socks = {}
        self.jobs = queue.Queue(maxsize=5000)
        # duplicate key -> (time, reply or None), oldest first, never more
        # than SEEN_MAX: a flood fills it to the brim and no further (1.0.33).
        self.seen = collections.OrderedDict()
        self.seen_lock = threading.Lock()
        self.unknown_said = {}
        self.unknown_lock = threading.Lock()
        # What is not written down one by one - malformed packets, and more
        # than a few unknown addresses a minute - is counted and summed up
        # once a minute instead (1.0.33): a flood of junk was a row each.
        self.quiet = collections.Counter()
        self.quiet_at = time.time()
        self.drops_this_minute = 0
        # Clients that have sent a right Message-Authenticator (1.0.33).
        self.ma_seen = set()
        self.ma_asked = {}
        # Refusals waiting out radius_reject_delay_ms (1.0.36).
        self.late = []
        self.late_lock = threading.Lock()
        self.late_wake = threading.Event()
        self.late_thread = None
        self.workers = []
        self.readers = []
        self.stop_flag = False
        self.counts = collections.Counter()
        self.bound = []
        self.trouble = ''

    # ---- the sockets -------------------------------------------------------------
    def want(self):
        bind = str(CONFIG.get('radius_bind') or '0.0.0.0')
        if bind == '::' and not ipv6_usable():
            # IPv4 and IPv6 asked for, on a machine without IPv6 (1.0.119):
            # IPv4 still, not RADIUS on nothing.
            log_sparing('radius-no-v6', 'radius: IPv6 is not on this machine - listening on '
                        'IPv4 (0.0.0.0) only', 'warn', every=3600)
            bind = '0.0.0.0'
        out = [('auth', bind, int(CONFIG.get('radius_auth_port') or 1812))]
        if int(CONFIG.get('radius_acct_port') or 0):
            out.append(('acct', bind, int(CONFIG.get('radius_acct_port'))))
        return out

    def start(self):
        self.stop_flag = False
        self.open_sockets()
        for i in range(int(CONFIG.get('radius_workers') or 16)):
            t = threading.Thread(target=self.work, name='radius-%d' % i, daemon=True)
            t.start()
            self.workers.append(t)

    def open_sockets(self):
        want = self.want()
        if [(k, b, p) for k, (b, p, _s) in sorted(self.socks.items())] == sorted(want):
            return
        # Only what changed is closed and opened again (1.0.67): the auth port
        # changed closed the accounting socket too, and binding it again while
        # its reader was still inside recvfrom failed - accounting stopped.
        keep = {}
        wanted = {(k, b, p) for k, b, p in want}
        old_readers = []
        for kind, (b, p, sock) in list(self.socks.items()):
            if (kind, b, p) in wanted:
                keep[kind] = (b, p, sock)
                continue
            try:
                sock.close()
            except OSError:
                pass
            old_readers += [t for t in self.readers if t.name == 'radius-' + kind]
        self.socks = dict(keep)
        for t in old_readers:
            t.join(2.5)             # out of its recvfrom (1 s timeout) before the port is taken again
        self.readers = [t for t in self.readers if t.is_alive()]
        self.bound = ['%s:%d/%s' % (b, p, k) for k, (b, p, _s) in sorted(keep.items())]
        troubles = []
        for kind, bind, port in want:
            if kind in keep:
                continue
            fam = socket.AF_INET6 if ':' in bind else socket.AF_INET
            try:
                sock = socket.socket(fam, socket.SOCK_DGRAM)
            except OSError as e:
                # IPv6 switched off on the machine (1.0.94): said, as a port in
                # use is - it killed the daemon at start, round and round.
                troubles.append('%s:%d (%s) could not be listened on: %s' % (bind, port, kind, e))
                continue
            # No SO_REUSEADDR: on UDP it lets a second process bind the very same
            # port and take half the packets. A port in use has to say so.
            if fam == socket.AF_INET6:
                try:
                    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                except OSError:
                    pass
            err = None
            for _try in range(6):
                try:
                    sock.bind((bind, port))
                    err = None
                    break
                except OSError as e:
                    err = e
                    time.sleep(0.5)
            if err is not None:
                troubles.append('%s:%d (%s) could not be listened on: %s' % (bind, port, kind, err))
                sock.close()
                continue
            sock.settimeout(1.0)
            self.socks[kind] = (bind, port, sock)
            self.bound.append('%s:%d/%s' % (bind, port, kind))
            t = threading.Thread(target=self.read, args=(kind, sock), name='radius-' + kind,
                                 daemon=True)
            t.start()
            self.readers.append(t)
        self.trouble = '; '.join(troubles)
        if troubles:
            self.d.store.add_event('radius', self.trouble, 'bad')
        else:
            log('RADIUS listening on %s' % ', '.join(self.bound))

    def stop(self):
        self.stop_flag = True
        for _b, _p, sock in self.socks.values():
            try:
                sock.close()
            except OSError:
                pass

    def read(self, kind, sock):
        while not self.stop_flag:
            try:
                data, peer = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                if self.socks.get(kind, (None, None, None))[2] is not sock:
                    return
                time.sleep(0.2)
                continue
            if self.socks.get(kind, (None, None, None))[2] is not sock:
                return
            try:
                self.jobs.put_nowait((kind, sock, data, peer, time.time()))
            except queue.Full:
                self.counts['overflow'] += 1

    def work(self):
        while not self.stop_flag:
            try:
                kind, sock, data, peer, arrived = self.jobs.get(timeout=1.0)
            except queue.Empty:
                continue
            # Older than any NAS waits (1.0.57): after a stall the queue held
            # minutes of requests whose NAS had long given up, each with its
            # directory binds and its code used up, ahead of the new ones.
            # 10 s (1.0.149): past what a VPN waits for an answer before it asks
            # again or asks the other node - 15 s worked on requests long given
            # up behind a slow directory, each using its code up.
            if time.time() - arrived > int(CONFIG.get('radius_stale_s') or 10):
                self.counts['stale'] += 1
                with self.unknown_lock:
                    self.quiet['too old to answer'] += 1
                continue
            try:
                self.handle(kind, sock, data, peer, arrived)
            except DbError as e:
                # Not answered, as any request while the database is away.
                self.counts['no_database'] += 1
                log_sparing('radius-db', 'RADIUS requests go unanswered: %s'
                            % str(e).split('\n')[0][:200], 'error')
            except Exception as e:
                # Sparingly (1.0.59): a packet that breaks it once breaks it
                # every time it is sent, by anybody using the NAS's address.
                log_sparing('radius-broke:%s:%s' % (type(e).__name__, str(e)[:60]),
                            'a RADIUS request from %s broke: %s\n%s'
                            % (peer[0], e, traceback.format_exc()), 'error', every=300)

    # ---- one packet -----------------------------------------------------------
    def handle(self, kind, sock, data, peer, arrived):
        ip, port = peer[0], peer[1]
        if ip.startswith('::ffff:'):
            ip = ip[7:]
        self.counts['packets'] += 1
        self.sum_up()
        # In maintenance nothing is answered (1.0.37): the VPN takes this
        # node for down and asks the other, as it would any node that is.
        if maintenance_now(self.d.store).get('on'):
            self.counts['maintenance'] += 1
            return
        client = self.d.store.client_for(ip)
        try:
            pkt = Packet.parse(data)
        except RadiusError as e:
            self.counts['malformed'] += 1
            # Only from a client is one written down, and then sparingly:
            # anybody can send junk to the port, from any address.
            if client:
                self.drop(ip, port, '', 'not a RADIUS packet: %s' % e, client=client, sparing=True)
            else:
                with self.unknown_lock:
                    self.quiet['malformed from %s' % ip if len(self.quiet) < 1000
                               else 'malformed, from other addresses'] += 1
            return
        if not client:
            self.counts['unknown'] += 1
            self.drop(ip, port, pkt.text(1), 'the address %s is not one of the clients' % ip,
                      pkt=pkt, unknown=True)
            return
        secret = (client.get('_secret') or '').encode('utf-8')
        if not secret:
            self.drop(ip, port, pkt.text(1), 'the secret of the client %s cannot be opened '
                      'on this machine' % client['name'], pkt=pkt, client=client)
            return
        # The whole packet in the key (1.0.57), as FreeRADIUS compares it: a
        # made-up packet with the same ident and authenticator from the NAS's
        # address can no longer stand in for the real one.
        key = (ip, port, pkt.ident, pkt.authenticator, kind, hashlib.sha256(data).digest()[:16])
        window = int(CONFIG.get('radius_dup_window_s') or 0)
        if window:
            with self.seen_lock:
                got = self.seen.get(key)
                if got and arrived - got[0] < window:
                    self.counts['repeated'] += 1
                    # A refusal sent late is given to a repeat once it went
                    # (1.0.136) - before, the NAS's repeats got nothing and it
                    # took the server for dead.
                    if got[1] and time.time() >= (got[2] if len(got) > 2 else 0):
                        try:
                            sock.sendto(got[1], peer)
                        except OSError:
                            pass
                    return
                self.seen[key] = (arrived, None)
                self.seen.move_to_end(key)
                # Old ones go from the front; past the limit the oldest go
                # whatever their age - never a rebuild of the whole table.
                cut = arrived - window
                while self.seen:
                    k0, v0 = next(iter(self.seen.items()))
                    if v0[0] >= cut and len(self.seen) <= self.SEEN_MAX:
                        break
                    self.seen.popitem(last=False)
        try:
            if kind == 'acct':
                reply = self.accounting(pkt, client, ip, port, secret, arrived)
            elif pkt.code == STATUS_SERVER:
                reply = self.status(pkt, client, ip, port, secret)
            elif pkt.code == ACCESS_REQUEST:
                remember = None
                if window:
                    def remember(b, key=key):
                        # The answer kept for a repeat the moment it is sent
                        # (1.0.101), not after it is written down: a repeat
                        # coming meanwhile got nothing.
                        with self.seen_lock:
                            if key in self.seen:
                                self.seen[key] = (arrived, b)
                reply = self.access(pkt, client, ip, port, secret, arrived, sock, peer, remember)
            else:
                # Not proven to come from the client: written down sparingly
                # (1.0.57) - anybody can send it from the NAS's address.
                self.drop(ip, port, pkt.text(1), 'a %s is not something this port answers'
                          % CODE_WORDS.get(pkt.code, 'code %d' % pkt.code), pkt=pkt,
                          client=client, sparing=True)
                reply = None
        except BaseException:
            # Nothing answered: a repeat of it is not swallowed as "repeated"
            # for the whole window (1.0.57).
            if window:
                with self.seen_lock:
                    self.seen.pop(key, None)
            raise
        if reply and not getattr(reply, 'sent', False):
            try:
                sock.sendto(reply, peer)
            except OSError as e:
                log('the answer to %s could not be sent: %s' % (ip, e), 'warn')
        if window:
            with self.seen_lock:
                # A refusal still waiting out its delay is not handed to a
                # repeat of the request either (1.0.36): it would have skipped
                # the wait.
                if reply is None and pkt.code == ACCESS_REQUEST:
                    # Left unanswered (no database, 1.0.59): the NAS's repeat
                    # is tried again, not swallowed as "repeated".
                    self.seen.pop(key, None)
                elif key in self.seen:
                    self.seen[key] = (arrived, bytes(reply) if reply else None,
                                      getattr(reply, 'late_until', 0))
        try:
            self.d.store.client_seen(client['id'])
        except Exception as e:                          # noqa: BLE001
            log_sparing('radius-client-seen', 'the client %s could not be marked as seen: %s'
                        % (client['name'], str(e).split('\n')[0][:200]), 'warn')

    SEEN_MAX = 20000

    def sum_up(self):
        """Once a minute, what was only counted, in one line."""
        t = time.time()
        if t - self.quiet_at < 60:
            return
        with self.unknown_lock:
            if t - self.quiet_at < 60:
                return
            said, self.quiet = self.quiet, collections.Counter()
            self.quiet_at = t
            self.drops_this_minute = 0
        if said:
            top = ', '.join('%s: %d' % kv for kv in said.most_common(8))
            try:
                self.d.store.add_event('radius', 'not answered and not written down one by one '
                                       'in the last minute: %d packet(s) - %s'
                                       % (sum(said.values()), top), 'warn')
            except Exception as e:                      # noqa: BLE001
                log('could not write the minute\'s summary: %s' % e, 'warn')

    def drop(self, ip, port, user, reason, pkt=None, client=None, unknown=False,
             sparing=False):
        """A packet that is not answered: written down - for an unknown
        address only once a minute, so a VPN pointed here before it was
        added does not fill the log, and never more than 30 a minute in
        all, so a flood from made-up addresses does not either (1.0.33)."""
        self.counts['dropped'] += 1
        if unknown or sparing:
            if unknown and not CONFIG.get('radius_unknown_log', 1):
                return
            with self.unknown_lock:
                t = time.time()
                last = self.unknown_said.get(ip, 0)
                if t - last < 60 or self.drops_this_minute >= 30:
                    # Bounded (1.0.57): a flood from made-up addresses made
                    # one key each until the minute was up.
                    self.quiet[(('unknown address %s' if unknown else 'dropped from %s') % ip)
                               if len(self.quiet) < 1000 else 'from other addresses'] += 1
                    return
                self.unknown_said[ip] = t
                self.drops_this_minute += 1
                if len(self.unknown_said) > 4000:
                    # Kept to the newest addresses, so a scan of the port
                    # cannot grow this table without end.
                    newest = sorted(self.unknown_said.items(), key=lambda kv: kv[1])[-2000:]
                    self.unknown_said = dict(newest)
        self.d.store.radius_add({
            'ts': time.time(), 'client': (client or {}).get('name') or '', 'nas_ip': ip,
            'src': '%s:%d' % (ip, port), 'packet': CODE_WORDS.get(pkt.code, '?') if pkt else '?',
            'username': str(user or '')[:190], 'realm': '', 'calling': '', 'called': '',
            'result': 'drop', 'reason': reason[:500], 'otp': '', 'rid': '', 'took_ms': 0,
            'attrs': json.dumps(pkt.words() if pkt else []), 'reply': '[]',
            'steps': json.dumps([{'what': 'answered', 'ok': False, 'said': reason}]),
            'device': '', 'tunnel': ''})
        if unknown:
            self.d.store.add_event('radius', 'a request from %s, which is not a client, was '
                                   'not answered' % ip, 'warn')

    def ma_check(self, pkt, client, secret, ip, port):
        """Whether the Message-Authenticator lets this one through."""
        got = pkt.message_authenticator_ok(secret)
        if got is False:
            self.drop(ip, port, pkt.text(1), 'the Message-Authenticator is wrong: the shared '
                      'secret is not the same as on the client', pkt=pkt, client=client,
                      sparing=True)
            return False
        if got is True:
            # Per address of the client (1.0.57): one device of a range that
            # sends it no longer made it required of all the others. Only an
            # Access-Request's makes it required (1.0.59): a Status-Server
            # always carries one, and a monitor asking that from the NAS's
            # address had every plain PAP request after it dropped.
            if pkt.code == ACCESS_REQUEST and (client['id'], ip) not in self.ma_seen:
                self.ma_seen.add((client['id'], ip))
                # Kept in the database too (1.0.101): a restart, or the other
                # node, no longer forgets that this NAS signs its requests.
                try:
                    # Under this node's name (1.0.101): one key written by
                    # both nodes at once stopped replication on the second.
                    self.d.store.set_meta('maseen:%s:%s:%s' % (node_name(), client['id'], ip),
                                          '1')
                except Exception:                       # noqa: BLE001
                    pass
            return True
        # None: there is none. A client that has sent one before must go on
        # sending one (1.0.33) - what is stripped off on the way, as
        # BlastRADIUS does, is refused.
        sticky = CONFIG.get('radius_ma_sticky', 1) and self.ma_known(client['id'], ip)
        # Proxy-State and no Message-Authenticator: the shape BlastRADIUS
        # needs (CVE-2024-3596), refused as FreeRADIUS's limit_proxy_state
        # does (1.0.57).
        if pkt.code == ACCESS_REQUEST and pkt.all(33):
            self.drop(ip, port, pkt.text(1), 'Proxy-State without a Message-Authenticator '
                      '(the shape of a BlastRADIUS forgery)', pkt=pkt, client=client,
                      sparing=True)
            return False
        if client.get('require_ma') or pkt.code == STATUS_SERVER or sticky:
            self.drop(ip, port, pkt.text(1), 'there is no Message-Authenticator, and this '
                      'client must send one%s' % (' - it has sent one before' if sticky and
                                                  not client.get('require_ma') else ''),
                      pkt=pkt, client=client, sparing=True)
            return False
        return True

    def ma_known(self, cid, ip):
        """Whether this address of the client has signed a request before -
        here, or on the other node, or before a restart (1.0.101). Looked up
        at most once a minute for an address that has not."""
        if (cid, ip) in self.ma_seen:
            return True
        t = time.time()
        if self.ma_asked.get((cid, ip), 0) > t - 60:
            return False
        if len(self.ma_asked) > 20000:
            self.ma_asked.clear()
        self.ma_asked[(cid, ip)] = t
        try:
            want = ':%s:%s' % (cid, ip)
            for r in self.d.store.db.rows("SELECT k FROM meta WHERE k LIKE 'maseen:%' AND "
                                          "substr(k, length(k) - ? + 1) = ?",
                                          (len(want), want)):
                if r['k'].split(':', 2)[-1] == want[1:]:
                    self.ma_seen.add((cid, ip))
                    return True
        except Exception as e:                          # noqa: BLE001
            # Not known is not "it never signed" (1.0.149): the database not
            # answering let an unsigned request past the rule that a client
            # which signs must always sign. Asked again next time, and this
            # request is not answered.
            self.ma_asked.pop((cid, ip), None)
            raise DbError('whether %s signs its requests could not be read: %s' % (ip, e))
        return False

    def status(self, pkt, client, ip, port, secret):
        if not CONFIG.get('radius_status_server', 1):
            return None
        if not self.ma_check(pkt, client, secret, ip, port):
            return None
        self.counts['status'] += 1
        return build_reply(pkt, ACCESS_ACCEPT, [attr_bytes('Reply-Message', 'otp is alive')],
                           secret, True)

    def access(self, pkt, client, ip, port, secret, arrived, sock=None, peer=None,
               remember=None):
        if not self.ma_check(pkt, client, secret, ip, port):
            return None
        rid = '%s:%d' % (ip, port)
        user = pkt.text(1)
        try:
            password = pkt.password(secret)
        except RadiusError:
            password = None
        chap = pkt.get(3) is not None
        # Another secret leaves control characters in what comes out (random
        # bytes); a password in another encoding than UTF-8 (cp1250, say)
        # does not, and is refused as before - not left unanswered.
        unreadable = pkt.get(2) is not None and (
            password is None or re.search(r'[\x01-\x1f\x7f]', password) is not None)
        if unreadable and not chap and pkt.get(80) is None:
            # A password that does not come out (another secret) and nothing
            # proving the packet is the client's: not written down one row a
            # packet (1.0.136) - anyone can send such from the NAS's address,
            # thousands a second. The NAS, had it sent it, could not have
            # read a refusal made with this secret either.
            self.drop(ip, port, user, 'the password cannot be read with this client\'s shared '
                      'secret (and there is no Message-Authenticator)', pkt=pkt,
                      client=client, sparing=True)
            return None
        words = pkt.words()
        w = dict(words)
        state = pkt.get(24)
        # Sign-in protection (1.0.137): a place blocked for guessing is
        # refused at once - nothing of it checked, nothing counted against a
        # token.
        # Never in the way of an answer: whatever goes wrong in it, the
        # request is decided as it would be without it.
        try:
            src = guard_source(w) if guard_on() else ''
            if src and guard_trusted(src):
                src = ''
            blocked = guard_blocked(self.d, src) if src else None
        except Exception as e:                          # noqa: BLE001
            log_sparing('radius-guard', 'the sign-in protection: %s' % e, 'warn')
            src, blocked = '', None
        # Where the person is, for the recovery codes' guard (1.0.149).
        try:
            REQUEST_PLACE.v = guard_source(w)
        except Exception:                               # noqa: BLE001
            REQUEST_PLACE.v = ''
        try:
            if blocked:
                d = Decision()
                d.user = str(user or '')[:190]
                d.step('sign-in protection', False, '%s is blocked for %s more: %s' % (
                    src, guard_left(blocked[0]), blocked[1]))
                d.refuse('Denied by the token server: too many wrong sign-ins from %s - '
                         'blocked for a while' % src)
            elif state is not None and bytes(state).startswith(CHAL_PREFIX):
                # The code from the second window (1.0.76).
                d = self.d.auth.answer(user, password, bytes(state), client.get('realm') or '',
                                       src=ip, rid=rid, chap=chap, client=client)
            else:
                d = self.d.auth.decide(user, password, client.get('realm') or '', src=ip,
                                       rid=rid, chap=chap, client=client)
        except DbError as e:
            # The database gone (1.0.59): no answer, as a node in maintenance
            # gives none - the VPN asks the other node, where a refusal would
            # have refused everybody until the database was back.
            self.counts['no_database'] += 1
            log_sparing('radius-db', 'RADIUS requests go unanswered: the database cannot be '
                        'reached (%s)' % str(e).split('\n')[0][:200], 'error')
            return None
        except Exception as e:
            if db_trouble(e):
                # The database there but not answering - locked, full, a
                # statement or a lock that ran out (1.0.149): as when it is
                # gone, no answer. A refusal refused everybody with a right
                # code, and the VPN never asked the other node.
                self.counts['no_database'] += 1
                log_sparing('radius-db', 'RADIUS requests go unanswered: the database is not '
                            'answering (%s)' % str(e).split('\n')[0][:200], 'error')
                return None
            # Whatever went wrong inside, the VPN gets an answer - a refusal
            # with the reason written down - rather than silence and a retry.
            log_sparing('radius-decide:%s' % type(e).__name__,
                        'a request for %s could not be decided: %s' % (user, e), 'error')
            d = Decision()
            d.user = str(user or '')
            d.step('the decision', False, 'it could not be made: %s' % e)
            d.refuse('the token server could not decide: %s' % str(e)[:120])
        if src and not blocked and guard_is_guess(d):
            try:
                guard_count(self.d, src, d.user or user)
            except Exception as e:                      # noqa: BLE001
                log_sparing('radius-guard', 'the sign-in protection: %s' % e, 'warn')
        pairs = []
        for name, value in d.reply:
            try:
                pairs.append(attr_bytes(name, value))
            except RadiusError as e:
                d.step('the answer', False, str(e))
                # Never an Accept without what limits it (1.0.101): one
                # attribute that cannot be built refuses, not drops.
                if d.result == 'accept':
                    d.refuse('the answer cannot be built whole: %s' % e)
        if d.result == 'accept':
            self.counts['accept'] += 1
            code = ACCESS_ACCEPT
        elif d.result == 'challenge' and d.state:
            # The second window (1.0.76): the State the VPN sends back with
            # the code, and the words it shows. Nothing that lets in.
            self.counts['challenge'] += 1
            code = ACCESS_CHALLENGE
            pairs = [attr_bytes('State', '0x' + bytes(d.state).hex())]
            said = (d.message or '').encode('utf-8')[:253].decode('utf-8', 'ignore')
            if said:
                pairs.append(attr_bytes('Reply-Message', said))
        else:
            self.counts['reject'] += 1
            code = ACCESS_REJECT
            # The reason is cut by bytes, not characters, so a reason full of
            # accented letters still fits the attribute; and if the attribute
            # cannot be built for whatever reason the reject still goes out
            # without it rather than the request going unanswered and unlogged.
            pairs = []
            # The reason stays here unless asked for (1.0.33): sent back, a
            # VPN may show it to whoever is signing in - whether the name has
            # a token, whether the code was right and the password not.
            if CONFIG.get('radius_reject_reason'):
                try:
                    said = (d.reason or '').encode('utf-8')[:253].decode('utf-8', 'ignore')
                    if said:
                        pairs = [attr_bytes('Reply-Message', said)]
                except (RadiusError, ValueError) as e:
                    d.step('the answer', False, 'the reason could not be sent along: %s' % e)
                    pairs = []
        try:
            reply = build_reply(pkt, code, pairs, secret, bool(CONFIG.get('radius_reply_ma', 1)))
        except RadiusError as e:
            # Too long with what the realm and the groups add (1.0.44): a
            # refusal still goes out and is written down - never an Accept
            # without the attributes that limit what it lets in to.
            d.step('the answer', False, '%s - refused, since it cannot be sent whole' % e)
            if code == ACCESS_ACCEPT:
                self.counts['accept'] -= 1
                self.counts['reject'] += 1
                d.refuse('the answer would be longer than a RADIUS packet may be: too many '
                         'reply attributes in the realm and its groups')
                code = ACCESS_REJECT
            reply = build_reply(pkt, code, [], secret, bool(CONFIG.get('radius_reply_ma', 1)))
        took = int((time.time() - arrived) * 1000)
        # The answer goes out before anything is written down (1.0.33): a
        # database that is slow or locked delays the log, not the person -
        # and never leaves a request that was let in without its answer.
        reply = SentReply(reply)
        delay = int(CONFIG.get('radius_reject_delay_ms') or 0) if code == ACCESS_REJECT else 0
        # To the address the request came from, as it came (1.0.36): on a
        # socket listening on :: an IPv4 client is ::ffff:a.b.c.d there, and
        # the bare a.b.c.d could not be sent to - every answer was lost.
        sock = sock or self.socks.get('auth', (None, None, None))[2]
        peer = peer or (ip, port)
        if delay:
            # Waited out by one thread for all of them, not a thread each
            # (1.0.36), and not in a worker: a flood of wrong codes cannot
            # tie up the workers sleeping.
            reply.late = True
            reply.late_until = time.time() + min(delay, 10000) / 1000.0
            self.later(min(delay, 10000) / 1000.0, sock, bytes(reply), peer)
        else:
            try:
                if sock is not None:
                    sock.sendto(bytes(reply), peer)
            except OSError as e:
                log('the answer to %s could not be sent: %s' % (ip, e), 'warn')
            if remember is not None:
                remember(bytes(reply))
        reply.sent = True
        try:
            self.write_down(pkt, client, ip, port, rid, arrived, d, code, reply, took, words, w)
        except Exception as e:                          # noqa: BLE001
            log_sparing('radius-write', 'the request from %s for %s could not be written down: %s'
                        % (ip, d.user, str(e).split('\n')[0][:200]), 'error')
        return reply

    def later(self, wait, sock, data, peer):
        """An answer sent after `wait` seconds, by the one thread that sends
        the late ones. Past 10 000 waiting the newest are sent at once rather
        than kept."""
        with self.late_lock:
            if len(self.late) >= 10000:
                # Dropped, not sent at once (1.0.57): sent at once, a flood
                # of wrong guesses went round the delay. The NAS asks again.
                self.counts['late_dropped'] += 1
                return
            heapq.heappush(self.late, (time.time() + wait, id(data), sock, data, peer))
            if self.late_thread is None or not self.late_thread.is_alive():
                self.late_thread = threading.Thread(target=self.send_lates, name='radius-late',
                                                    daemon=True)
                self.late_thread.start()
        self.late_wake.set()

    def send_lates(self):
        while not self.stop_flag:
            # Cleared before the queue is looked at, not after the wait: one
            # put in between would otherwise sleep a whole second.
            self.late_wake.clear()
            with self.late_lock:
                due = []
                now = time.time()
                while self.late and self.late[0][0] <= now:
                    due.append(heapq.heappop(self.late))
                wait = (self.late[0][0] - now) if self.late else 1.0
            for _t, _i, sock, data, peer in due:
                self.send_late(sock, data, peer)
            self.late_wake.wait(max(0.005, min(wait, 1.0)))

    @staticmethod
    def send_late(sock, data, peer):
        try:
            if sock is not None:
                sock.sendto(data, peer)
        except OSError:
            pass

    def write_down(self, pkt, client, ip, port, rid, arrived, d, code, reply, took, words, w):
        if d.result == 'accept' and d.token_name:
            self.d.tokens.mark_from(d.token_name, w.get('Calling-Station-Id') or ip,
                                    (client or {}).get('name') or '')
        av = {}
        for name, value in words:
            if name == 'Cisco-AVPair' and '=' in value:
                k, _, v = value.partition('=')
                if k == 'mdm-tlv':
                    k, _, v = v.partition('=')
                av[k] = v
        tunnel = ''
        for name, value in words:
            if name == 'Vendor-3076-Attr-146' and value.startswith('0x'):
                try:
                    tunnel = bytes.fromhex(value[2:]).decode('ascii', 'ignore').strip('\x00')
                except ValueError:
                    pass
        reply_words = [(n, v) for n, v in Packet.parse(bytes(reply)).words()
                       if n != 'Message-Authenticator']
        self.d.store.radius_add({
            'ts': arrived, 'client': client['name'], 'nas_ip': w.get('NAS-IP-Address') or ip,
            'src': rid, 'packet': 'Access-Request',
            'username': d.user[:190] or (pkt.text(1) or '')[:190],
            'realm': d.realm, 'calling': (w.get('Calling-Station-Id') or '')[:190],
            'called': (w.get('Called-Station-Id') or '')[:190], 'result': d.result,
            'reason': d.reason[:1000], 'otp': d.otp[:190], 'rid': rid, 'took_ms': took,
            'attrs': json.dumps(words), 'reply': json.dumps(reply_words),
            'steps': json.dumps(d.steps), 'device': (av.get('computer-name') or '')[:190],
            'tunnel': tunnel[:190]})
        self.ship(pkt, words, reply_words, code, ip, port, rid, arrived)

    def accounting(self, pkt, client, ip, port, secret, arrived):
        if pkt.code == STATUS_SERVER:
            # Asked on the accounting port, answered with an
            # Accounting-Response (RFC 5997 4; 1.0.44).
            if not CONFIG.get('radius_status_server', 1):
                return None
            if not self.ma_check(pkt, client, secret, ip, port):
                return None
            self.counts['status'] += 1
            return build_reply(pkt, ACCOUNTING_RESPONSE, [], secret, True)
        # Sparingly, as on the other port (1.0.59): neither is proven to come
        # from the client, and each one was a row in the database.
        if pkt.code != ACCOUNTING_REQUEST:
            self.drop(ip, port, pkt.text(1), 'only Accounting-Request is answered on this port',
                      pkt=pkt, client=client, sparing=True)
            return None
        if not pkt.accounting_ok(secret):
            self.drop(ip, port, pkt.text(1), 'the authenticator of the accounting request is '
                      'wrong: the shared secret is not the same as on the client', pkt=pkt,
                      client=client, sparing=True)
            return None
        # A Message-Authenticator, where there is one, has to be right too
        # (1.0.59) - over the packet with the authenticator as noughts.
        if pkt.message_authenticator_ok(secret, zero_authenticator=True) is False and \
                pkt.message_authenticator_ok(secret) is not True:
            self.drop(ip, port, pkt.text(1), 'the Message-Authenticator of the accounting '
                      'request is wrong', pkt=pkt, client=client, sparing=True)
            return None
        self.counts['accounting'] += 1
        words = pkt.words()
        w = dict(words)
        self.d.store.radius_add({
            'ts': arrived, 'client': client['name'], 'nas_ip': w.get('NAS-IP-Address') or ip,
            'src': '%s:%d' % (ip, port), 'packet': 'Accounting-Request',
            'username': (w.get('User-Name') or '')[:190], 'realm': '',
            'calling': (w.get('Calling-Station-Id') or '')[:190],
            'called': (w.get('Called-Station-Id') or '')[:190], 'result': 'acct',
            'reason': (w.get('Acct-Status-Type') or '')[:100], 'otp': '', 'rid': '',
            'took_ms': int((time.time() - arrived) * 1000), 'attrs': json.dumps(words),
            'reply': '[]', 'steps': '[]', 'device': '', 'tunnel': ''})
        if self.d.shipper:
            self.d.shipper.detail_line(ip, 'detail', arrived, self.header(
                'Accounting-Request', ip, port, port_here=self.port_of('acct')) + words)
        return build_reply(pkt, ACCOUNTING_RESPONSE, [], secret, with_ma=False)

    def port_of(self, kind):
        got = self.socks.get(kind)
        return got[1] if got else 0

    @staticmethod
    def header(packet, ip, port, port_here, reply=False):
        """What FreeRADIUS writes first in a detail record under
        `log_packet_header = yes`."""
        if reply:
            return [('Packet-Type', packet), ('Packet-Dst-IP-Address', ip),
                    ('Packet-Dst-IP-Port', str(port))]
        return [('Packet-Type', packet), ('Packet-Src-IP-Address', ip),
                ('Packet-Src-IP-Port', str(port)), ('Packet-Dst-IP-Port', str(port_here))]

    def ship(self, pkt, words, reply_words, code, ip, port, rid, arrived):
        sh = self.d.shipper
        if not sh:
            return
        here = self.port_of('auth')
        ask = self.header('Access-Request', ip, port, here) + words + [('Totp-Request-Id', rid)]
        sh.detail_line(ip, 'auth-detail', arrived, ask)
        answer = self.header(CODE_WORDS[code], ip, port, here, reply=True) + reply_words + [
            ('Totp-Request-Id', rid)]
        sh.detail_line(ip, 'reply-detail', time.time(), answer)

    def state(self):
        return {'listening': self.bound, 'trouble': self.trouble, 'counts': dict(self.counts),
                'queued': self.jobs.qsize()}
