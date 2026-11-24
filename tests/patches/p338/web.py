"""1.0.338 (web, OUTDIR): the SMS counter of the texts' editor as the SMS is sent."""
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
("""  return t.normalize('NFKD').replace(/[̀-ͯ]/g, '');
""",
 """  /* As the server sends it (1.0.338): its dashes and quotes too - one "–" counted the SMS as
     Unicode, 70 a part, while it went as one plain SMS. */
  return t.normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[–—]/g, '-')
    .replace(/[„“]/g, '"');
"""),
])
