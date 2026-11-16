# 1.0.288 pages: the card watched - the kit's 4th edition (isemon 1.10.356-1.10.358) - python3 web.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/assets/admin.js', [
    # 4: out already - counted from when the server saw it; F5 started the countdown afresh, every time.
    (
"""  if (conf.out) { CW.out = Date.now(); certWatchLayer(true); }""",
"""  if (conf.out) { CW.out = Date.now() - Math.max(0, Number(conf.out_for) || 0) * 1000; certWatchLayer(true); }"""),
    # 5/d: the server ended the sign-in just now - 5 wide: its card out, 6: another card. Said, nothing tried.
    (
"""    if (w === 4) { certWatchUnable(); return; }""",
"""    if (w === 4) { certWatchUnable(); return; }
    /* The server ended the sign-in just now (1.0.288): said why, and nothing tried by itself. */
    if (w === 5 || w === 6) { certWatchEnd(w === 6 ? 'other' : (CW.out ? 'late' : 'out')); return; }"""),
    (
"""    /* This browser cannot be checked (1.0.286): its checks never once found the card - an iPad's Safari
       signs nothing for a page in the background. */""",
"""    /* This browser cannot be checked (1.0.286): its checks never once found the card. */"""),
    # 2: a check waiting over 4 s on a window of the card's (Windows' "insert the smart card", the browser's
    # chooser): the card is out - the countdown at once, behind that window; the server told. Put back and
    # answered there, the check comes back 1 wide and the notice goes.
    (
"""  to = setTimeout(function () { fin(0); }, 20000);
  img.onload = function () { var nw = img.naturalWidth; fin(nw >= 2 && nw <= 4 ? nw : 1); };""",
"""  to = setTimeout(function () { fin(0); }, 20000);
  setTimeout(function () {
    if (done || g !== CW.gen || CW.out) return;
    if (c.mode === 'grace') { CW.out = began; certWatchLayer(true); }
    api('card-gone', {why: 'waiting'}).then(function (d) {
      if (g === CW.gen && d && d.gone) certWatchEnd('out');
    }, function () { });
  }, 4000);
  img.onload = function () { var nw = img.naturalWidth; fin(nw >= 2 && nw <= 6 ? nw : 1); };"""),
    (
"""  toast('This browser cannot have the card checked (as an iPad cannot): this sign-in is not watched.', 'warn');""",
"""  toast('This browser cannot have the card checked: this sign-in is not watched.', 'warn');"""),
    # 3: Cancel in that window - Chrome and Edge offer no card to this server again until restarted.
    (
"""    box.appendChild(el('p', 'cw-p', 'The smart card or YubiKey was taken out, so this sign-in is locked. Put it back - the page goes on where you left off.'));
""",
"""    box.appendChild(el('p', 'cw-p', 'The smart card or YubiKey was taken out, so this sign-in is locked. Put it back - the page goes on where you left off.'));
    box.appendChild(el('p', 'cw-hint', 'A window asking for the smart card: put the card back and press OK there - not Cancel. After Cancel the browser offers no card here until it is closed and opened again.'));
"""),
])
edit('web/assets/otp.css', [(
""".cw-until{color:var(--warn);font-weight:600;font-size:13.5px;margin:0 0 18px}""",
""".cw-until{color:var(--warn);font-weight:600;font-size:13.5px;margin:0 0 18px}
.cw-hint{margin:0 0 14px;padding:9px 12px;border:1px solid var(--line);border-radius:8px;color:var(--tx-dim);font-size:12.5px;line-height:1.5;text-align:left}""")])
edit('web/admin/index.php', [
    # 5/d: 5 wide - ended just now for its card; 6 - for another card.
    (
"""                 4 => 'R0lGODlhBAABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAAEAAEAAAgGAAEIBBAQADs='];""",
"""                 4 => 'R0lGODlhBAABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAAEAAEAAAgGAAEIBBAQADs=',
                 /* 1.0.288: 5 wide - the sign-in ended just now for its card, 6 - for another card: the page
                    says why and tries nothing by itself (a 403 left it without a word). */
                 5 => 'R0lGODlhBQABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAAFAAEAAAgGAAEIFBgQADs=',
                 6 => 'R0lGODlhBgABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAAGAAEAAAgGAAEIHBgQADs='];"""),
    (
"""            if (is_array($d) && empty($d['gone'])) {
                $wide = !empty($d['unable']) ? 4 : (!empty($d['alive']) ? 1 : 2);
            }""",
"""            if (is_array($d) && empty($d['gone'])) {
                $wide = !empty($d['unable']) ? 4 : (!empty($d['alive']) ? 1 : 2);
            } elseif (is_array($d) && !empty($d['watched'])) {
                $wide = ($d['why'] ?? '') === 'other' ? 6 : 5;
            }"""),
    # 5/e: a name CSP's grammar does not take (an underscore) or an IPv6 address: pictures over https then -
    # the card left unchecked held the sign-in (423) once its page stopped checking.
    (
"""    if ($cwp >= 1025 && $cwp <= 65535 && preg_match('/^([A-Za-z0-9.-]{1,253}|\\[[0-9A-Fa-f:.]{2,45}\\])\\z/', $cwh)) {
        otp_csp($nonce, 'https://' . $cwh . ':' . $cwp);
    } else {""",
"""    if ($cwp >= 1025 && $cwp <= 65535) {
        otp_csp($nonce, preg_match('/^[A-Za-z0-9.-]{1,253}\\z/', $cwh) ? 'https://' . $cwh . ':' . $cwp : 'https:');
    } else {"""),
])
print('1.0.288 web patched')
