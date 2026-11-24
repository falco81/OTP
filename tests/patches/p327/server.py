"""1.0.327 (parts): in a replicated pair each node tidies only its own counts; a restore on the
node that is not the lead has its names put right by the lead; {account} in a link's address."""
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


edit('65_codes.py', [
("""        if r['k'].startswith('chal:'):
            gone = not isinstance(v, dict) or fnum(v.get('exp')) < t - 60
        else:
""",
 """        if r['k'].startswith('chal:'):
            gone = not isinstance(v, dict) or fnum(v.get('exp')) < t - 60
        elif not _tidy_mine(store, r['k']):
            continue
        else:
"""),
("""def chal_tidy(store):
""",
 """def _tidy_mine(store, k):
    \"\"\"Whether this node tidies count `k` (1.0.327): in a replicated pair only its own
    ('...@@<this node>') - the other node's row deleted here while it added to it there, its
    newest count was lost: one code or one directory password more. One written before 1.0.146
    (no node in it): the lead's. Every other way (one node, one database for both): all.\"\"\"
    if CONFIG.get('ha_mode') != 'replicated':
        return True
    if NODE_KEY_SEP not in k:
        return ha_lead(store)
    return k.rsplit(NODE_KEY_SEP, 1)[1] == node_name()


def chal_tidy(store):
"""),
])

edit('80_daemon.py', [
("""    if not ha_lead(store):
        return
    if not sealing_key():
        # Not without the key that opens the tokens (1.0.225): their keys would stay sealed
""",
 """    if not ha_lead(store):
        # A copy put back here, the node that is not the lead (1.0.327): its names stayed as
        # they were until the lead started again - nobody found those tokens meanwhile. The
        # lead is asked: a key of this node's own, the lead does it on its next look.
        if any(not str(n.get('name') or '').isascii() and norm_name(n['name']) != n['name']
               for n in store.db.rows('SELECT name FROM tokens')):
            store.set_meta('names:nfc:ask' + NODE_KEY_SEP + node_name(), str(time.time()))
        return
    if not sealing_key():
        # Not without the key that opens the tokens (1.0.225): their keys would stay sealed
"""),
("""                try:
                    lockouts_tick(self)         # who is locked out, for the pages (1.0.112)
""",
 """                try:
                    names_nfc_asked(self.store)  # the other node put a copy back (1.0.327)
                except Exception as e:          # noqa: BLE001
                    log_sparing('names-nfc-asked', 'the names of tokens: %s' % e, 'warn', every=600)
                try:
                    lockouts_tick(self)         # who is locked out, for the pages (1.0.112)
"""),
("""def names_nfc_kept(store):
""",
 """def names_nfc_asked(store):
    \"\"\"The lead: names put in one form when the other node asked (1.0.327) - it put an old
    copy back. Each ask taken away only as it was read: one made again meanwhile stays.\"\"\"
    if CONFIG.get('ha_mode') != 'replicated' or not ha_lead(store):
        return
    asks = store.db.rows("SELECT k, v FROM meta WHERE k LIKE 'names:nfc:ask%'")
    if not asks:
        return
    names_nfc_kept(store)
    for r in asks:
        store.db.run('DELETE FROM meta WHERE k = ? AND v = ?', (r['k'], r['v']))


def names_nfc_kept(store):
"""),
])

# {account} (and every {word}) inside a link's address: the value itself, as an address takes it.
edit('86t_texts.py', [
("""def text_rich_clean(value):
""",
 """def fill_html(t, fmt, plain):
    \"\"\"A text of a mail filled in (1.0.327): {account} inside a link's address took the HTML
    that keeps a name from turning into a link - its quote closed the address, and every
    mail's link was broken. Inside href="..." each {word} is the plain value, as an address
    takes it; everywhere else as before.\"\"\"
    import urllib.parse as _up

    def one(n):
        k = n.group(1)
        if k not in plain:
            return n.group(0)
        return html.escape(_up.quote(str(plain[k] if plain[k] is not None else ''), safe="@:/+-._~=&?#,;!$'()*"),
                           quote=True)
    t = re.sub(r'(<a href=")([^"]*)(")', lambda m: m.group(1) + re.sub(
        r'(?<!\\{)\\{(\\w+)\\}(?!\\})', one, m.group(2)) + m.group(3), str(t))
    return t.format(**fmt)


def text_rich_clean(value):
"""),
])
edit('86_mail.py', [
("w['lede'].format(**fmt)", "fill_html(w['lede'], fmt, plain_fmt_h)"),
("w['step1'].format(**fmt)", "fill_html(w['step1'], fmt, plain_fmt_h)"),
("w['step2'].format(**fmt)", "fill_html(w['step2'], fmt, plain_fmt_h)"),
("w['step3'].format(**fmt)", "fill_html(w['step3'], fmt, plain_fmt_h)"),
("w['facts'].format(**fmt)", "fill_html(w['facts'], fmt, plain_fmt_h)"),
("w['pending'].format(**fmt)", "fill_html(w['pending'], fmt, plain_fmt_h)"),
("w['codes_p'].format(**fmt)", "fill_html(w['codes_p'], fmt, plain_fmt_h)"),
("w['warn'].format(**fmt)", "fill_html(w['warn'], fmt, plain_fmt_h)"),
("w['foot'].format(**fmt)", "fill_html(w['foot'], fmt, plain_fmt_h)"),
])
edit('65_codes.py', [
("""    lede = (w['h_%slede' % v].format(account=acc) if name
""",
 """    lede = (fill_html(w['h_%slede' % v], {'account': acc}, {'account': name}) if name
"""),
])
