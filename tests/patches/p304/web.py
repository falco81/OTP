# 1.0.304: the upgrade (hunt round 3) - a save that fails during an upgrade is said, not swallowed; a
# daemon down after the upgrade ended is "not answering", not "in maintenance"; the sign-in page loads
# again only when the daemon really came back, and never under somebody typing.   python3 web.py OUTDIR
import sys
W = sys.argv[1].rstrip('/') + '/web/'


def edit(f, pairs):
    s = open(W + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(W + f, 'w').write(s)


edit('assets/core.js', [
("""      return data;
    });
  });
}
""",
 """      return data;
    });
  }).catch(function (e) {
    /* Whether it was a change (1.0.304): a save that fails during an upgrade is said - only what
       is asked again by itself (a look, a list) goes silent while the band explains it. */
    if (e && typeof e === 'object') e.post = !!opts.method;
    throw e;
  });
}
"""),
("""  if (e && (e.upgrading || (e.unreachable && typeof upgradeExpected === 'function' && upgradeExpected()))) return;""",
 """  if (e && (e.upgrading || (e.unreachable && typeof upgradeExpected === 'function' && upgradeExpected()))) {
    if (!e.post) return;
    toast('Not saved: otp is being upgraded - try again once it answers', 'bad');
    return;
  }"""),
])

edit('assets/admin.js', [
("""  UPG.u = u;
  if (from !== 'status') {
    if (!UPG.away) UPG.away = Date.now();
    UPG.phpAway = false;
  }
  upgradeNote();""",
 """  UPG.u = u;
  /* Away only while it runs (1.0.304): a daemon down after the upgrade ended (done, failed) is
     down - said as such, not "in maintenance" for half an hour. */
  if (from !== 'status' && u.state === 'running') {
    if (!UPG.away) UPG.away = Date.now();
    UPG.phpAway = false;
  }
  upgradeNote();"""),
("""  var want = upgradeRunning() || UPG.reloading || (UPG.away && Date.now() - UPG.away < 30 * 60000);""",
 """  var want = upgradeRunning() || UPG.reloading;"""),
("""      if (UPG.away) { $('offline').hidden = true; upgPill(); }""",
 """      if (UPG.away && upgradeRunning()) { $('offline').hidden = true; upgPill(); }
      else if (!upgradeRunning()) UPG.away = 0;"""),
])

edit('admin/index.php', [
("""        [$hs] = otp_call('/api/health', 'GET', null, 3.0);""",
 """        [$hs, $hb] = otp_call('/api/health', 'GET', null, 3.0);
        /* Answering as the sign-in page means it (1.0.304): its database open too - the page loaded
           again every 2 s while the database was still opening. */
        $hj = json_decode((string) $hb, true);
        $up = $hs === 200 && is_array($hj) && !empty($hj['database']['ok']);"""),
("""                          'pages' => OTP_VERSION, 'api' => $hs === 200],""",
 """                          'pages' => OTP_VERSION, 'api' => $up],"""),
("""      if (!d.api) { down = true; return; }
      if (down || !u || u.state !== 'running') { location.reload(); return; }""",
 """      if (!d.api) { down = true; return; }
      if (down || !u || u.state !== 'running') {
        /* Never under somebody typing (1.0.304): a name, a password or a code - said, loaded with a press. */
        var a = document.activeElement;
        var typing = Array.prototype.some.call(document.querySelectorAll('.signin input:not([type=hidden])'), function (x) {
          return x === a || (x.value || '') !== '';
        });
        if (!typing) { location.reload(); return; }
        if (!document.getElementById('upband-in-again')) {
          var again = document.createElement('a');
          again.id = 'upband-in-again';
          again.className = 'fgo';
          again.textContent = (typeof i18nText === 'function' && i18nText('It is back - load the page again')) || 'It is back - load the page again';
          again.onclick = function () { location.reload(); };
          box.appendChild(again);
        }
        return;
      }"""),
])
print('ok')
