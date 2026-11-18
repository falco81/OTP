"""1.0.312 (web, OUTDIR): a domain that never locks - its window and duration greyed, not as if in force."""
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
("""    tile('counted over', dpSpan(lk.window_s));
    tile('locked for', dpSpan(lk.duration_s));""",
 """    /* Never locked (1.0.312): the window and the duration the domain keeps mean nothing - greyed, not
       shown as if they were in force. */
    tile('counted over', dpSpan(lk.window_s), lk.threshold ? '' : 'dim');
    tile('locked for', dpSpan(lk.duration_s), lk.threshold ? '' : 'dim');"""),
])
edit(OUT / 'web/assets/otp.css', [
(""".dp-tile.warn{border-color:rgba(210,153,34,.5);background:var(--warn-bg)}""",
 """.dp-tile.warn{border-color:rgba(210,153,34,.5);background:var(--warn-bg)}
.dp-tile.dim{opacity:.45}"""),
])
print('ok')
