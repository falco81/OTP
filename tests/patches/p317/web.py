"""1.0.317 (web, OUTDIR): a node's answer asked for again only once the last ask is back, and its end once;
an IPv6 network's prefix counted; a pasted colour escaped; "Show all" from the first page; the remote
backups' sizes with the page's decimal mark."""
import sys, pathlib
OUT = pathlib.Path(sys.argv[1])


def edit(path, pairs):
    p = pathlib.Path(path)
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (str(p), n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit(OUT / 'web/assets/admin.js', [
("""  return api(what, body).then(function (x) {
    var left = (x.nodes || []).slice(), began = Date.now();
    var timer = setInterval(function () {
      api(what, {action: 'result', id: x.id}).then(function (r) {
        left = left.filter(function (n) {
          var got = (r.nodes || {})[n];
          if (got) { onEach(n, got); return false; }
          return true;
        });
        if (!left.length || Date.now() - began > 60000) {
          clearInterval(timer);
          left.forEach(function (n) { onEach(n, {ok: false, error: 'did not answer in a minute - is it running?'}); });
          if (onDone) onDone();
        }
      }).catch(function () {
        /* Every answer failing (1.0.208): asked once a second for good, its
           button busy - the minute ends it as well. */
        if (Date.now() - began > 60000) {
          clearInterval(timer);
          left.forEach(function (n) { onEach(n, {ok: false, error: 'did not answer in a minute - is it running?'}); });
          if (onDone) onDone();
        }
      });
    }, 1000);""",
 """  return api(what, body).then(function (x) {
    var left = (x.nodes || []).slice(), began = Date.now();
    /* One ask at a time, and the end said once (1.0.317): a slow answer had the next second's ask
       overtake it - onDone twice (two toasts, the pane loaded twice), "did not answer" said again. */
    var asking = false, over = false;
    var end = function () {
      if (over) return;
      over = true;
      clearInterval(timer);
      left.forEach(function (n) { onEach(n, {ok: false, error: 'did not answer in a minute - is it running?'}); });
      left = [];
      if (onDone) onDone();
    };
    var timer = setInterval(function () {
      if (asking || over) return;
      asking = true;
      api(what, {action: 'result', id: x.id}).then(function (r) {
        asking = false;
        if (over) return;
        left = left.filter(function (n) {
          var got = (r.nodes || {})[n];
          if (got) { onEach(n, got); return false; }
          return true;
        });
        if (!left.length || Date.now() - began > 60000) end();
      }).catch(function () {
        asking = false;
        /* Every answer failing (1.0.208): asked once a second for good, its
           button busy - the minute ends it as well. */
        if (Date.now() - began > 60000) end();
      });
    }, 1000);"""),
("""    var left = nodes.slice(), began = Date.now(), got = {};
    var timer = setInterval(function () {
      api('dbtls', {action: 'result', id: id, of: of}).then(function (r) {
        left = left.filter(function (n) {
          var x = (r.nodes || {})[n];
          if (x) { got[n] = x; if (onEach) onEach(n, x); return false; }
          return true;
        });
        if (r.view) DBT.d = r.view;
        if (!left.length || Date.now() - began > 150000) {
          clearInterval(timer);
          left.forEach(function (n) { got[n] = {ok: false, error: 'did not answer in two and a half minutes - is it running?'}; });
          resolve(got);
        }
      }).catch(function () {
        if (Date.now() - began > 150000) {             /* (1.0.208) */
          clearInterval(timer);
          left.forEach(function (n) { got[n] = {ok: false, error: 'did not answer in two and a half minutes - is it running?'}; });
          resolve(got);
        }
      });
    }, 1000);""",
 """    var left = nodes.slice(), began = Date.now(), got = {};
    var asking = false, over = false;               /* one ask at a time, ended once (1.0.317) */
    var end = function () {
      if (over) return;
      over = true;
      clearInterval(timer);
      left.forEach(function (n) { got[n] = {ok: false, error: 'did not answer in two and a half minutes - is it running?'}; });
      left = [];
      resolve(got);
    };
    var timer = setInterval(function () {
      if (asking || over) return;
      asking = true;
      api('dbtls', {action: 'result', id: id, of: of}).then(function (r) {
        asking = false;
        if (over) return;
        left = left.filter(function (n) {
          var x = (r.nodes || {})[n];
          if (x) { got[n] = x; if (onEach) onEach(n, x); return false; }
          return true;
        });
        if (r.view) DBT.d = r.view;
        if (!left.length || Date.now() - began > 150000) end();
      }).catch(function () {
        asking = false;
        if (Date.now() - began > 150000) end();      /* (1.0.208) */
      });
    }, 1000);"""),
("""/* Is the address in the network? IPv4 by its bits; IPv6 the same address only. */
function lbIpIn(ip, net) {
  var p = String(net || '').split('/');
  if (ip.indexOf(':') >= 0 || p[0].indexOf(':') >= 0) return ip.toLowerCase() === p[0].toLowerCase();
""",
 """/* An IPv6 address as its 8 groups (1.0.317), or null. */
function lbV6(a) {
  a = String(a || '').toLowerCase();
  if (a.indexOf(':') < 0 || /[^0-9a-f:]/.test(a)) return null;
  var halves = a.split('::');
  if (halves.length > 2) return null;
  var head = halves[0] ? halves[0].split(':') : [], tail = halves.length === 2 && halves[1] ? halves[1].split(':') : [];
  var fill = 8 - head.length - tail.length;
  if (halves.length === 1 ? fill !== 0 : fill < 1) return null;
  var g = head.concat(new Array(halves.length === 2 ? fill : 0).fill('0'), tail).map(function (x) { return parseInt(x || '0', 16); });
  return g.length === 8 && g.every(function (x) { return x >= 0 && x <= 0xffff; }) ? g : null;
}
/* Is the address in the network? IPv4 by its bits; IPv6 by its bits too (1.0.317: the prefix was
   thrown away - a balancer inside 2001:db8::/64 was said not to be let in). */
function lbIpIn(ip, net) {
  var p = String(net || '').split('/');
  if (ip.indexOf(':') >= 0 || p[0].indexOf(':') >= 0) {
    var a6 = lbV6(ip), b6 = lbV6(p[0]), bits6 = p[1] === undefined ? 128 : +p[1];
    if (!a6 || !b6 || isNaN(bits6) || bits6 < 0 || bits6 > 128) return ip.toLowerCase() === p[0].toLowerCase();
    for (var i = 0; i < 8 && bits6 > 0; i++, bits6 -= 16) {
      var m6 = bits6 >= 16 ? 0xffff : (0xffff << (16 - bits6)) & 0xffff;
      if ((a6[i] & m6) !== (b6[i] & m6)) return false;
    }
    return true;
  }
"""),
("""    else if (tag === 'font' && n.getAttribute('color')) out += '<span style="color:' + n.getAttribute('color') + '">' + inner + '</span>';""",
 """    else if (tag === 'font' && n.getAttribute('color')) out += '<span style="color:' + htmlText(n.getAttribute('color')) + '">' + inner + '</span>';"""),
("""        all.onclick = function () { RQ_SINCE = null; loadRequests(); };""",
 """        all.onclick = function () { RQ_SINCE = null; PAGE.requests = 0; loadRequests(); };"""),
("""  do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
  return n.toFixed(n < 10 ? 1 : 0) + ' ' + u[i];""",
 """  do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
  var said = n.toFixed(n < 10 ? 1 : 0);
  return (numDecimal() === ',' ? said.replace('.', ',') : said) + ' ' + u[i];"""),
])
