# 1.0.286 pages: a browser that cannot be checked (the kit's 3rd edition) - python3 web.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/admin/index.php', [(
"""        $d = null;
        if (otp_session() !== '') {
            [$status, $body] = otp_call('/api/auth/card', 'POST', ['cert' => $pem], 10.0);
            $d = $status === 200 ? json_decode((string) $body, true) : null;
        }
        if (is_array($d) && empty($d['gone'])) {
            header('Content-Type: image/gif');
            echo base64_decode(!empty($d['alive'])
                ? 'R0lGODlhAQABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAABAAEAAAgEAAEEBAA7'
                : 'R0lGODlhAgABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAACAAEAAAgFAAEACAgAOw==');
            exit;
        }""",
"""        /* 1.0.286: 3 wide - no cookie came with the check (the page then says so on 443, where its cookie
           does come); 4 wide - this browser cannot be checked (its checks never once found the card): it is
           not watched. */
        $gifs = [1 => 'R0lGODlhAQABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAABAAEAAAgEAAEEBAA7',
                 2 => 'R0lGODlhAgABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAACAAEAAAgFAAEACAgAOw==',
                 3 => 'R0lGODlhAwABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAADAAEAAAgFAAEIDAgAOw==',
                 4 => 'R0lGODlhBAABAIEAAAAAAP///wAAAAAAACH5BAEAAAAALAAAAAAEAAEAAAgGAAEIBBAQADs='];
        $wide = 0;
        if (otp_session() !== '') {
            [$status, $body] = otp_call('/api/auth/card', 'POST', ['cert' => $pem], 10.0);
            $d = $status === 200 ? json_decode((string) $body, true) : null;
            if (is_array($d) && empty($d['gone'])) {
                $wide = !empty($d['unable']) ? 4 : (!empty($d['alive']) ? 1 : 2);
            }
        } else {
            $wide = 3;
        }
        if ($wide > 0) {
            header('Content-Type: image/gif');
            echo base64_decode($gifs[$wide]);
            exit;
        }""")])

edit('web/assets/admin.js', [(
"""    if (w === 1) { CW.misses = 0; certWatchIn(); return; }
    if (w === 2) { CW.misses = 0; certWatchOut(took); return; }""",
"""    if (w === 1) { CW.misses = 0; certWatchIn(); return; }
    if (w === 2) { CW.misses = 0; certWatchOut(took); return; }
    /* This browser cannot be checked (1.0.286): its checks never once found the card - an iPad's Safari
       signs nothing for a page in the background. */
    if (w === 4) { certWatchUnable(); return; }"""), (
"""    CW.misses += 1;
    if (CW.misses < 2 && !CW.out) { certWatchNext(1500); return; }
    api('card-gone', {}).then(function (d) {
      if (g !== CW.gen) return;""",
"""    CW.misses += 1;
    if (w !== 3 && CW.misses < 2 && !CW.out) { certWatchNext(1500); return; }
    /* w 3: the picture came, but no cookie came with it - said as such (here, on 443, the cookie comes). */
    api('card-gone', {why: w === 3 ? 'nocookie' : 'nopicture'}).then(function (d) {
      if (g !== CW.gen) return;
      if (d && d.unable) { certWatchUnable(); return; }"""), (
"""  img.onload = function () { fin(img.naturalWidth === 2 ? 2 : 1); };""",
"""  img.onload = function () { var nw = img.naturalWidth; fin(nw >= 2 && nw <= 4 ? nw : 1); };"""), (
"""function certWatchIn() {""",
"""/* Not watched from now on (1.0.286): the checks stop, the notice goes, and the person is told why. */
function certWatchUnable() {
  CW.gen++; CW.conf = null; CW.out = 0;
  if (CW.timer) clearTimeout(CW.timer);
  certWatchLayer(false);
  toast('This browser cannot have the card checked (as an iPad cannot): this sign-in is not watched.', 'warn');
}
function certWatchIn() {"""), (
"""     : 'nothing - the session goes on', 'admin_cert_card: ' + (d.watch || 'off')],""",
"""     : 'nothing - the session goes on', 'admin_cert_card: ' + (d.watch || 'off') +
     (d.watch && d.watch !== 'off' ? ' · admin_cert_card_unable: ' + (d.watch_unable || 'allow') : '')],""")])
print('1.0.286 web patched')
