"""1.0.316 (web, OUTDIR): what a node said on Settings → Logs, when it is otp's own sentence, in the page's
language - as the facets do (a word alone, a path, stays as written)."""
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
("""      if (n.said && !n.ok) c.appendChild(noI18n(el('div', 'si-said small', n.said)));
      var row2 = el('div', 'btnrow');
      var again = cmdButton('Put in and look again', 'refresh', 'small');""",
 """      if (n.said && !n.ok) {
        /* otp's own sentence (the root helper did not answer...) in the page's language (1.0.316);
           what only a tool says matches nothing and stays as it is. */
        var lsaid = noI18n(el('div', 'si-said small', n.said));
        if (/\\s/.test(n.said)) lsaid.removeAttribute('data-no-i18n');
        c.appendChild(lsaid);
      }
      var row2 = el('div', 'btnrow');
      var again = cmdButton('Put in and look again', 'refresh', 'small');"""),
])
