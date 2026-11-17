# 1.0.299 PHP: the pages read how far an upgrade of this node is straight from the disk
# (.upgrade.json, root's) - while the daemon, nginx and PHP restart.   python3 php.py OUTDIR
import sys
D = sys.argv[1].rstrip('/') + '/web/'


def edit(f, pairs):
    s = open(D + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(D + f, 'w').write(s)


edit('otp-api.php', [
("""/** Call the daemon and return the decoded reply, or null. */""",
 """/**
 * How far an upgrade of this node is (1.0.299), or null: .upgrade.json beside these pages, which
 * root writes whole (otp_upgrade.py, install.sh --upgrade) and nginx never serves (a dot name).
 * Read from the disk, not through the daemon - it is what restarts. Believed only as written:
 * running for 30 min after its last word, done or failed for 10; one of the three states, its
 * time not ahead. Who asked, why it failed and its id only for a page with a session ($full).
 */
function otp_upgrading(bool $full = false): ?array
{
    static $got = false;
    if ($got === false) {
        $got = null;
        $f = __DIR__ . '/.upgrade.json';
        $raw = is_link($f) ? false : @file_get_contents($f, false, null, 0, 65536);
        $d = is_string($raw) ? json_decode($raw, true) : null;
        if (is_array($d)) {
            $state = (string) ($d['state'] ?? '');
            $keep = ['running' => 1800, 'done' => 600, 'failed' => 600][$state] ?? 0;
            $at = is_numeric($d['at'] ?? null) ? (int) $d['at'] : 0;
            $now = time();
            if ($keep > 0 && $at > 0 && $at <= $now + 60 && $now - $at <= $keep) {
                $t = static function ($v, int $most): string {
                    $s = preg_replace('/[\\x00-\\x1f\\x7f]/', '', is_scalar($v) ? (string) $v : '');
                    $s = substr((string) $s, 0, $most);
                    return preg_match('//u', $s) ? $s : '';
                };
                $ver = static function ($v): string {
                    return is_string($v) && preg_match('/^\\d{1,4}\\.\\d{1,4}\\.\\d{1,6}\\z/', $v) ? $v : '';
                };
                $n = static function ($v, int $hi): int {
                    return is_numeric($v) ? max(0, min($hi, (int) $v)) : 0;
                };
                $got = [
                    'state' => $state, 'version' => $ver($d['version'] ?? ''), 'from' => $ver($d['from'] ?? ''),
                    'node' => (string) preg_replace('/[^A-Za-z0-9._-]/', '', $t($d['node'] ?? '', 64)),
                    'part' => $n($d['part'] ?? 0, 99), 'parts' => $n($d['parts'] ?? 0, 99),
                    'words' => $t($d['words'] ?? '', 200),
                    'started' => $n($d['started'] ?? 0, PHP_INT_MAX), 'at' => $at,
                    'downgrade' => ($d['downgrade'] ?? false) === true,
                    'by' => $t($d['by'] ?? '', 100), 'said' => $t($d['said'] ?? '', 300),
                    'id' => (string) preg_replace('/[^A-Za-z0-9._-]/', '', $t($d['id'] ?? '', 64)),
                ];
                if ($got['version'] === '') {
                    $got = null;
                }
            }
        }
    }
    if ($got === null) {
        return null;
    }
    $out = $got;
    if (!$full) {
        unset($out['by'], $out['said'], $out['id']);
    }
    return $out;
}

/** The answer of a daemon away while this node is upgraded (1.0.299): 503, and how far it is -
 *  the pages take it as expected, not as "down". False when no upgrade is known here. */
function otp_upgrading_answer(): bool
{
    $u = otp_upgrading(otp_session() !== '');
    if ($u === null) {
        return false;
    }
    http_response_code(503);
    echo json_encode(['ok' => false, 'upgrading' => $u, 'error' => $u['state'] === 'running'
        ? 'otp is being upgraded to ' . $u['version'] . ' - back in a moment'
        : 'the daemon is not answering — is otp.service running?'],
        JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
    return true;
}

/** Call the daemon and return the decoded reply, or null. */"""),
("""/** Pass a daemon reply straight through to the browser. */
function otp_relay(string $path, string $method = 'GET', array|object|null $payload = null,
                      float $timeout = 30.0): void
{
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');

    if (otp_token() === null) {
        http_response_code(503);""",
 """/** Pass a daemon reply straight through to the browser. $alter (1.0.299): an answer of 200
 *  changed on its way (decoded as objects, so {} stays {}), or null to pass it as it came. */
function otp_relay(string $path, string $method = 'GET', array|object|null $payload = null,
                      float $timeout = 30.0, ?callable $alter = null): void
{
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');

    if (otp_token() === null) {
        if (otp_upgrading_answer()) {
            return;
        }
        http_response_code(503);"""),
("""    [$status, $body] = otp_call($path, $method, $payload, $timeout);
    if ($status === 0) {
        http_response_code(503);
        echo json_encode(['ok' => false, 'error' =>
            'the daemon is not answering — is otp.service running?']);
        return;
    }""",
 """    [$status, $body] = otp_call($path, $method, $payload, $timeout);
    if ($status === 0) {
        if (otp_upgrading_answer()) {
            return;
        }
        http_response_code(503);
        echo json_encode(['ok' => false, 'error' =>
            'the daemon is not answering — is otp.service running?']);
        return;
    }
    if ($alter !== null && $status === 200) {
        $data = json_decode($body);
        if (is_object($data)) {
            $data = $alter($data);
            $again = is_object($data) ? json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
                                                          | JSON_INVALID_UTF8_SUBSTITUTE | JSON_PRESERVE_ZERO_FRACTION) : false;
            if (is_string($again)) {
                $body = $again;
            }
        }
    }"""),
])

edit('admin/index.php', [
("""    if ($what === 'logo' && !$post) {
        otp_serve_logo();
    }""",
 """    if ($what === 'logo' && !$post) {
        otp_serve_logo();
    }
    if ($what === 'upgrade-state' && !$post) {
        /* How far an upgrade of this node is (1.0.299), without the daemon: the pages ask this
           while it restarts - and whether it answers again, and the version of these files. */
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store');
        [$hs] = otp_call('/api/health', 'GET', null, 3.0);
        echo json_encode(['ok' => true, 'upgrading' => otp_upgrading(otp_session() !== ''),
                          'pages' => OTP_VERSION, 'api' => $hs === 200],
                         JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
        exit;
    }"""),
("""    $query = $_GET;
    unset($query['api']);
    otp_relay($reads[$what] . ($query ? '?' . http_build_query($query) : ''), 'GET', null, 60.0);
    exit;""",
 """    $query = $_GET;
    unset($query['api']);
    /* The status with this node's upgrade file in it, when there is one (1.0.299): the band
       appears at once, before anything restarts - and an upgrade by hand (no plan) too. */
    $alter = null;
    if ($what === 'status' && otp_upgrading(true) !== null) {
        $alter = static function (object $d): object {
            $d->upgrade_file = otp_upgrading(true);
            return $d;
        };
    }
    otp_relay($reads[$what] . ($query ? '?' . http_build_query($query) : ''), 'GET', null, 60.0, $alter);
    exit;"""),
("""$health  = otp_get('/api/health', 5.0);
$alive   = is_array($health);""",
 """$health  = otp_get('/api/health', 5.0);
$alive   = is_array($health);
/* This node being upgraded (1.0.299): the sign-in page says so itself, from the file, and loads
   again when the daemon is back - not "the daemon is not answering". */
$upg     = $me ? null : otp_upgrading(otp_session() !== '');
$upg_run = is_array($upg) && $upg['state'] === 'running';"""),
("""    <?php elseif (!$alive): ?>
      <div class="offline">The daemon is not answering.""",
 """    <?php endif; ?>
    <?php if ($upg_run):
        $upg_pc = $upg['parts'] > 0 ? (int) round(100 * max(0, $upg['part'] - 1) / $upg['parts']) : 3; ?>
      <div class="upband-in" id="upband-in" data-alive="<?= $alive ? '1' : '' ?>">
        <b><?= $upg['downgrade'] ? 'otp is being taken back to' : 'otp is being upgraded to' ?> <span data-no-i18n><?= h($upg['version']) ?></span></b>
        <div class="up-bar"><span id="upband-in-bar" style="width:<?= $upg_pc ?>%"></span></div>
        <div class="small muted"><span id="upband-in-words"><?= h($upg['words']) ?></span><?php if ($upg['parts'] > 0): ?> · <span id="upband-in-step" data-no-i18n><?= h($upg['part'] . ' / ' . $upg['parts']) ?></span><?php endif; ?></div>
        <div class="small">otp.service and these pages restart once - this page loads again by itself when they are back.</div>
      </div>
    <?php elseif (is_array($upg) && $upg['state'] === 'failed'): ?>
      <div class="offline">The upgrade to otp <span data-no-i18n><?= h($upg['version']) ?></span> failed<?= $upg['said'] !== '' ? ': <span data-no-i18n>' . h($upg['said']) . '</span>' : '' ?></div>
    <?php endif; ?>
    <?php if ($token_ok || !$token_there): ?>
    <?php if ($upg_run): ?>
    <?php elseif (!$alive): ?>
      <div class="offline">The daemon is not answering."""),
("""    <?php elseif (empty($health['users'])): ?>
      <div class="offline">There is no account on this machine yet. Make one on the server:<br>
        <span class="mono">otp --add-user yourname --role fulladmin</span></div>
    <?php endif; ?>""",
 """    <?php elseif (empty($health['users'])): ?>
      <div class="offline">There is no account on this machine yet. Make one on the server:<br>
        <span class="mono">otp --add-user yourname --role fulladmin</span></div>
    <?php endif; ?>
    <?php endif; ?>"""),
("""<script nonce="<?= h($nonce) ?>" src="/assets/core.js?v=<?= h(OTP_VERSION) ?>"></script>
<script nonce="<?= h($nonce) ?>">
(function () {
  var form = $('signin-form'), said = $('in-said'), go = $('in-go');""",
 """<script nonce="<?= h($nonce) ?>" src="/assets/core.js?v=<?= h(OTP_VERSION) ?>"></script>
<script nonce="<?= h($nonce) ?>">
/* This node being upgraded (1.0.299): asked every 2 s how far it is; loaded again once the daemon
   answers after having been away, or the upgrade has ended. */
(function () {
  var box = document.getElementById('upband-in');
  if (!box) return;
  var down = box.getAttribute('data-alive') !== '1', gone = 0;
  function ask() {
    fetch('?api=upgrade-state', {credentials: 'same-origin', cache: 'no-store'}).then(function (r) { return r.json(); }).then(function (d) {
      gone = 0;
      var u = d && d.upgrading;
      if (u && u.state === 'running') {
        var w = document.getElementById('upband-in-words'), s = document.getElementById('upband-in-step'), b = document.getElementById('upband-in-bar');
        if (w && u.words) w.textContent = (typeof i18nText === 'function' && i18nText(u.words)) || u.words;
        if (s && u.parts) s.textContent = u.part + ' / ' + u.parts;
        if (b && u.parts) b.style.width = Math.round(100 * Math.max(0, u.part - 1) / u.parts) + '%';
      }
      if (!d.api) { down = true; return; }
      if (down || !u || u.state !== 'running') { location.reload(); return; }
    }).catch(function () { down = true; gone++; }).then(function () { setTimeout(ask, 2000); });
  }
  setTimeout(ask, 2000);
}());
(function () {
  var form = $('signin-form'), said = $('in-said'), go = $('in-go');"""),
])

edit('healthz.php', [
("""if (otp_token() === null) {
    // Said as it is (1.0.36): the daemon may well be up; it is the pages
    // that cannot reach it.
    http_response_code(503);""",
 """/* This node being upgraded (1.0.299): a monitor sees maintenance, not "down" - the same 503. */
function otp_health_upgrading(): void
{
    $u = otp_upgrading();
    if ($u === null || $u['state'] !== 'running') {
        return;
    }
    http_response_code(503);
    echo 'maintenance ' . $u['node'] . ': being upgraded to ' . $u['version'] . "\\n";
    exit;
}
if (otp_token() === null) {
    otp_health_upgrading();
    // Said as it is (1.0.36): the daemon may well be up; it is the pages
    // that cannot reach it.
    http_response_code(503);"""),
("""if (!is_array($got) || empty($got['ok'])) {
    http_response_code(503);""",
 """if (!is_array($got) || empty($got['ok'])) {
    otp_health_upgrading();
    http_response_code(503);"""),
])
print('ok')
