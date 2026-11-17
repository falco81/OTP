# 1.0.294 web: the quick views count from the server; three grids that spilled at phone width.
#   python3 web.py OUTDIR (out/otp-VER)
import sys
D = sys.argv[1].rstrip('/') + '/web/assets/'


def edit(f, pairs):
    s = open(D + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:90])
        s = s.replace(a, b)
    open(D + f, 'w').write(s)


edit('admin.js', [
("""      result === 'accept' ? ['People', num(top.length)] : ['Wrong codes', num(dash.otp_bad || 0)],""",
 """      result === 'accept' ? ['People', num(dash.people != null ? dash.people : top.length)] : ['Wrong codes', num(dash.otp_bad || 0)],"""),
("""        openRequests(result === 'accept' ? {name: r.said, result: result} : {reason: r.said, result: result});""",
 """        /* The day the view counted (1.0.294), not the Log's last window. */
        var day = Date.now() / 1000 - 86400;
        openRequests(result === 'accept' ? {name: r.said, result: result, since: day} : {reason: r.said, result: result, since: day});"""),
("""  peek('Tokens', function () { return api('tokens&limit=1000&sort=last_used&desc=1'); }, function (body, d) {""",
 """  /* The locked ones asked for on their own (1.0.294): out of the newest used 1000 a token locked
     before it was ever used was missing, and "never used" counted only those 1000. */
  peek('Tokens', function () {
    return Promise.all([api('tokens&limit=1000&sort=last_used&desc=1'), api('tokens&limit=200&sort=locked_until&desc=1')])
      .then(function (two) { two[0].lockrows = two[1].rows || []; return two[0]; });
  }, function (body, d) {"""),
("""    var locked = rows.filter(function (r) { return r.locked_until && r.locked_until * 1000 > Date.now(); });
    var never = rows.filter(function (r) { return !r.last_used; }).length;""",
 """    var locked = (d.lockrows || rows).filter(function (r) { return r.locked_until && r.locked_until * 1000 > Date.now(); });
    var never = (d.counts && d.counts.never_used != null) ? d.counts.never_used : rows.filter(function (r) { return !r.last_used; }).length;"""),
])

edit('otp.css', [
(""".rb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}""",
 """.rb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(330px,100%),1fr));gap:12px}"""),
("""  .msects{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px;margin:16px 0 6px}""",
 """  .msects{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(330px,100%),1fr));gap:14px;margin:16px 0 6px}"""),
(""".ntp-srv .check{white-space:nowrap}""",
 """.ntp-srv .check{white-space:nowrap}
@media (max-width:640px){.ntp-srv{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}"""),
])
print('ok')
