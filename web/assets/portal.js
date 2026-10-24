/* portal.js - the enrolment pages: somebody making their own token.
   Drawn with isemon's pieces (core.js); every answer comes from the daemon. */
'use strict';

function drawLangPick() {
  var host = $('langpick');
  if (!host || !window.OTP_LANGS || window.OTP_LANGS.length < 2) return;
  clear(host);
  window.OTP_LANGS.forEach(function (l) {
    var b = el('button', l.code === window.OTP_LANG ? 'on' : '', l.code.toUpperCase());
    b.type = 'button';
    b.setAttribute('data-no-i18n', '');
    b.title = l.name;
    b.onclick = function () {
      document.cookie = 'otp_lang=' + encodeURIComponent(l.code) + '; path=/; max-age=31536000; '
        + 'samesite=strict' + (location.protocol === 'https:' ? '; secure' : '');
      location.reload();
    };
    host.appendChild(b);
  });
}

/** The help an administrator wrote, as paragraphs, text and nothing else. */
function drawHelp(host, text) {
  if (!host || !text) return;
  clear(host);
  String(text).split(/\n\s*\n/).forEach(function (para) {
    var p = el('p', '');
    para.split('\n').forEach(function (line, i) {
      if (i) p.appendChild(el('br'));
      p.appendChild(document.createTextNode(line));
    });
    host.appendChild(p);
  });
}

function portalDoor() {
  drawLangPick();
  var h = $('help-text');
  if (h) drawHelp(h, h.getAttribute('data-help'));
  var form = $('signin-form'), said = $('in-said'), go = $('in-go');
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    said.className = 'said';
    said.textContent = '';
    go.disabled = true;
    var words = go.querySelector('span');
    words.textContent = 'Signing in…';
    api('login', {name: $('in-name').value, password: $('in-pass').value}).then(function () {
      said.className = 'said good';
      said.textContent = 'Welcome.';
      location.reload();
    }).catch(function (e) {
      said.className = 'said bad';
      said.textContent = String(e.message || e);
      go.disabled = false;
      words.textContent = 'Sign in';
      $('in-pass').value = '';
      $('in-pass').focus();
    });
  });
  $('in-name').focus();
}

var ME = null;

function portalApp(me) {
  ME = me;
  drawLangPick();
  dressButtons(document);
  $('signout').onclick = function () {
    api('logout', {}).then(function () { location.reload(); }, function () { location.reload(); });
  };
  drawPortal();
}

function stateCard(kind, title, words) {
  var box = el('div', 'bigstate');
  var mark = el('div', 'mark ' + kind);
  mark.innerHTML = iconMarkup(kind === 'ok' ? 'check' : (kind === 'warn' ? 'clock' : 'token'), 24);
  box.appendChild(mark);
  var w = el('div', 'words');
  w.appendChild(el('b', '', title));
  if (words) w.appendChild(el('span', '', words));
  box.appendChild(w);
  return box;
}

/* The ways of getting a code (1.0.76): the app, a code by mail, a code by
   SMS - what the person's realm offers. */
var WAYS = {
  totp: {icon: 'token', title: 'The app on my phone',
         words: 'An authenticator application shows a new code every 30 seconds. Works without signal.'},
  mail: {icon: 'mail', title: 'A code by e-mail',
         words: 'After your password the VPN asks for a code we send to your mailbox.'},
  sms: {icon: 'phone', title: 'A code by SMS',
        words: 'After your password the VPN asks for a code we send to your phone as a text message.'}
};
var VER_LAST = null;

function drawPortal() {
  var host = $('portal');
  clear(host);
  var tok = ME.token;
  var card = el('div', 'card');
  host.appendChild(card);
  var ways = ME.methods || ['totp'];
  if (ME.verify) {
    card.appendChild(verifyCard());
  } else if (ME.may_replace && tok) {
    card.appendChild(stateCard('warn', 'Choose the new way',
      'Your token goes on working until the new one is set up.'));
    card.appendChild(wayChooser(true));
  } else if (!tok && (ways.length > 1 || ways[0] !== 'totp')) {
    card.appendChild(stateCard('crit', 'You have no token yet',
      'Choose how you will get the code the VPN asks for after your password.'));
    card.appendChild(wayChooser(false));
  } else if (tok && tok.kind && tok.kind !== 'totp') {
    card.appendChild(stateCard(tok.state === 'disabled' ? 'crit' : 'ok',
      tok.state === 'disabled' ? 'Your token is switched off'
        : (tok.kind === 'mail' ? 'You get your codes by e-mail' : 'You get your codes by SMS'),
      tok.state === 'disabled' ? 'The administrator has switched it off; ask them.'
        : 'To ' + tok.dest + ' · ' + (tok.last_used ? 'last used ' + stamp(tok.last_used)
        : 'never used') + ' · ' + tok.scratch_left + ' recovery code(s) left'));
    if (tok.pending) {
      /* Being replaced by the app (1.0.103): after a reload the box to
         confirm it was gone, and the app scanned never came into use. */
      card.appendChild(el('p', 'note', 'A new token was made and is waiting for a code from it. '
        + 'Until then the old one goes on working.'));
      card.appendChild(confirmForm(true));
      var keepOld = cmdButton('Keep the old one', 'undo', '');
      keepOld.onclick = function () {
        api('cancel', {}).then(function (d) { ME = d.me; drawPortal(); toast('the old token stays', 'good'); }).catch(oops);
      };
      var r3 = el('div', 'btnrow');
      r3.style.marginTop = '14px';
      r3.appendChild(keepOld);
      card.appendChild(r3);
    } else if (tok.state !== 'disabled') {
      card.appendChild(el('p', 'note', 'Sign in to the VPN with your name and password; it then '
        + 'asks for a code in a second window, and we send the code '
        + (tok.kind === 'mail' ? 'to your mailbox. No mail? A recovery code works there instead.'
          : 'to your phone. No signal? A recovery code works there instead.')));
      if (ME.reissue) host.appendChild(reissueCard());
    }
  } else if (!tok) {
    card.appendChild(stateCard('crit', 'You have no token yet',
      'A token is the application on your phone that shows a new code every few seconds. '
      + 'The VPN asks for that code.'));
    card.appendChild(howTo());
    var go = cmdButton('Make my token', 'add', 'primary');
    go.onclick = function () { enrol(go); };
    card.appendChild(go);
  } else if (tok.state === 'pending') {
    card.appendChild(stateCard('warn', 'Your token is waiting for a code',
      'It was made, and it is not in use until a code from it is typed here. If you scanned '
      + 'it, type the code your phone shows now. If you did not, make it again.'));
    card.appendChild(confirmForm(false));
    var again = cmdButton('Make it again', 'refresh', '');
    again.onclick = function () {
      /* Busy from the first press (1.0.57): pressed twice, two tokens were
         made and the one shown could be the one the server had replaced. */
      if (again.disabled) return;
      busy(again, true);
      api('cancel', {}).then(function (d) { ME = d.me; enrol(again); }).catch(function (e) { busy(again, false); oops(e); });
    };
    var row = el('div', 'btnrow');
    row.style.marginTop = '14px';
    row.appendChild(again);
    /* Another way after all (1.0.103) - mail or SMS - where it is offered. */
    if (ways.length > 1) {
      var other = cmdButton('Choose another way', 'prev', '');
      other.onclick = function () {
        if (other.disabled) return;
        busy(other, true);
        api('cancel', {}).then(function (d) { ME = d.me; drawPortal(); }).catch(function (e) { busy(other, false); oops(e); });
      };
      row.appendChild(other);
    }
    card.appendChild(row);
  } else {
    card.appendChild(stateCard(tok.state === 'disabled' ? 'crit' : 'ok',
      tok.state === 'disabled' ? 'Your token is switched off' : 'You have a token',
      tok.state === 'disabled' ? 'The administrator has switched it off; ask them.'
        : 'Made ' + stamp(tok.created) + ' · ' + (tok.last_used ? 'last used ' + stamp(tok.last_used)
        : 'never used') + ' · ' + tok.scratch_left + ' recovery code(s) left'));
    if (tok.pending) {
      card.appendChild(el('p', 'note', 'A new token was made and is waiting for a code from it. '
        + 'Until then the old one goes on working.'));
      card.appendChild(confirmForm(true));
      var keep = cmdButton('Keep the old one', 'undo', '');
      keep.onclick = function () {
        api('cancel', {}).then(function (d) { ME = d.me; drawPortal(); toast('the old token stays', 'good'); }).catch(oops);
      };
      var r2 = el('div', 'btnrow');
      r2.style.marginTop = '14px';
      r2.appendChild(keep);
      card.appendChild(r2);
    } else if (ME.reissue && tok.state !== 'disabled') {
      host.appendChild(reissueCard());
    }
  }
  if (ME.help) {
    var help = el('div', 'card help');
    var inner = el('div');
    drawHelp(inner, ME.help);
    help.appendChild(inner);
    host.appendChild(help);
  }
  explainWhatWasDrawn(host);
}

/** The choice of a way, and where a sent code goes. */
function wayChooser(replacing) {
  var ways = ME.methods || ['totp'];
  var wrap = el('div', 'ways');
  var pick = {kind: ways.length === 1 ? ways[0] : (ME.token && ME.token.kind && ways.indexOf(ME.token.kind) < 0 ? ways[0] : null)};
  var tiles = el('div', 'way-tiles');
  var destBox = el('div', 'way-dest');
  var said = el('div', 'said');
  var inputs = {};
  var go = cmdButton(replacing ? 'Set it up' : 'Continue', 'next', 'primary');
  /* The language of the codes and of the VPN's question, and for a mail
     HTML or plain text (1.0.83) - chosen here, changed later by an
     administrator. */
  var langs = (window.OTP_LANGS || [{code: 'cs', name: 'Čeština'}, {code: 'en', name: 'English'}])
    .filter(function (l) { return l.code === 'cs' || l.code === 'en'; });
  if (!langs.length) langs = [{code: 'cs', name: 'Čeština'}, {code: 'en', name: 'English'}];
  var langSel = selectBox(langs.map(function (l) { return [l.code, l.name || l.code.toUpperCase()]; }),
                          window.OTP_LANG === 'en' ? 'en' : 'cs');
  noI18n(langSel);
  var fmtSel = selectBox([['html', 'with colours and the code large (HTML)'], ['text', 'plain text only']],
                         ME.mail_fmt_default || 'html');
  var prefs = el('div', 'formgrid way-prefs');
  var fLang = formField('Language of the codes', langSel);
  var fFmt = formField('The mail with the code', fmtSel);
  prefs.appendChild(fLang);
  prefs.appendChild(fFmt);
  var paint = function () {
    Array.prototype.forEach.call(tiles.children, function (t) { t.classList.toggle('on', t.dataset.k === pick.kind); });
    clear(destBox);
    if (pick.kind === 'mail' || pick.kind === 'sms') {
      var inp = inputs[pick.kind];
      if (!inp) {
        inp = inputs[pick.kind] = textBox((ME.suggest || {})[pick.kind] || '', pick.kind === 'mail'
          ? 'name@example.cz' : '+420 603 123 456', '');
        inp.type = pick.kind === 'mail' ? 'email' : 'tel';
        inp.autocomplete = pick.kind === 'mail' ? 'email' : 'tel';
        noI18n(inp);
        inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') go.click(); });
      }
      destBox.appendChild(formField(pick.kind === 'mail' ? 'Your e-mail address' : 'Your mobile number', inp));
      /* Where it came from (1.0.91): the company directory's, and that it
         can be changed. */
      if ((ME.suggest || {})[pick.kind]) {
        destBox.appendChild(el('p', 'muted small', pick.kind === 'mail'
          ? 'Filled in from the company directory - change it if the codes should go elsewhere.'
          : 'Filled in from the company directory - change it if the codes should go to another phone.'));
      }
      destBox.appendChild(el('p', 'muted small', 'We send a code there now; type it on the next step to prove it reaches you.'));
      setTimeout(function () { inp.focus(); }, 30);
    }
    if (pick.kind) {
      destBox.appendChild(prefs);
      fFmt.hidden = pick.kind !== 'mail';
      /* The language of the app's token is only the VPN's question. */
      fLang.querySelector('label').textContent = pick.kind === 'totp' ? 'Language of the VPN’s question' : 'Language of the codes';
    }
    go.disabled = !pick.kind;
  };
  ways.forEach(function (k) {
    var w = WAYS[k];
    var t = el('button', 'way-tile');
    t.type = 'button';
    t.dataset.k = k;
    var ic = el('span', 'way-ic');
    ic.innerHTML = iconMarkup(w.icon, 22);
    t.appendChild(ic);
    var tx = el('span', 'way-tx');
    tx.appendChild(el('b', '', w.title));
    tx.appendChild(el('span', '', w.words));
    t.appendChild(tx);
    t.onclick = function () { pick.kind = k; paint(); };
    tiles.appendChild(t);
  });
  wrap.appendChild(tiles);
  wrap.appendChild(destBox);
  var row = el('div', 'btnrow');
  row.style.marginTop = '14px';
  row.appendChild(go);
  if (replacing) {
    var keep = cmdButton('Keep the one I have', 'undo', '');
    keep.onclick = function () { api('cancel', {}).then(function (d) { ME = d.me; drawPortal(); }).catch(oops); };
    row.appendChild(keep);
  }
  wrap.appendChild(row);
  wrap.appendChild(said);
  go.onclick = function () {
    said.className = 'said';
    said.textContent = '';
    if (pick.kind === 'totp') { enrol(go, langSel.value); return; }
    var dest = (inputs[pick.kind] || {}).value || '';
    if (!dest.trim()) { said.className = 'said bad'; said.textContent = pick.kind === 'mail' ? 'Type your e-mail address.' : 'Type your mobile number.'; return; }
    busy(go, true);
    VER_LAST = {kind: pick.kind, dest: dest, lang: langSel.value,
                mail_fmt: pick.kind === 'mail' ? fmtSel.value : ''};
    api('enroll', VER_LAST).then(function (d) {
      ME = d.me;
      drawPortal();
    }).catch(function (e) {
      said.className = 'said bad';
      said.textContent = String(e.message || e);
    }).then(function () { busy(go, false); });
  };
  paint();
  return wrap;
}

/** The code sent to the address or the number, typed back. */
function verifyCard() {
  var v = ME.verify || {};
  var wrap = el('div');
  wrap.appendChild(stateCard('warn', v.kind === 'mail' ? 'Check your mailbox' : 'Check your phone',
    'We sent a code to ' + (v.dest || '') + '. Type it here - then you are set up.'));
  var f = el('form', 'btnrow');
  var box = textBox('', '000000', 'codein');
  box.inputMode = 'numeric';
  box.maxLength = 10;
  box.autocomplete = 'one-time-code';
  noI18n(box);
  var go = cmdButton('Confirm', 'check', 'primary');
  go.type = 'submit';
  f.appendChild(box);
  f.appendChild(go);
  var said = el('div', 'said');
  wrap.appendChild(f);
  wrap.appendChild(said);
  var row = el('div', 'btnrow');
  row.style.marginTop = '14px';
  /* After a reload too (1.0.98): the address is the one the server keeps
     for this check, asked for by `again`. */
  if (VER_LAST || (ME && ME.verify)) {
    var again = cmdButton('Send it again', 'refresh', '');
    again.onclick = function () {
      busy(again, true);
      api('enroll', VER_LAST || {kind: ME.verify.kind, again: true, lang: window.OTP_LANG || ''}).then(function (d) { ME = d.me; drawPortal(); toast('sent again', 'good'); })
        .catch(oops).then(function () { busy(again, false); });
    };
    row.appendChild(again);
  }
  var other = cmdButton('Another address or way', 'undo', '');
  other.onclick = function () { api('cancel', {}).then(function (d) { ME = d.me; drawPortal(); }).catch(oops); };
  row.appendChild(other);
  wrap.appendChild(row);
  f.addEventListener('submit', function (e) {
    e.preventDefault();
    var typed = box.value.replace(/\s/g, '');
    if (!/^[0-9]{4,10}$/.test(typed)) {
      said.className = 'said bad';
      said.textContent = 'Type the code from the message: its digits only.';
      return;
    }
    busy(go, true);
    said.className = 'said';
    said.textContent = '';
    api('verify', {code: typed}).then(function (d) {
      ME = d.me;
      showSentMade(d.made);
    }).catch(function (e) {
      said.className = 'said bad';
      said.textContent = String(e.message || e);
      if (e.status === 410 || /last try|ran out/.test(String(e.message))) {
        setTimeout(function () { api('me').then(function (d) { ME = d.me; drawPortal(); }).catch(function () { /* the next look draws it */ }); }, 2500);
      }
      box.select();
    }).then(function () { busy(go, false); });
  });
  setTimeout(function () { box.focus(); }, 50);
  return wrap;
}

/** Set up with codes by mail or SMS: the recovery codes, once. */
function showSentMade(made) {
  var host = $('portal');
  clear(host);
  var card = el('div', 'card');
  card.appendChild(stateCard('ok', 'You are set up', 'Sign in to the VPN with your name and '
    + 'password; it then asks for the code we send ' + (made.kind === 'mail' ? 'by e-mail to ' : 'by SMS to ')
    + made.dest + '.'));
  if (made.scratch && made.scratch.length) {
    var sc = el('div');
    sc.style.marginTop = '18px';
    sc.appendChild(el('h3', 'peek-h', 'Recovery codes'));
    sc.appendChild(el('p', 'note', 'Each works once, instead of a sent code, for the day the '
      + 'mail or the signal does not come. Print them or write them down and keep them '
      + 'somewhere safe: they are not shown again.'));
    var codes = el('div', 'codes');
    made.scratch.forEach(function (c) {
      codes.appendChild(copyOnClick(noI18n(el('span', '', c)), c, 'the recovery code was copied'));
    });
    sc.appendChild(codes);
    var pr = cmdButton('Print them', 'download', 'small noprint');
    pr.onclick = function () { window.print(); };
    sc.appendChild(pr);
    card.appendChild(sc);
  }
  var back = cmdButton('Done', 'check', 'primary');
  back.style.marginTop = '16px';
  back.onclick = function () { drawPortal(); };
  card.appendChild(back);
  host.appendChild(card);
  explainWhatWasDrawn(host);
}

function howTo() {
  var ol = el('ol', 'howto');
  [['Install an authenticator application on your phone', ' - Google Authenticator, '
    + 'Microsoft Authenticator, or any other that reads a QR code.'],
   ['Press Make my token below', ' - a QR code appears.'],
   ['In the application, add an account and scan the QR code', ' - it starts showing '
    + 'codes at once.'],
   ['Type the code it shows here', ' - and the token is ready for the VPN.']].forEach(function (one) {
    var li = el('li');
    li.appendChild(el('b', '', one[0]));
    li.appendChild(document.createTextNode(one[1]));
    ol.appendChild(li);
  });
  return ol;
}

function enrol(button, lang) {
  busy(button, true);
  /* Away from codes sent, to the app (1.0.94): the old token goes on
     working until the new one is confirmed - said so, not "not in use". */
  var replacing = !!(ME && ME.may_replace);
  api('enroll', {lang: lang || window.OTP_LANG || ''}).then(function (d) {
    showMade(d.made, d.confirm, replacing);
  }).catch(oops).then(function () { busy(button, false); });
}

/** The new token: the QR code, the key as text, the recovery codes, and the
    box the first code goes into. */
function showMade(made, confirm, replacing) {
  var host = $('portal');
  clear(host);
  var card = el('div', 'card');
  card.appendChild(el('h2', '', replacing ? 'Your new token' : 'Your token'));
  var grid = el('div', 'enrol');
  var left = el('div');
  var qr = el('div', 'qrbox');
  var img = el('img');
  img.src = made.qr;
  img.alt = 'QR code';
  qr.appendChild(img);
  left.appendChild(qr);
  grid.appendChild(left);
  var right = el('div');
  right.appendChild(el('p', 'lede', 'Scan this with the authenticator application on your '
    + 'phone: add an account, then choose to scan a QR code.'));
  right.appendChild(kvTable([['Issuer', made.issuer], ['Account', made.label],
                             ['Codes', made.digits + ' digits, a new one every ' + made.period
                              + ' s']]));
  if (made.secret_spaced) {
    right.appendChild(el('p', 'muted small', 'No camera? Type this key into the application '
      + 'instead (time based):'));
    var key = el('div', 'keytext', made.secret_spaced);
    noI18n(key);
    copyOnClick(key, String(made.secret_spaced || '').replace(/\s+/g, ''), 'the key was copied');
    right.appendChild(key);
  }
  grid.appendChild(right);
  card.appendChild(grid);
  if (made.scratch && made.scratch.length) {
    var sc = el('div');
    sc.style.marginTop = '18px';
    sc.appendChild(el('h3', 'peek-h', 'Recovery codes'));
    sc.appendChild(el('p', 'note', 'Each works once, instead of a code from the phone, for '
      + 'the day the phone is lost or flat. Print them or write them down and keep them '
      + 'somewhere safe: they are not shown again.'));
    var codes = el('div', 'codes');
    made.scratch.forEach(function (c) {
      codes.appendChild(copyOnClick(noI18n(el('span', '', c)), c, 'the recovery code was copied'));
    });
    sc.appendChild(codes);
    var pr = cmdButton('Print them', 'download', 'small noprint');
    pr.onclick = function () { window.print(); };
    sc.appendChild(pr);
    card.appendChild(sc);
  }
  host.appendChild(card);
  if (confirm) {
    var c2 = el('div', 'card noprint');
    c2.appendChild(el('h2', '', 'Type the code your phone shows now'));
    c2.appendChild(el('p', 'note', replacing
      ? 'Until you do, the old token goes on working and this one does not.'
      : 'Until you do, the token is not in use.'));
    c2.appendChild(confirmForm(replacing));
    host.appendChild(c2);
  } else {
    var done = el('div', 'card');
    done.appendChild(stateCard('ok', 'The token is ready', 'Sign in to the VPN with the code '
      + 'your phone shows.'));
    var back = cmdButton('Done', 'check', 'primary');
    back.onclick = function () { location.reload(); };
    done.appendChild(back);
    host.appendChild(done);
  }
  explainWhatWasDrawn(host);
}

function confirmForm(replacing) {
  var f = el('form', 'btnrow');
  var box = textBox('', '000000', 'codein');
  box.inputMode = 'numeric';
  box.maxLength = 8;
  box.autocomplete = 'one-time-code';
  noI18n(box);
  var go = cmdButton(replacing ? 'Use the new token' : 'Confirm', 'check', 'primary');
  go.type = 'submit';
  f.appendChild(box);
  f.appendChild(go);
  var said = el('div', 'said');
  var wrap = el('div');
  wrap.appendChild(f);
  wrap.appendChild(said);
  f.addEventListener('submit', function (e) {
    e.preventDefault();
    busy(go, true);
    said.className = 'said';
    said.textContent = '';
    var typed = box.value.replace(/\s/g, '');
    /* Not digits, or too few: said here, not counted as a wrong code there
       (1.0.36). */
    if (!/^[0-9]{6,8}$/.test(typed)) {
      said.className = 'said bad';
      said.textContent = 'Type the code the application shows: its digits only.';
      busy(go, false);
      box.select();
      return;
    }
    api('confirm', {code: typed}).then(function (d) {
      if (d.good) {
        ME = d.me;
        var host = $('portal');
        clear(host);
        var card = el('div', 'card');
        card.appendChild(stateCard('ok', 'The token is ready', 'Sign in to the VPN with the '
          + 'code your phone shows. Each code works once.'));
        var back = cmdButton('Done', 'check', 'primary');
        back.onclick = function () { drawPortal(); };
        card.appendChild(back);
        host.appendChild(card);
      } else {
        said.className = 'said bad';
        clear(said);
        /* The daemon says "Not a valid token. " and then why: two sentences,
           each translated on its own (1.0.36). */
        var why = String(d.said || '');
        if (why.indexOf('Not a valid token') === 0) {
          why = why.replace(/^Not a valid token\.?\s*/, '');
          said.appendChild(el('div', '', 'That is not the code the token shows now.'));
          said.appendChild(el('div', '', why || 'Wait for the next one and type it.'));
        } else {
          said.textContent = why;
        }
        box.select();
      }
    }).catch(function (e) {
      said.className = 'said bad';
      said.textContent = String(e.message || e);
    }).then(function () { busy(go, false); });
  });
  setTimeout(function () { box.focus(); }, 50);
  return wrap;
}

function reissueCard() {
  var card = el('div', 'card');
  var sent = ME.token && ME.token.kind && ME.token.kind !== 'totp';
  var ways = ME.methods || ['totp'];
  card.appendChild(el('h2', '', sent ? 'Another address, number or way' : 'A new phone, or a new token'));
  card.appendChild(el('p', 'note', sent
    ? 'To change where your codes go, type your password and a code we send you now - or one '
      + 'of your recovery codes. If you have neither, ask the administrator.'
    : 'To replace your token, type your password and a code from '
    + 'the token you have now - or one of your recovery codes. If you have lost both, ask the '
    + 'administrator.'));
  var pw = el('input');
  pw.type = 'password';
  pw.placeholder = 'password';
  pw.autocomplete = 'current-password';
  /* Not .mono: that would leave its hint untranslated. */
  var code = textBox('', sent ? (ME.token.kind === 'mail' ? 'the code from the mail' : 'the code from the SMS')
                                : 'a code from the old token', '');
  code.style.fontFamily = 'ui-monospace,SFMono-Regular,Menlo,Consolas,monospace';
  code.inputMode = 'numeric';
  var grid = el('div', 'formgrid');
  grid.appendChild(formField('Your password', pw));
  /* With codes sent (1.0.80): the code has to be asked for first - a button
     of its own beside the box, as tall as it, not a small one under it. */
  var codeHost = code;
  if (sent) {
    codeHost = el('div', 'code-ask');
    codeHost.appendChild(code);
  }
  grid.appendChild(formField(sent ? 'A code we send you now, or a recovery code' : 'A code from the old token', codeHost,
    sent ? 'Press ' + (ME.token.kind === 'mail' ? 'Send me a code: it goes to your mailbox.' : 'Send me a code: it goes to your phone.')
      + ' It proves the change is yours.' : ''));
  card.appendChild(grid);
  var said = el('div', 'said');
  if (sent) {
    var send = cmdButton('Send me a code', ME.token.kind === 'mail' ? 'mail' : 'phone', '');
    send.onclick = function () {
      busy(send, true);
      api('sendold', {lang: window.OTP_LANG || ''}).then(function (d) {
        said.className = 'said good';
        said.textContent = 'A code was sent to ' + d.sent_to + '.';
        code.focus();
      }).catch(function (e) { said.className = 'said bad'; said.textContent = String(e.message || e); })
        .then(function () { busy(send, false); });
    };
    codeHost.appendChild(send);
  }
  /* Which way next (1.0.76): the same, or another the realm offers. */
  var want = 'totp';
  if (!sent && ways.length > 1) {
    var other = el('label', 'check small');
    other.style.marginTop = '10px';
    var cb = el('input'); cb.type = 'checkbox';
    other.appendChild(cb);
    other.appendChild(el('span', '', 'I want to get my codes another way (e-mail or SMS)'));
    cb.onchange = function () { want = cb.checked ? 'other' : 'totp'; };
    card.appendChild(other);
  }
  var go = cmdButton(sent ? 'Go on' : 'Make a new token', sent ? 'next' : 'refresh', 'primary');
  go.style.marginTop = '12px';
  go.onclick = function () {
    busy(go, true);
    said.className = 'said';
    said.textContent = '';
    api('reissue', {password: pw.value, code: code.value.replace(/\s/g, ''), kind: sent ? 'other' : want}).then(function (d) {
      if (d.choose) { ME = d.me; drawPortal(); return; }
      showMade(d.made, d.confirm, true);
    }).catch(function (e) {
      said.className = 'said bad';
      said.textContent = String(e.message || e);
    }).then(function () { busy(go, false); });
  };
  card.appendChild(go);
  card.appendChild(said);
  return card;
}
