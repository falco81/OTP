# 1.0.285 pages: the card of a sign-in with a certificate watched - the kit "card-removal-watch" merged
# (its pages, its notice, its picture of the certificate's port) - python3 web.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


# ---- nginx: only while the card is watched - cert-alive let through, no TLS session, no connection kept ----
edit('deploy/otp_web.py', [(
"""              '        if ($arg_api !~ "^cert-(login|check)$") { return 404; }',""",
"""              '        if ($arg_api !~ "^cert-(login|check%s)$") { return 404; }' % ('|alive' if card else ''),"""), (
"""    out = ['server {'] + listens + ['    server_name %s;' % names] + keep
    # A certificate nginx itself refuses""",
"""    out = ['server {'] + listens + ['    server_name %s;' % names]
    if card:
        # The card watched (1.0.285, admin_cert_card): every check a handshake of its own, which only the
        # card can sign - no TLS session taken up again, no connection kept open. Off: as before.
        out += [k for k in keep if not k.strip().startswith('ssl_session_')]
        out += ['    ssl_session_cache off;', '    ssl_session_tickets off;', '    keepalive_timeout 0;']
    else:
        out += keep
    # A certificate nginx itself refuses"""), (
"""def certlogin_server(block, port, ca_path):""",
"""def certlogin_server(block, port, ca_path, card=False):"""), (
"""    return {'port': port, 'ca': ''.join(b.strip() + '\\n' for b in blocks)}""",
"""    # The card watched (1.0.285): the port keeps no TLS session then.
    return {'port': port, 'ca': ''.join(b.strip() + '\\n' for b in blocks), 'card': bool(cl.get('card'))}"""), (
"""            text = CERT_HEAD + certlogin_server(block, int(cl['port']), CERT_CA_PATH)
            if vip_block:
                text += certlogin_server(vip_block, int(cl['port']), CERT_CA_PATH)""",
"""            text = CERT_HEAD + certlogin_server(block, int(cl['port']), CERT_CA_PATH, cl.get('card'))
            if vip_block:
                text += certlogin_server(vip_block, int(cl['port']), CERT_CA_PATH, cl.get('card'))""")])

# ---- the page's policy: one function, the check's picture let in by one address when it is watched ----
edit('web/otp-page.php', [(
"""$nonce = base64_encode(random_bytes(16));
header("Content-Security-Policy: default-src 'self'; "
     . "script-src 'self' 'nonce-$nonce'; "
     . "style-src 'self' 'unsafe-inline'; style-src-elem 'self' 'nonce-$nonce'; "
     . "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; "
     . "base-uri 'none'; form-action 'self'; frame-ancestors 'none'");""",
"""$nonce = base64_encode(random_bytes(16));
/* The page's policy (1.0.285: one function - the administration sends it again, before any output, with
   the address of the certificate's port for pictures when the card of the sign-in is watched). */
function otp_csp(string $nonce, string $img_also = ''): void
{
    header("Content-Security-Policy: default-src 'self'; "
         . "script-src 'self' 'nonce-$nonce'; "
         . "style-src 'self' 'unsafe-inline'; style-src-elem 'self' 'nonce-$nonce'; "
         . "img-src 'self' data:" . ($img_also !== '' ? ' ' . $img_also : '') . "; connect-src 'self'; font-src 'self'; object-src 'none'; "
         . "base-uri 'none'; form-action 'self'; frame-ancestors 'none'", true);
}
otp_csp($nonce);""")])

# ---- PHP: ?api=cert-alive on the certificate's port (a picture), ?api=card-gone on 443, the policy ----
edit('web/admin/index.php', [(
"""    $what = (string) ($_GET['api'] ?? '');
    if ($_SERVER['REQUEST_METHOD'] !== 'GET' || !in_array($what, ['cert-login', 'cert-check'], true)) {
        http_response_code(404);
        exit;
    }
    $pem = rawurldecode((string) ($_SERVER['SSL_CLIENT_CERT'] ?? ''));""",
"""    $what = (string) ($_GET['api'] ?? '');
    if ($_SERVER['REQUEST_METHOD'] !== 'GET' || !in_array($what, ['cert-login', 'cert-check', 'cert-alive'], true)) {
        http_response_code(404);
        exit;
    }
    if ($what === 'cert-alive') {
        /* The card watched (1.0.285): the signed-in page loads a picture from here every few seconds - a
           new connection, whose handshake only the card can sign. Whatever certificate came (none: the
           card is out) goes to the daemon with the session's cookie; the answer is a picture 1 pixel wide
           (the card is there), 2 wide (it is out, the session waits) or none - 403 (the session is over).
           No session, no question asked. A picture: no CORS, nothing for another site to read. */
        header('Cache-Control: no-store');
        $pem = ($_SERVER['OTP_CERT_FAIL'] ?? '') === '1' ? '' : rawurldecode((string) ($_SERVER['SSL_CLIENT_CERT'] ?? ''));
        if (strlen($pem) > 20000) {
            $pem = '';
        }
        $d = null;
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
        }
        http_response_code(403);
        exit;
    }
    $pem = rawurldecode((string) ($_SERVER['SSL_CLIENT_CERT'] ?? ''));"""), (
"""        'kerberos' => '/api/kerberos',
        'certlogin' => '/api/certlogin',
    ];
    if ($post) {""",
"""        'kerberos' => '/api/kerberos',
        'certlogin' => '/api/certlogin',
        'card-gone' => '/api/auth/cardgone',
    ];
    if ($post) {"""), (
"""$mfa     = (is_array($me) && !empty($me['mfa'])) ? (string) $me['mfa'] : '';
if ($mfa !== '') { $me = null; }""",
"""$mfa     = (is_array($me) && !empty($me['mfa'])) ? (string) $me['mfa'] : '';
if ($mfa !== '') { $me = null; }
/* The card watched (1.0.285): its check is a picture from the certificate's port, which this page's
   policy lets in by that one address - only for a sign-in that is watched, sent again before anything of
   the page is. The name is the one this page was reached by (as the picture's). */
if (is_array($me) && is_array($me['card'] ?? null)) {
    $cwp = (int) ($me['card']['port'] ?? 0);
    $cwh = preg_replace('/:\\d+$/', '', (string) ($_SERVER['HTTP_HOST'] ?? ''));
    if ($cwp >= 1025 && $cwp <= 65535 && preg_match('/^([A-Za-z0-9.-]{1,253}|\\[[0-9A-Fa-f:.]{2,45}\\])\\z/', $cwh)) {
        otp_csp($nonce, 'https://' . $cwh . ':' . $cwp);
    } else {
        $me['card'] = null;
    }
}"""), (
"""  if ($('mfa-box').dataset.stage) mfaStep();
  else if (krbAuto) krbTry(true);""",
"""  /* Signed out because of the card (1.0.285): said once, by a word of this tab's own - never a text of
     the address - and nothing tried by itself (otp.krb.out), so the browser's certificate chooser does
     not open again on its own. */
  try {
    var cw = sessionStorage.getItem('otp.card.out');
    if (cw) {
      sessionStorage.removeItem('otp.card.out');
      var cws = $('krb-said') || $('in-said');
      if (cws) {
        cws.className = 'said bad';
        cws.textContent = cw === 'late' ? 'Signed out: the card you signed in with was not put back in time.'
          : cw === 'other' ? 'Signed out: another card than the one you signed in with was offered.'
          : 'Signed out: the card you signed in with was taken out.';
      }
    }
  } catch (e) { }
  if ($('mfa-box').dataset.stage) mfaStep();
  else if (krbAuto) krbTry(true);""")])

# ---- a question refused because the card is out (423): the page checks at once ----
edit('web/assets/core.js', [(
"""      if (!r.ok || data.ok === false) {
        var err = new Error(data.error || ('HTTP ' + r.status));
        err.status = r.status;""",
"""      if (r.status === 423 && data && data.code === 'card') {
        /* The card of a sign-in with a certificate is out (1.0.285): the page checks it at once. */
        if (typeof certWatchNow === 'function') certWatchNow();
        var locked = new Error(data.error || 'the card is out');
        locked.status = 423;
        locked.unreachable = true;
        locked.data = data;
        throw locked;
      }
      if (!r.ok || data.ok === false) {
        var err = new Error(data.error || ('HTTP ' + r.status));
        err.status = r.status;""")])

edit('web/assets/admin.js', [(
"""  api('whoami').then(function (d) { limit = (d.idle_min || 120) * 60000; }).catch(function () {});""",
"""  api('whoami').then(function (d) { limit = (d.idle_min || 120) * 60000; }).catch(function () {});
  /* The card watched (1.0.285): switched on while these pages were open - learnt within a minute. */
  var cwAsked = Date.now();
  setInterval(function () {
    if (CW.conf || Date.now() - cwAsked < 55000) return;
    cwAsked = Date.now();
    api('whoami').then(function (d) { certWatchLater(d && d.who && d.who.card); }).catch(function () {});
  }, 30000);"""), (
"""  ['By itself on the sign-in page', d.auto ? 'yes - at once, the form if it did not work' : 'no - a button under the form', ''],
   ['A password on the sign-in page',""",
"""  ['When the card is taken out', d.watch === 'signout' ? 'signed out at the next check (every ' + d.watch_s + ' s)'
     : d.watch === 'grace' ? 'a notice, then signed out unless it is back within ' + d.watch_grace_s + ' s (checked every ' + d.watch_s + ' s)'
     : 'nothing - the session goes on', 'admin_cert_card: ' + (d.watch || 'off')],
   ['By itself on the sign-in page', d.auto ? 'yes - at once, the form if it did not work' : 'no - a button under the form', ''],
   ['A password on the sign-in page',"""), (
"""/* ---- upgrades and maintenance (1.0.37) ------------------------------------ */""",
"""/* ---- The card watched (1.0.285) ------------------------------------------------
   A sign-in made with a card, while Settings - Accounts - Signing in with a certificate - "When the card is
   taken out" asks for it. Every few seconds a picture from the certificate's port - a new connection, so
   the card has to sign it: 1 pixel wide, the card is there; 2, it is out and the session waits (grace);
   none, it is out or the session is over. Out: signed out at once (signout), or a notice counting down
   until it is back (grace). The server ends the session as well - this only makes it be seen at once.
   Kind to the card: one check at a time, one for all the tabs of this browser (the others take its
   answer), a check that waited for a window of the card's (its PIN, "insert the card") followed by a
   longer pause - no window comes back again and again. */
var CW = {conf: null, timer: null, out: 0, gen: 0, layer: null, busy: false, misses: 0, tick: null, n: null, ok: 0};
var CW_SHARED = 'otp.card.check';
function certWatchStart(conf) {
  if (!conf || !conf.port || (conf.mode !== 'signout' && conf.mode !== 'grace')) return;
  if (CW.conf) { CW.conf = conf; return; }
  CW.conf = conf; CW.gen++;
  if (conf.out) { CW.out = Date.now(); certWatchLayer(true); }
  /* The first check soon: a card taken out while the page loaded is seen at once. */
  certWatchNext(conf.out ? 300 : 1500);
}
/* Learnt later (switched on while the page was open): this page's policy does not let the check's
   picture in yet - the page is loaded again (or asked to be, with changes not saved). */
function certWatchLater(conf) {
  if (!conf || CW.conf || !conf.port || (conf.mode !== 'signout' && conf.mode !== 'grace')) return;
  if (ME && ME.card) { certWatchStart(conf); return; }
  var unsaved = (typeof DIRTY === 'object' && DIRTY && Object.keys(DIRTY).length) ||
                (typeof PENDING === 'object' && PENDING && Object.keys(PENDING).length);
  if (!unsaved) location.reload();
  else if (!CW.said) { CW.said = true; toast('The card you signed in with is watched from now on - save and reload the page.', 'warn'); }
}
function certWatchNow() { if (CW.conf && !CW.busy) certWatchNext(0); }
function certWatchNext(ms) {
  var g = CW.gen;
  if (CW.timer) clearTimeout(CW.timer);
  CW.timer = setTimeout(function () { if (g === CW.gen) certWatchCheck(); }, ms);
}
function certWatchShared() {
  try { var v = JSON.parse(localStorage.getItem(CW_SHARED) || 'null'); return v && typeof v.t === 'number' ? v : null; } catch (e) { return null; }
}
function certWatchCheck() {
  var c = CW.conf, g = CW.gen;
  if (!c || CW.busy) return;
  /* Another tab of this browser checked a moment ago and the card was there: its answer is this one's. */
  var sh = certWatchShared();
  if (sh && sh.w === 1 && !CW.out && Date.now() - sh.t < c.every * 600) {
    certWatchNext(c.every * 1000 - (Date.now() - sh.t) + 200 + Math.random() * 800);
    return;
  }
  var done = false, img = new Image(), to = null, began = Date.now();
  CW.busy = true;
  var fin = function (w) {
    if (done) return;
    done = true;
    clearTimeout(to);
    CW.busy = false;
    img.onload = img.onerror = null;
    if (g !== CW.gen) return;
    try { localStorage.setItem(CW_SHARED, JSON.stringify({t: Date.now(), w: w})); } catch (e) { }
    var took = Date.now() - began;
    if (w === 1) { CW.misses = 0; certWatchIn(); return; }
    if (w === 2) { CW.misses = 0; certWatchOut(took); return; }
    /* No picture at all: the handshake failed (nothing to sign it with), or the session is over (403).
       Once more after a moment - one lost connection is not a card taken out; then the pages are told
       (the server holds or ends the sign-in, and says so in the events). */
    CW.misses += 1;
    if (CW.misses < 2 && !CW.out) { certWatchNext(1500); return; }
    api('card-gone', {}).then(function (d) {
      if (g !== CW.gen) return;
      if (!d || !d.watched) { certWatchNext(c.every * 1000); return; }
      if (d.gone) { certWatchEnd(CW.out ? 'late' : 'out'); return; }
      certWatchOut(took);
    }, function (e) {
      if (g !== CW.gen) return;
      /* The pages do not answer either: the network, not the card - asked again later. A sign-in the
         pages no longer know is shown as signed out by whatever asks next. */
      certWatchNext(Math.max(5000, c.every * 1000));
    });
  };
  /* A check left without an answer for 20 s: counted as none (fail closed); the browser may still be
     waiting on a window of the card's - no new check starts until this one is over. */
  to = setTimeout(function () { fin(0); }, 20000);
  img.onload = function () { fin(img.naturalWidth === 2 ? 2 : 1); };
  img.onerror = function () { fin(0); };
  img.src = 'https://' + location.hostname + ':' + c.port + '/admin/?api=cert-alive&r=' + Date.now().toString(36);
}
function certWatchIn() {
  var c = CW.conf;
  if (CW.out) {
    CW.out = 0;
    certWatchLayer(false);
    toast('The card is back.', 'good');
  }
  certWatchNext(c.every * 1000);
}
function certWatchOut(took) {
  var c = CW.conf;
  if (c.mode === 'signout') { certWatchEnd('out'); return; }
  if (!CW.out) CW.out = Date.now();
  var left = c.grace - Math.floor((Date.now() - CW.out) / 1000);
  if (left <= 0) { certWatchEnd('late'); return; }
  certWatchLayer(true);
  /* Asked again every 5 s; after a check that waited on a window of the card's, 10 s. */
  certWatchNext(took > 4000 ? 10000 : 5000);
}
function certWatchLayer(on) {
  if (!on) {
    if (CW.tick) { clearInterval(CW.tick); CW.tick = null; }
    if (CW.layer) {
      CW.layer.remove(); CW.layer = null;
      (CW.held || []).forEach(function (e) { e.inert = false; });
      CW.held = [];
    }
    return;
  }
  if (!CW.layer) {
    /* The notice (1.0.285, design B): the seconds left in a ring that empties as they go. */
    var l = el('div', 'cw-layer');
    l.id = 'cw-layer';
    l.setAttribute('role', 'alertdialog');
    l.setAttribute('aria-modal', 'true');
    var box = el('div', 'cw-box');
    var ring = el('div', 'cw-ring');
    var R = 60, C = 2 * Math.PI * R;
    ring.innerHTML = '<svg viewBox="0 0 132 132" aria-hidden="true"><circle class="cw-track" cx="66" cy="66" r="60"/>' +
      '<circle class="cw-arc" cx="66" cy="66" r="60" stroke-dasharray="' + C.toFixed(2) + '" stroke-dashoffset="0"/></svg>';
    var mid = el('div', 'cw-mid');
    var n = noI18n(el('div', 'cw-n', ''));
    n.id = 'cw-n';
    mid.appendChild(n);
    mid.appendChild(el('div', 'cw-unit', 'seconds'));
    ring.appendChild(mid);
    box.appendChild(ring);
    box.appendChild(el('h3', '', 'Put the card back'));
    box.appendChild(el('p', 'cw-p', 'The smart card or YubiKey was taken out, so this sign-in is locked. Put it back - the page goes on where you left off.'));
    var until = el('div', 'cw-until', '');
    until.id = 'cw-until';
    box.appendChild(until);
    var out = cmdButton('Sign out', 'out', 'danger');
    out.id = 'cw-out';
    out.onclick = function () { certWatchEnd('', true); };
    box.appendChild(out);
    l.appendChild(box);
    /* Nothing behind it reachable - by the mouse or the keyboard. */
    CW.held = [];
    Array.prototype.forEach.call(document.body.children, function (e) {
      if (!e.inert) { e.inert = true; CW.held.push(e); }
    });
    document.body.appendChild(l);
    CW.layer = l; CW.n = n; CW.arc = ring.querySelector('.cw-arc'); CW.arcC = C; CW.until = until;
    setTimeout(function () { try { out.focus(); } catch (e) { } }, 50);
  }
  var draw = function () {
    if (!CW.conf || !CW.out) return;
    var left = Math.max(0, CW.conf.grace - Math.floor((Date.now() - CW.out) / 1000));
    CW.n.textContent = String(left);
    CW.arc.setAttribute('stroke-dashoffset', (CW.arcC * (1 - left / Math.max(1, CW.conf.grace))).toFixed(2));
    CW.until.textContent = 'Signed out in ' + left + ' s unless the card is back';
    if (left <= 0) certWatchEnd('late');
  };
  draw();
  if (!CW.tick) CW.tick = setInterval(draw, 1000);
}
function certWatchEnd(why, asked) {
  if (!CW.conf) return;
  CW.gen++; CW.conf = null;
  if (CW.timer) clearTimeout(CW.timer);
  if (CW.tick) { clearInterval(CW.tick); CW.tick = null; }
  try {
    sessionStorage.setItem('otp.krb.out', '1');
    if (why) sessionStorage.setItem('otp.card.out', why);
  } catch (e) { }
  var go = function () { location.replace(location.pathname); };
  api('logout', {}).then(go, go);
}
/* Another tab saw the card out or the session over: this one checks at once. */
window.addEventListener('storage', function (e) {
  if (e.key !== CW_SHARED || !CW.conf) return;
  var v = certWatchShared();
  if (v && v.w !== 1) certWatchNow();
});
if (typeof ME !== 'undefined' && ME && ME.card) certWatchStart(ME.card);


/* ---- upgrades and maintenance (1.0.37) ------------------------------------ */""")])

s = open(O + 'web/assets/otp.css').read()
if '.cw-layer' not in s:
    s += r'''
/* The card's notice (1.0.285; the kit "card-removal-watch", design B: the seconds in a ring). */
.cw-layer{position:fixed;inset:0;z-index:9000;display:flex;align-items:center;justify-content:center;padding:16px;
  background:rgba(5,8,12,.72);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.cw-box{width:min(440px,calc(100vw - 32px));padding:30px 28px 26px;border:1px solid var(--line);border-radius:18px;
  background:var(--panel);text-align:center;box-shadow:0 24px 70px rgba(0,0,0,.55)}
.cw-ring{position:relative;width:150px;height:150px;margin:0 auto;display:flex;align-items:center;justify-content:center}
.cw-ring svg{position:absolute;inset:0;width:100%;height:100%;transform:rotate(-90deg)}
.cw-track{fill:none;stroke:var(--line);stroke-width:7}
.cw-arc{fill:none;stroke:var(--warn);stroke-width:7;stroke-linecap:round;transition:stroke-dashoffset .9s linear}
.cw-mid{position:relative;display:flex;flex-direction:column;align-items:center}
.cw-n{font-size:46px;font-weight:800;line-height:1;color:var(--warn);font-variant-numeric:tabular-nums}
.cw-unit{font-size:13px;font-weight:600;color:var(--tx-dim);margin-top:3px}
.cw-box h3{margin:16px 0 8px;font-size:21px;color:var(--tx)}
.cw-p{margin:0 0 14px;color:var(--tx-dim);font-size:14px;line-height:1.55}
.cw-until{color:var(--warn);font-weight:600;font-size:13.5px;margin:0 0 18px}
@media (prefers-reduced-motion:reduce){.cw-arc{transition:none}}
'''
    open(O + 'web/assets/otp.css', 'w').write(s)
print('1.0.285 web patched')
